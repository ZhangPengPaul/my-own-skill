import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from commit_learning_state import commit_fact  # noqa: E402
import delete_observations as delete_observations_module  # noqa: E402
import validate_student_data  # noqa: E402
from delete_observations import delete_observations  # noqa: E402
from learning_state import ValidationError  # noqa: E402
from summarize_progress import render  # noqa: E402
from tests.workspace_fixtures import create_workspace, interaction_observation  # noqa: E402


class DeleteObservationsTest(unittest.TestCase):
    def test_replaced_candidate_after_snapshot_is_preserved_and_deletion_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(
                workspace,
                observations=[
                    interaction_observation(),
                    interaction_observation(
                        record_id="observation-002",
                        interaction_id="interaction-002",
                    ),
                ],
            )
            unchanged = workspace / "observations/observation-001.json"
            unchanged_body = unchanged.read_bytes()
            candidate = workspace / "observations/observation-002.json"
            replacement = b"non-cooperating replacement\n"
            real_read_snapshot = (
                delete_observations_module._read_workspace_snapshot_fd_unlocked
            )
            replaced = False

            def read_snapshot_then_replace(*args, **kwargs):
                nonlocal replaced
                snapshot = real_read_snapshot(*args, **kwargs)
                candidate.unlink()
                candidate.write_bytes(replacement)
                replaced = True
                return snapshot

            with mock.patch.object(
                delete_observations_module,
                "_read_workspace_snapshot_fd_unlocked",
                side_effect=read_snapshot_then_replace,
            ):
                with self.assertRaisesRegex(
                    ValidationError,
                    "observation identity changed",
                ):
                    delete_observations(workspace)

            self.assertTrue(replaced)
            self.assertEqual(unchanged_body, unchanged.read_bytes())
            self.assertEqual(replacement, candidate.read_bytes())

    def test_deletion_keeps_using_opened_workspace_when_path_is_retargeted_after_migration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            requested = root / "student-a"
            moved_requested = root / "student-a-moved"
            replacement = root / "student-b"
            create_workspace(
                requested,
                observations=[interaction_observation(record_id="observation-a")],
            )
            create_workspace(
                replacement,
                observations=[interaction_observation(record_id="observation-b")],
            )
            real_cleanup = validate_student_data._cleanup_lock_descriptor
            retargeted = False

            def cleanup_then_retarget(lock_fd):
                nonlocal retargeted
                real_cleanup(lock_fd)
                if not retargeted:
                    requested.rename(moved_requested)
                    try:
                        requested.symlink_to(replacement, target_is_directory=True)
                    except (NotImplementedError, OSError) as error:
                        self.skipTest(f"symlinks are unavailable: {error}")
                    retargeted = True

            with mock.patch.object(
                validate_student_data,
                "_cleanup_lock_descriptor",
                side_effect=cleanup_then_retarget,
            ):
                self.assertEqual(1, delete_observations(requested))

            self.assertTrue(retargeted)
            self.assertEqual([], list((moved_requested / "observations").iterdir()))
            self.assertTrue(
                (replacement / "observations" / "observation-b.json").is_file()
            )

    def test_deletion_removes_pending_summary_without_changing_formal_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace, observations=[
                interaction_observation(),
                interaction_observation(record_id="observation-002", interaction_id="interaction-002"),
            ])
            state_before = (workspace / "state.json").read_bytes()
            before = render(workspace, now="2026-08-08T00:00:00+00:00")
            self.assertIn("出现 2 次", before)
            self.assertEqual(2, delete_observations(
                workspace, target_id="mathematics.geometry.dihedral-angle",
            ))
            after = render(workspace, now="2026-08-08T00:00:00+00:00")
            self.assertIn("- 无待验证观察", after)
            self.assertNotIn("出现 2 次", after)
            self.assertEqual([], list((workspace / "observations").iterdir()))
            self.assertEqual(state_before, (workspace / "state.json").read_bytes())

    def test_filters_and_removes_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "init_student.py"), "--root", str(root), "student-a"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            workspace = root / "student-a"
            for number, subject, when in (
                (1, "mathematics", "2026-08-01T00:00:00+00:00"),
                (2, "english", "2026-08-02T00:00:00+00:00"),
                (3, "mathematics", "2026-08-03T00:00:00+00:00"),
            ):
                commit_fact(workspace, interaction_observation(
                    record_id="observation-%03d" % number,
                    interaction_id="interaction-%03d" % number,
                    subject=subject,
                    module_id=("vocabulary-and-grammar" if subject == "english" else "geometry"),
                    target_id=("english.vocabulary.word" if subject == "english" else "mathematics.geometry.dihedral-angle"),
                    occurred_at=when,
                ), now="2026-08-04T00:00:00+00:00")
            self.assertEqual(1, delete_observations(
                workspace, subject="mathematics", before="2026-08-02T00:00:00+00:00"
            ))
            self.assertFalse((workspace / "observations/observation-001.json").exists())
            self.assertTrue((workspace / "observations/observation-003.json").exists())


if __name__ == "__main__":
    unittest.main()
