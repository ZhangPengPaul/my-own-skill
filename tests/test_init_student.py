from datetime import datetime, timedelta
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/shanghai-high-school-study-coach"
SCRIPTS = SKILL / "scripts"
SCRIPT = SCRIPTS / "init_student.py"
sys.path.insert(0, str(SCRIPTS))

import init_student


class InitStudentTest(unittest.TestCase):
    def run_init(self, root, student_id, script=SCRIPT):
        return subprocess.run(
            [sys.executable, str(script), "--root", str(root), student_id],
            capture_output=True,
            text=True,
        )

    def assert_template_error(self, mutate_template):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            copied_skill = base / "skill"
            shutil.copytree(SKILL / "scripts", copied_skill / "scripts")
            shutil.copytree(SKILL / "assets", copied_skill / "assets")
            template = copied_skill / "assets/student-workspace-template"
            mutate_template(template)
            workspace_root = base / "workspaces"

            result = self.run_init(
                workspace_root,
                "student-a",
                copied_skill / "scripts/init_student.py",
            )

            self.assertEqual(1, result.returncode, result.stderr)
            self.assertTrue(
                result.stderr.startswith("ERROR:"),
                f"unexpected stderr: {result.stderr!r}",
            )
            self.assertNotIn("Traceback", result.stderr)
            if workspace_root.exists():
                self.assertEqual([], list(workspace_root.iterdir()))

    def test_creates_valid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "student-a")
            self.assertEqual(0, result.returncode, result.stderr)
            workspace = root / "student-a"
            for relative in (
                "profile.md",
                "state.json",
                "plans/current.md",
                "mistakes",
                "sessions",
                "materials",
            ):
                self.assertTrue((workspace / relative).exists(), relative)
            state = json.loads(
                (workspace / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual("student-a", state["student_id"])
            updated_at = datetime.fromisoformat(state["updated_at"])
            self.assertIsNotNone(updated_at.tzinfo)
            self.assertEqual(timedelta(0), updated_at.utcoffset())
            self.assertNotIn(
                "__STUDENT_ID__",
                (workspace / "profile.md").read_text(encoding="utf-8"),
            )

    def test_refuses_to_overwrite_existing_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(0, self.run_init(root, "student-a").returncode)
            marker = root / "student-a" / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            result = self.run_init(root, "student-a")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_invalid_id_leaves_no_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Student Name")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual([], list(root.iterdir()))

    def test_root_symlink_retarget_does_not_redirect_initialization_or_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            real_root = base / "real-root"
            outside_root = base / "outside-root"
            real_root.mkdir()
            outside_root.mkdir()
            alias = base / "workspace-alias"
            try:
                alias.symlink_to(real_root, target_is_directory=True)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")

            outside_destination = outside_root / "student-a"
            outside_destination.mkdir()
            outside_destination_marker = outside_destination / "marker.txt"
            outside_destination_marker.write_text("preserve", encoding="utf-8")
            original_validate = init_student.validate_workspace
            outside_temporary = {}

            def retarget_alias(workspace):
                original_validate(workspace)
                temporary = outside_root / workspace.name
                temporary.mkdir()
                (temporary / "marker.txt").write_text("preserve", encoding="utf-8")
                outside_temporary["path"] = temporary
                alias.unlink()
                alias.symlink_to(outside_root, target_is_directory=True)

            with mock.patch.object(
                init_student, "validate_workspace", side_effect=retarget_alias
            ):
                try:
                    destination = init_student.initialize(alias, "student-a")
                except OSError as error:
                    self.fail(f"initialization followed a retargeted root alias: {error}")

            self.assertEqual(real_root.resolve() / "student-a", destination)
            self.assertTrue((destination / "state.json").is_file())
            self.assertEqual(
                "preserve", outside_destination_marker.read_text(encoding="utf-8")
            )
            self.assertEqual(
                "preserve",
                (outside_temporary["path"] / "marker.txt").read_text(
                    encoding="utf-8"
                ),
            )

    def test_concurrent_empty_destination_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "student-a"
            destination_inode = {}
            original_validate = init_student.validate_workspace

            def create_destination(workspace):
                original_validate(workspace)
                destination.mkdir()
                destination_inode["before"] = destination.stat().st_ino

            with mock.patch.object(
                init_student, "validate_workspace", side_effect=create_destination
            ):
                with self.assertRaisesRegex(
                    init_student.ValidationError, "workspace already exists"
                ):
                    init_student.initialize(root, "student-a")

            self.assertEqual(destination_inode["before"], destination.stat().st_ino)
            self.assertEqual([], list(destination.iterdir()))
            self.assertEqual(
                [],
                [path for path in root.iterdir() if path.name.startswith(".student-a-")],
            )

    def test_platform_publish_is_atomic_and_no_clobber(self):
        if not (
            sys.platform == "darwin"
            or sys.platform.startswith("linux")
            or sys.platform == "win32"
        ):
            self.skipTest(f"no platform primitive contract for {sys.platform}")
        self.assertTrue(
            hasattr(init_student, "_publish_no_replace"),
            "no-clobber publisher is missing",
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "marker.txt").write_text("published", encoding="utf-8")
            destination = root / "destination"

            init_student._publish_no_replace(source, destination)

            self.assertFalse(source.exists())
            self.assertEqual(
                "published", (destination / "marker.txt").read_text(encoding="utf-8")
            )

            second_source = root / "second-source"
            second_source.mkdir()
            occupied = root / "occupied"
            occupied.mkdir()
            occupied_inode = occupied.stat().st_ino

            with self.assertRaisesRegex(
                init_student.ValidationError, "workspace already exists"
            ):
                init_student._publish_no_replace(second_source, occupied)

            self.assertTrue(second_source.is_dir())
            self.assertEqual(occupied_inode, occupied.stat().st_ino)

    def test_keyboard_interrupt_cleans_owned_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch.object(
                init_student,
                "validate_workspace",
                side_effect=KeyboardInterrupt("stop"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    init_student.initialize(root, "student-a")

            self.assertEqual([], list(root.iterdir()))

    def test_cleanup_does_not_delete_replaced_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_validate = init_student.validate_workspace
            replacement = {}

            def replace_temporary(workspace):
                original_validate(workspace)
                workspace.rename(workspace.with_name(workspace.name + "-moved"))
                workspace.mkdir()
                marker = workspace / "marker.txt"
                marker.write_text("external", encoding="utf-8")
                replacement["path"] = workspace
                raise RuntimeError("injected failure")

            with mock.patch.object(
                init_student, "validate_workspace", side_effect=replace_temporary
            ):
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    init_student.initialize(root, "student-a")

            self.assertTrue(
                replacement["path"].is_dir(),
                "cleanup deleted a directory that replaced the owned temporary",
            )
            self.assertEqual(
                "external",
                (replacement["path"] / "marker.txt").read_text(encoding="utf-8"),
            )
            self.assertFalse((root / "student-a").exists())

    def test_cleanup_stays_on_verified_inode_when_top_level_name_is_replaced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_validate = init_student.validate_workspace
            real_fstat = os.fstat
            real_rmtree = shutil.rmtree
            probe = {}

            def fail_after_validation(workspace):
                original_validate(workspace)
                probe["temporary"] = workspace
                raise RuntimeError("injected failure")

            def replace_top_level_name():
                if "replacement" in probe:
                    return
                temporary = probe["temporary"]
                moved = temporary.with_name(temporary.name + "-moved-after-open")
                temporary.rename(moved)
                temporary.mkdir()
                marker = temporary / "marker.txt"
                marker.write_text("external", encoding="utf-8")
                probe["moved"] = moved
                probe["replacement"] = temporary

            def replace_before_path_rmtree(path, *args, **kwargs):
                replace_top_level_name()
                return real_rmtree(path, *args, **kwargs)

            def replace_after_directory_open(file_descriptor):
                opened = real_fstat(file_descriptor)
                if "temporary" in probe:
                    replace_top_level_name()
                return opened

            with mock.patch.object(
                init_student,
                "validate_workspace",
                side_effect=fail_after_validation,
            ), mock.patch.object(
                shutil,
                "rmtree",
                side_effect=replace_before_path_rmtree,
            ), mock.patch.object(
                init_student.os,
                "fstat",
                side_effect=replace_after_directory_open,
            ):
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    init_student.initialize(root, "student-a")

            self.assertTrue(
                probe["replacement"].is_dir(),
                "cleanup deleted the directory that replaced the temporary name",
            )
            self.assertEqual(
                "external",
                (probe["replacement"] / "marker.txt").read_text(encoding="utf-8"),
            )
            self.assertTrue(probe["moved"].is_dir())
            self.assertEqual([], list(probe["moved"].iterdir()))
            self.assertFalse((root / "student-a").exists())

    def test_rejects_source_replacement_after_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "student-a"
            original_validate = init_student.validate_workspace
            probe = {}

            def replace_after_validation(workspace):
                original_validate(workspace)
                moved = root / "moved-original"
                workspace.rename(moved)
                workspace.mkdir()
                marker = workspace / "foreign-marker.txt"
                marker.write_text("foreign", encoding="utf-8")
                probe["moved"] = moved
                probe["replacement"] = workspace

            with mock.patch.object(
                init_student,
                "validate_workspace",
                side_effect=replace_after_validation,
            ):
                with self.assertRaisesRegex(
                    init_student.ValidationError, "identity|changed"
                ):
                    init_student.initialize(root, "student-a")

            self.assertFalse(destination.exists())
            self.assertEqual(
                "foreign",
                (probe["replacement"] / "foreign-marker.txt").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual([], list(probe["moved"].iterdir()))

    def test_post_publish_identity_mismatch_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "student-a"
            real_publish = init_student._publish_no_replace
            probe = {}

            def replace_at_publish(source, publish_destination):
                if "replacement" not in probe:
                    moved = root / "moved-after-precheck"
                    source.rename(moved)
                    source.mkdir()
                    marker = source / "foreign-marker.txt"
                    marker.write_text("foreign", encoding="utf-8")
                    probe["moved"] = moved
                    probe["replacement"] = source
                return real_publish(source, publish_destination)

            with mock.patch.object(
                init_student,
                "_publish_no_replace",
                side_effect=replace_at_publish,
            ):
                with self.assertRaisesRegex(
                    init_student.ValidationError, "identity|changed"
                ):
                    init_student.initialize(root, "student-a")

            self.assertFalse(destination.exists())
            self.assertEqual(
                "foreign",
                (probe["replacement"] / "foreign-marker.txt").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual([], list(probe["moved"].iterdir()))

    def test_failed_identity_rollback_requires_manual_inspection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "student-a"
            real_publish = init_student._publish_no_replace
            probe = {}

            def replace_and_block_rollback(source, publish_destination):
                if "replacement" not in probe:
                    moved = root / "moved-before-failed-rollback"
                    source.rename(moved)
                    source.mkdir()
                    marker = source / "foreign-marker.txt"
                    marker.write_text("foreign", encoding="utf-8")
                    probe["moved"] = moved
                    probe["replacement"] = source
                    result = real_publish(source, publish_destination)
                    source.mkdir()
                    (source / "blocker.txt").write_text(
                        "preserve", encoding="utf-8"
                    )
                    return result
                return real_publish(source, publish_destination)

            with mock.patch.object(
                init_student,
                "_publish_no_replace",
                side_effect=replace_and_block_rollback,
            ):
                with self.assertRaisesRegex(
                    init_student.ValidationError, "manual inspection|人工"
                ):
                    init_student.initialize(root, "student-a")

            self.assertEqual(
                "foreign",
                (destination / "foreign-marker.txt").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "preserve",
                (probe["replacement"] / "blocker.txt").read_text(encoding="utf-8"),
            )
            self.assertEqual([], list(probe["moved"].iterdir()))

    def test_rejects_non_utf8_profile_without_partial_workspace(self):
        self.assert_template_error(
            lambda template: (template / "profile.md").write_bytes(b"\xff")
        )

    def test_rejects_non_object_state_without_partial_workspace(self):
        self.assert_template_error(
            lambda template: (template / "state.json").write_text(
                "[]\n", encoding="utf-8"
            )
        )

    def test_rejects_missing_profile_placeholder_without_partial_workspace(self):
        self.assert_template_error(
            lambda template: (template / "profile.md").write_text(
                "# 学生档案\n", encoding="utf-8"
            )
        )

    def test_rejects_duplicate_profile_placeholder_without_partial_workspace(self):
        def duplicate_placeholder(template):
            profile = template / "profile.md"
            content = profile.read_text(encoding="utf-8")
            profile.write_text(
                content.replace(
                    "__STUDENT_ID__", "__STUDENT_ID__\n__STUDENT_ID__"
                ),
                encoding="utf-8",
            )

        self.assert_template_error(duplicate_placeholder)

    def test_rejects_non_utf8_current_plan_without_partial_workspace(self):
        self.assert_template_error(
            lambda template: (template / "plans/current.md").write_bytes(b"\xff")
        )

    def test_rejects_non_utf8_record_templates_without_partial_workspace(self):
        for filename in (
            "session-record-template.md",
            "mistake-record-template.md",
        ):
            with self.subTest(filename=filename):
                self.assert_template_error(
                    lambda template, filename=filename: (
                        template.parent / filename
                    ).write_bytes(b"\xff")
                )


if __name__ == "__main__":
    unittest.main()
