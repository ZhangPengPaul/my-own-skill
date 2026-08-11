from datetime import datetime, timedelta
from pathlib import Path
import errno
import json
import os
import shutil
import stat
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
    def temporary_path(self, root):
        candidates = [
            path for path in root.iterdir() if path.name.startswith(".student-a-")
        ]
        self.assertEqual(1, len(candidates))
        return candidates[0]

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
                ".workspace.lock",
                "sessions",
                "plan-items",
                "summaries",
                "materials",
            ):
                self.assertTrue((workspace / relative).exists(), relative)
            state = json.loads(
                (workspace / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual("student-a", state["student_id"])
            self.assertEqual(2, state["schema_version"])
            self.assertEqual(
                {
                    "chinese",
                    "mathematics",
                    "english",
                    "politics",
                    "history",
                    "geography",
                },
                set(state["subjects"]),
            )
            for subject in state["subjects"].values():
                self.assertEqual(
                    {"knowledge_units", "patterns"},
                    set(subject),
                )
            updated_at = datetime.fromisoformat(state["updated_at"])
            self.assertIsNotNone(updated_at.tzinfo)
            self.assertEqual(timedelta(0), updated_at.utcoffset())
            self.assertNotIn(
                "__STUDENT_ID__",
                (workspace / "profile.md").read_text(encoding="utf-8"),
            )
            profile = (workspace / "profile.md").read_text(encoding="utf-8")
            for field in (
                "grade",
                "term",
                "current_materials",
                "teacher_priorities",
                "learning_preferences",
                "available_time",
                "learning_goals",
            ):
                self.assertIn(field, profile)
            for removed in ("selected_subjects", "target_exams", "target_dates"):
                self.assertNotIn(removed, profile)

    def test_file_close_error_does_not_mask_write_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory_fd = os.open(tmp, os.O_RDONLY)
            created_fd = {}
            close_attempts = []
            real_open = os.open
            real_close = os.close

            def track_open(*args, **kwargs):
                file_fd = real_open(*args, **kwargs)
                created_fd["value"] = file_fd
                return file_fd

            def fail_write(file_fd, data):
                raise OSError("fictional primary write failure")

            def fail_created_close(file_fd):
                if file_fd == created_fd.get("value"):
                    close_attempts.append(file_fd)
                    raise OSError("fictional file close failure")
                return real_close(file_fd)

            try:
                with mock.patch.object(
                    init_student.os,
                    "open",
                    side_effect=track_open,
                ), mock.patch.object(
                    init_student.os,
                    "write",
                    side_effect=fail_write,
                ), mock.patch.object(
                    init_student.os,
                    "close",
                    side_effect=fail_created_close,
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        "primary write failure",
                    ):
                        init_student._write_new_file(
                            directory_fd,
                            "fictional.txt",
                            "content",
                        )
                self.assertEqual([created_fd["value"]], close_attempts)
            finally:
                if "value" in created_fd:
                    real_close(created_fd["value"])
                real_close(directory_fd)

    def test_file_close_failure_propagates_after_successful_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory_fd = os.open(tmp, os.O_RDONLY)
            created_fd = {}
            close_attempts = []
            real_open = os.open
            real_close = os.close

            def track_open(*args, **kwargs):
                file_fd = real_open(*args, **kwargs)
                created_fd["value"] = file_fd
                return file_fd

            def fail_created_close(file_fd):
                if file_fd == created_fd.get("value"):
                    close_attempts.append(file_fd)
                    raise OSError("fictional file close failure")
                return real_close(file_fd)

            try:
                with mock.patch.object(
                    init_student.os,
                    "open",
                    side_effect=track_open,
                ), mock.patch.object(
                    init_student.os,
                    "close",
                    side_effect=fail_created_close,
                ):
                    with self.assertRaisesRegex(
                        OSError,
                        "file close failure",
                    ):
                        init_student._write_new_file(
                            directory_fd,
                            "fictional.txt",
                            "content",
                        )
                self.assertEqual([created_fd["value"]], close_attempts)
            finally:
                if "value" in created_fd:
                    real_close(created_fd["value"])
                real_close(directory_fd)

    def test_temporary_name_replacement_does_not_redirect_construction(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outside = root / "outside"
            outside.mkdir()
            marker = outside / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            real_mkdir_at = getattr(init_student, "_mkdir_at", None)
            self.assertIsNotNone(real_mkdir_at, "descriptor-relative mkdir is missing")
            calls = 0

            def replace_name_after_first_child(parent_fd, name):
                nonlocal calls
                child_fd = real_mkdir_at(parent_fd, name)
                calls += 1
                if calls == 1:
                    temporary_names = [
                        path
                        for path in root.iterdir()
                        if path.name.startswith(".student-a-")
                    ]
                    self.assertEqual(1, len(temporary_names))
                    temporary = temporary_names[0]
                    moved = root / "owned-moved"
                    temporary.rename(moved)
                    try:
                        temporary.symlink_to(outside, target_is_directory=True)
                    except (NotImplementedError, OSError) as error:
                        os.close(child_fd)
                        self.skipTest(f"symlinks are unavailable: {error}")
                return child_fd

            with mock.patch.object(
                init_student,
                "_mkdir_at",
                side_effect=replace_name_after_first_child,
            ):
                with self.assertRaisesRegex(
                    init_student.ValidationError,
                    "identity|changed",
                ):
                    init_student.initialize(root, "student-a")

            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))
            self.assertEqual([marker], list(outside.iterdir()))
            self.assertFalse((root / "student-a").exists())

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
            original_validate = init_student.validate_workspace_fd
            outside_temporary = {}

            def retarget_alias(workspace_fd):
                original_validate(workspace_fd)
                owned_temporary = self.temporary_path(real_root)
                temporary = outside_root / owned_temporary.name
                temporary.mkdir()
                (temporary / "marker.txt").write_text("preserve", encoding="utf-8")
                outside_temporary["path"] = temporary
                alias.unlink()
                alias.symlink_to(outside_root, target_is_directory=True)

            with mock.patch.object(
                init_student, "validate_workspace_fd", side_effect=retarget_alias
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
            original_validate = init_student.validate_workspace_fd

            def create_destination(workspace_fd):
                original_validate(workspace_fd)
                destination.mkdir()
                destination_inode["before"] = destination.stat().st_ino

            with mock.patch.object(
                init_student, "validate_workspace_fd", side_effect=create_destination
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
                "validate_workspace_fd",
                side_effect=KeyboardInterrupt("stop"),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    init_student.initialize(root, "student-a")

            self.assertEqual([], list(root.iterdir()))

    def test_workspace_publish_fsyncs_temporary_before_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            temporary = root / "temporary"
            destination = root / "student-a"
            temporary.mkdir()
            root_fd = os.open(root, init_student._directory_open_flags())
            temporary_fd = os.open(
                temporary,
                init_student._directory_open_flags(),
            )
            opened = os.fstat(temporary_fd)
            identity = (opened.st_dev, opened.st_ino)
            events = []
            real_fsync = os.fsync
            real_publish = init_student._publish_no_replace

            def track_fsync(file_fd):
                if file_fd == temporary_fd:
                    events.append("fsync-temporary")
                elif file_fd == root_fd:
                    events.append("fsync-root")
                return real_fsync(file_fd)

            def track_publish(source, target):
                events.append("publish")
                return real_publish(source, target)

            try:
                with mock.patch.object(
                    init_student.os,
                    "fsync",
                    side_effect=track_fsync,
                ), mock.patch.object(
                    init_student,
                    "_publish_no_replace",
                    side_effect=track_publish,
                ):
                    init_student._publish_verified_workspace(
                        root_fd,
                        temporary,
                        destination,
                        temporary_fd,
                        identity,
                    )
            finally:
                os.close(temporary_fd)
                os.close(root_fd)

            self.assertEqual(
                ["fsync-temporary", "publish", "fsync-root"],
                events,
            )

    def test_directory_fsync_failures_leave_no_partial_workspace(self):
        for stage in ("temporary", "root"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                root_identity = (root.stat().st_dev, root.stat().st_ino)
                real_fsync = os.fsync
                failed = False

                def fail_selected_directory_fsync(file_fd):
                    nonlocal failed
                    entry = os.fstat(file_fd)
                    if not stat.S_ISDIR(entry.st_mode):
                        return real_fsync(file_fd)
                    identity = (entry.st_dev, entry.st_ino)
                    selected = (
                        identity != root_identity
                        if stage == "temporary"
                        else identity == root_identity
                    )
                    if selected and not failed:
                        failed = True
                        raise OSError("fictional %s fsync failure" % stage)
                    return real_fsync(file_fd)

                with mock.patch.object(
                    init_student.os,
                    "fsync",
                    side_effect=fail_selected_directory_fsync,
                ):
                    with self.assertRaisesRegex(OSError, "%s fsync" % stage):
                        init_student.initialize(root, "student-a")

                self.assertTrue(failed)
                self.assertEqual([], list(root.iterdir()))

    def test_mkdtemp_open_recovers_by_releasing_reserved_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_open = os.open
            real_close = os.close
            real_dup = os.dup
            failed_calls = 0
            reserve = {"fd": None, "released": False}

            def track_reserve(file_fd):
                reserve["fd"] = real_dup(file_fd)
                return reserve["fd"]

            def track_reserve_release(file_fd):
                if file_fd == reserve["fd"]:
                    reserve["released"] = True
                return real_close(file_fd)

            def fail_temporary_open(path, *args, **kwargs):
                nonlocal failed_calls
                if (
                    isinstance(path, str)
                    and path.startswith(".student-a-")
                    and not reserve["released"]
                ):
                    failed_calls += 1
                    raise OSError(
                        errno.EMFILE,
                        "fictional persistent temporary open failure",
                    )
                return real_open(path, *args, **kwargs)

            with mock.patch.object(
                init_student.os,
                "open",
                side_effect=fail_temporary_open,
            ), mock.patch.object(
                init_student.os,
                "dup",
                side_effect=track_reserve,
            ), mock.patch.object(
                init_student.os,
                "close",
                side_effect=track_reserve_release,
            ):
                destination = init_student.initialize(root, "student-a")

            self.assertEqual(1, failed_calls)
            self.assertTrue(reserve["released"])
            self.assertEqual(root.resolve() / "student-a", destination)
            self.assertEqual(
                ["student-a"],
                [path.name for path in root.iterdir()],
            )

    def test_failed_recovery_open_never_deletes_replacement_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            real_open = os.open
            real_close = os.close
            real_dup = os.dup
            reserve = {"fd": None, "released": False}
            attempts = 0
            paths = {}

            def track_reserve(file_fd):
                reserve["fd"] = real_dup(file_fd)
                return reserve["fd"]

            def track_reserve_release(file_fd):
                if file_fd == reserve["fd"]:
                    reserve["released"] = True
                return real_close(file_fd)

            def fail_and_replace_temporary(path, *args, **kwargs):
                nonlocal attempts
                if isinstance(path, str) and path.startswith(".student-a-"):
                    attempts += 1
                    if attempts == 2:
                        temporary = root / path
                        moved = root / "owned-moved-after-emfile"
                        temporary.rename(moved)
                        temporary.mkdir()
                        marker = temporary / "foreign-marker.txt"
                        marker.write_text("preserve", encoding="utf-8")
                        paths["moved"] = moved
                        paths["replacement"] = temporary
                    raise OSError(errno.EMFILE, "fictional persistent EMFILE")
                return real_open(path, *args, **kwargs)

            with mock.patch.object(
                init_student.os,
                "open",
                side_effect=fail_and_replace_temporary,
            ), mock.patch.object(
                init_student.os,
                "dup",
                side_effect=track_reserve,
            ), mock.patch.object(
                init_student.os,
                "close",
                side_effect=track_reserve_release,
            ):
                with self.assertRaisesRegex(OSError, "persistent EMFILE"):
                    init_student.initialize(root, "student-a")

            self.assertEqual(2, attempts)
            self.assertTrue(reserve["released"])
            self.assertEqual(
                "preserve",
                (paths["replacement"] / "foreign-marker.txt").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertTrue(paths["moved"].is_dir())
            self.assertFalse((root / "student-a").exists())

    def test_mkdir_fstat_failure_closes_child_descriptor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root_fd = os.open(tmp, init_student._directory_open_flags())
            child_fd = None
            real_open = os.open
            real_close = os.close

            def track_child_open(path, *args, **kwargs):
                nonlocal child_fd
                child_fd = real_open(path, *args, **kwargs)
                return child_fd

            try:
                with mock.patch.object(
                    init_student.os,
                    "open",
                    side_effect=track_child_open,
                ), mock.patch.object(
                    init_student.os,
                    "fstat",
                    side_effect=OSError("fictional child fstat failure"),
                ):
                    with self.assertRaisesRegex(OSError, "child fstat failure"):
                        init_student._mkdir_at(root_fd, "child")

                self.assertIsNotNone(child_fd)
                with self.assertRaises(OSError):
                    os.fstat(child_fd)
            finally:
                if child_fd is not None:
                    try:
                        real_close(child_fd)
                    except OSError:
                        pass
                real_close(root_fd)

    def test_cleanup_does_not_delete_replaced_temporary_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original_validate = init_student.validate_workspace_fd
            replacement = {}

            def replace_temporary(workspace_fd):
                original_validate(workspace_fd)
                workspace = self.temporary_path(root)
                workspace.rename(workspace.with_name(workspace.name + "-moved"))
                workspace.mkdir()
                marker = workspace / "marker.txt"
                marker.write_text("external", encoding="utf-8")
                replacement["path"] = workspace
                raise RuntimeError("injected failure")

            with mock.patch.object(
                init_student, "validate_workspace_fd", side_effect=replace_temporary
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
            original_validate = init_student.validate_workspace_fd
            probe = {}

            def fail_after_validation(workspace_fd):
                original_validate(workspace_fd)
                workspace = self.temporary_path(root)
                probe["temporary"] = workspace
                temporary = probe["temporary"]
                moved = temporary.with_name(temporary.name + "-moved-after-open")
                temporary.rename(moved)
                temporary.mkdir()
                marker = temporary / "marker.txt"
                marker.write_text("external", encoding="utf-8")
                probe["moved"] = moved
                probe["replacement"] = temporary
                raise RuntimeError("injected failure")

            with mock.patch.object(
                init_student,
                "validate_workspace_fd",
                side_effect=fail_after_validation,
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
            original_validate = init_student.validate_workspace_fd
            probe = {}

            def replace_after_validation(workspace_fd):
                original_validate(workspace_fd)
                workspace = self.temporary_path(root)
                moved = root / "moved-original"
                workspace.rename(moved)
                workspace.mkdir()
                marker = workspace / "foreign-marker.txt"
                marker.write_text("foreign", encoding="utf-8")
                probe["moved"] = moved
                probe["replacement"] = workspace

            with mock.patch.object(
                init_student,
                "validate_workspace_fd",
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

    def test_rejects_missing_profile_marker_without_partial_workspace(self):
        self.assert_template_error(
            lambda template: (template / "profile.md").write_text(
                "# 学生档案\n", encoding="utf-8"
            )
        )

    def test_rejects_duplicate_profile_marker_without_partial_workspace(self):
        def duplicate_marker(template):
            profile = template / "profile.md"
            content = profile.read_text(encoding="utf-8")
            profile.write_text(
                content.replace(
                    "__STUDENT_ID__", "__STUDENT_ID__\n__STUDENT_ID__"
                ),
                encoding="utf-8",
            )

        self.assert_template_error(duplicate_marker)

if __name__ == "__main__":
    unittest.main()
