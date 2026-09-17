import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from tests.workspace_fixtures import (  # noqa: E402
    create_workspace,
    interaction_observation,
)

import commit_learning_state  # noqa: E402
import delete_observations  # noqa: E402
import init_student  # noqa: E402
from learning_state import ValidationError  # noqa: E402
import summarize_progress  # noqa: E402
import validate_student_data  # noqa: E402


class PersistentCliIdentityTest(unittest.TestCase):
    def _workspace(self, root, *, with_observation=False):
        workspace = root / "student-a"
        observations = [interaction_observation()] if with_observation else []
        create_workspace(workspace, observations=observations)
        return workspace

    def _fact_file(self, root):
        path = root / "observation-input.json"
        path.write_text(
            json.dumps(interaction_observation(), ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def _commands(self, root, student_id=None):
        commands = []
        for name in ("commit", "validate", "summarize", "delete"):
            case_root = root / name
            case_root.mkdir()
            workspace = self._workspace(
                case_root,
                with_observation=name == "delete",
            )
            if name == "commit":
                command = [
                    sys.executable,
                    str(SCRIPTS / "commit_learning_state.py"),
                    str(workspace),
                    "--fact-file",
                    str(self._fact_file(case_root)),
                ]
            elif name == "validate":
                command = [
                    sys.executable,
                    str(SCRIPTS / "validate_student_data.py"),
                    str(workspace),
                ]
            elif name == "summarize":
                command = [
                    sys.executable,
                    str(SCRIPTS / "summarize_progress.py"),
                    str(workspace),
                ]
            else:
                command = [
                    sys.executable,
                    str(SCRIPTS / "delete_observations.py"),
                    str(workspace),
                ]
            if student_id is not None:
                command.extend(("--student-id", student_id))
            commands.append((name, workspace, command))
        return commands

    def _identity_gate_entrypoints(self, root, *, mismatched):
        expected_student_id = "student-b" if mismatched else "student-a"
        entrypoints = []
        for name in ("commit", "validate", "summarize", "delete"):
            case_root = root / name
            case_root.mkdir()
            workspace = self._workspace(
                case_root,
                with_observation=name == "delete",
            )
            if name == "commit":
                invoke = lambda workspace=workspace: commit_learning_state.commit_fact(
                    workspace,
                    interaction_observation(),
                    expected_student_id=expected_student_id,
                )
            elif name == "validate":
                invoke = lambda workspace=workspace: validate_student_data.validate_workspace(
                    workspace,
                    expected_student_id=expected_student_id,
                )
            elif name == "summarize":
                invoke = lambda workspace=workspace: summarize_progress.render(
                    workspace,
                    expected_student_id=expected_student_id,
                )
            else:
                invoke = lambda workspace=workspace: delete_observations.delete_observations(
                    workspace,
                    expected_student_id=expected_student_id,
                )
            entrypoints.append((name, invoke))

        init_root = root / "init"
        workspace = self._workspace(init_root)
        if mismatched:
            state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
            state["student_id"] = "student-b"
            (workspace / "state.json").write_text(
                json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        entrypoints.append(
            (
                "init",
                lambda: init_student.ensure_workspace_with_status(
                    init_root,
                    "student-a",
                ),
            )
        )
        return entrypoints

    def _patch_full_snapshot_reads(self):
        def fail_full_snapshot(*args, **kwargs):
            raise RuntimeError("full snapshot read reached")

        return (
            mock.patch.object(
                validate_student_data,
                "_read_workspace_snapshot_fd_unlocked",
                side_effect=fail_full_snapshot,
            ),
            mock.patch.object(
                commit_learning_state,
                "_read_workspace_snapshot_fd_unlocked",
                side_effect=fail_full_snapshot,
            ),
            mock.patch.object(
                delete_observations,
                "_read_workspace_snapshot_fd_unlocked",
                side_effect=fail_full_snapshot,
            ),
        )

    def test_mismatched_identity_precedes_every_full_snapshot_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrypoints = self._identity_gate_entrypoints(
                Path(tmp),
                mismatched=True,
            )
            patches = self._patch_full_snapshot_reads()
            with patches[0], patches[1], patches[2]:
                for name, invoke in entrypoints:
                    with self.subTest(command=name):
                        with self.assertRaisesRegex(
                            ValidationError,
                            "workspace state student_id does not match requested student_id",
                        ):
                            invoke()

    def test_full_snapshot_fault_is_reachable_for_matching_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            entrypoints = self._identity_gate_entrypoints(
                Path(tmp),
                mismatched=False,
            )
            patches = self._patch_full_snapshot_reads()
            with patches[0], patches[1], patches[2]:
                for name, invoke in entrypoints:
                    with self.subTest(command=name):
                        with self.assertRaisesRegex(
                            RuntimeError,
                            "full snapshot read reached",
                        ):
                            invoke()

    def test_invalid_identity_is_rejected_before_opening_a_workspace(self):
        invalid_student_id = "Student B"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            entrypoints = self._identity_gate_entrypoints(root, mismatched=False)[:-1]
            open_failure = RuntimeError("workspace was opened for an invalid identity")
            with mock.patch.object(
                validate_student_data,
                "open_workspace_descriptor",
                side_effect=open_failure,
            ), mock.patch.object(
                commit_learning_state,
                "open_workspace_descriptor",
                side_effect=open_failure,
            ), mock.patch.object(
                delete_observations,
                "open_workspace_descriptor",
                side_effect=open_failure,
            ):
                for name, _ in entrypoints:
                    workspace = root / name / "student-a"
                    if name == "commit":
                        invoke = lambda workspace=workspace: commit_learning_state.commit_fact(
                            workspace,
                            interaction_observation(),
                            expected_student_id=invalid_student_id,
                        )
                    elif name == "validate":
                        invoke = lambda workspace=workspace: validate_student_data.validate_workspace(
                            workspace,
                            expected_student_id=invalid_student_id,
                        )
                    elif name == "summarize":
                        invoke = lambda workspace=workspace: summarize_progress.render(
                            workspace,
                            expected_student_id=invalid_student_id,
                        )
                    else:
                        invoke = lambda workspace=workspace: delete_observations.delete_observations(
                            workspace,
                            expected_student_id=invalid_student_id,
                        )
                    with self.subTest(command=name):
                        with self.assertRaisesRegex(
                            ValidationError,
                            "expected student_id is invalid",
                        ):
                            invoke()

    def test_persistent_clis_reject_missing_student_id_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, workspace, command in self._commands(Path(tmp)):
                before = {
                    path.relative_to(workspace): path.read_bytes()
                    for path in workspace.rglob("*")
                    if path.is_file()
                }
                result = subprocess.run(command, capture_output=True, text=True)
                after = {
                    path.relative_to(workspace): path.read_bytes()
                    for path in workspace.rglob("*")
                    if path.is_file()
                }
                with self.subTest(command=name):
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual(before, after)

    def test_persistent_clis_reject_mismatched_student_id_without_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, workspace, command in self._commands(
                Path(tmp), student_id="student-b"
            ):
                before = {
                    path.relative_to(workspace): path.read_bytes()
                    for path in workspace.rglob("*")
                    if path.is_file()
                }
                result = subprocess.run(command, capture_output=True, text=True)
                after = {
                    path.relative_to(workspace): path.read_bytes()
                    for path in workspace.rglob("*")
                    if path.is_file()
                }
                with self.subTest(command=name):
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual(before, after)

    def test_persistent_clis_accept_matching_student_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name, workspace, command in self._commands(
                Path(tmp), student_id="student-a"
            ):
                result = subprocess.run(command, capture_output=True, text=True)
                with self.subTest(command=name):
                    self.assertEqual(0, result.returncode, result.stderr)
                if name == "commit":
                    self.assertTrue(
                        (workspace / "observations/observation-001.json").is_file()
                    )
                elif name == "delete":
                    self.assertEqual([], list((workspace / "observations").iterdir()))


if __name__ == "__main__":
    unittest.main()
