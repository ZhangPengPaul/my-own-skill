import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
VALIDATOR_SCRIPT = SCRIPTS / "validate_student_data.py"
sys.path.insert(0, str(SCRIPTS))

import validate_student_data  # noqa: E402
import commit_learning_state  # noqa: E402
from commit_learning_state import commit_fact  # noqa: E402
from validate_student_data import (  # noqa: E402
    ValidationError,
    WorkspaceSnapshot,
    validate_state,
    validate_workspace,
)
from tests.workspace_fixtures import (  # noqa: E402
    create_workspace,
    knowledge_observation,
    plan_fact,
    session_fact,
    state_from_facts,
)


class ValidateStudentDataTest(unittest.TestCase):
    def run_validator(self, workspace):
        return subprocess.run(
            [sys.executable, str(VALIDATOR_SCRIPT), str(workspace)],
            capture_output=True,
            text=True,
        )

    def assert_cli_invalid(self, workspace):
        result = self.run_validator(workspace)
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertTrue(
            result.stderr.startswith("INVALID:"),
            f"unexpected stderr: {result.stderr!r}",
        )
        self.assertNotIn("Traceback", result.stderr)

    def test_accepts_empty_schema_v2_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            expected = create_workspace(workspace)

            snapshot = validate_workspace(workspace)

        self.assertIsInstance(snapshot, WorkspaceSnapshot)
        self.assertEqual(expected, snapshot.state)
        self.assertEqual((), snapshot.sessions)
        self.assertEqual((), snapshot.plan_items)

    def test_accepts_state_derived_from_active_facts(self):
        session = session_fact(observations=[knowledge_observation()])
        plan = plan_fact()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            expected = create_workspace(
                workspace,
                sessions=[session],
                plan_items=[plan],
            )

            snapshot = validate_workspace(workspace)

        self.assertEqual(expected, snapshot.state)
        self.assertEqual((session,), snapshot.sessions)
        self.assertEqual((plan,), snapshot.plan_items)

    def test_validation_waits_for_concurrent_commit_snapshot(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace)
            replace_entered = threading.Event()
            allow_replace = threading.Event()
            validation_finished = threading.Event()
            writer_errors = []
            validation_results = []
            real_replace = commit_learning_state._replace_state_atomically

            def blocked_replace(root_fd, state):
                replace_entered.set()
                if not allow_replace.wait(timeout=5):
                    raise RuntimeError("timed out waiting to replace state")
                return real_replace(root_fd, state)

            def write_fact():
                try:
                    commit_fact(workspace, fact)
                except BaseException as error:
                    writer_errors.append(error)

            def validate_snapshot():
                try:
                    validation_results.append(validate_workspace(workspace))
                except BaseException as error:
                    validation_results.append(error)
                finally:
                    validation_finished.set()

            writer = threading.Thread(target=write_fact)
            validator = threading.Thread(target=validate_snapshot)
            with mock.patch.object(
                commit_learning_state,
                "_replace_state_atomically",
                side_effect=blocked_replace,
            ):
                writer.start()
                self.assertTrue(replace_entered.wait(timeout=5))
                validator.start()
                finished_before_state_replace = validation_finished.wait(timeout=0.2)
                allow_replace.set()
                writer.join(timeout=5)
                validator.join(timeout=5)

            self.assertFalse(writer.is_alive())
            self.assertFalse(validator.is_alive())
            self.assertFalse(
                finished_before_state_replace,
                "validation read a snapshot while the writer held the workspace lock",
            )
            self.assertEqual([], writer_errors)
            self.assertEqual(1, len(validation_results))
            self.assertIsInstance(validation_results[0], WorkspaceSnapshot)
            self.assertEqual(
                1,
                validation_results[0].state["process"]["recorded_sessions"],
            )

    def test_rejects_fact_filename_that_does_not_match_record_id(self):
        session = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace, sessions=[session])
            original_path = workspace / "sessions/record-session-001.json"
            original_path.rename(workspace / "sessions/alias.json")

            with self.assertRaisesRegex(ValidationError, "filename|record_id"):
                validate_workspace(workspace)

    def test_validate_state_accepts_matching_facts(self):
        session = session_fact(observations=[knowledge_observation()])
        state = state_from_facts(sessions=[session])

        validate_state(state, [session], [])

    def test_read_failure_is_reported_as_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace)
            with mock.patch.object(
                validate_student_data.os,
                "read",
                side_effect=OSError("fictional read failure"),
            ):
                with self.assertRaisesRegex(
                    ValidationError, "profile.md.*fictional read failure"
                ):
                    validate_workspace(workspace)

    def test_rejects_symlinked_required_children_in_empty_workspace(self):
        for relative, is_directory in (
            ("profile.md", False),
            ("state.json", False),
            (".workspace.lock", False),
            ("sessions", True),
            ("plan-items", True),
            ("summaries", True),
            ("materials", True),
        ):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                workspace = root / "student-a"
                create_workspace(workspace)
                target = workspace / relative
                outside = root / ("outside-dir" if is_directory else "outside-file")
                if is_directory:
                    outside.mkdir()
                    target.rmdir()
                else:
                    outside.write_text("outside", encoding="utf-8")
                    target.unlink()
                try:
                    target.symlink_to(outside, target_is_directory=is_directory)
                except (NotImplementedError, OSError) as error:
                    self.skipTest(f"symlinks are unavailable: {error}")

                with self.assertRaisesRegex(
                    ValidationError, "symlink|regular|directory|invalid type"
                ):
                    validate_workspace(workspace)

    def test_rejects_state_not_derived_from_active_facts(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace)
            state_path = workspace / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["process"]["recorded_sessions"] = 9
            state_path.write_text(json.dumps(state), encoding="utf-8")

            with self.assertRaisesRegex(
                ValidationError, "derived|reconcile|recorded_sessions|process"
            ):
                validate_workspace(workspace)

    def test_rejects_symlinked_session_fact(self):
        session = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "student-a"
            create_workspace(workspace)
            outside = root / "outside.json"
            outside.write_text(json.dumps(session), encoding="utf-8")
            link = workspace / "sessions/record-session-001.json"
            try:
                link.symlink_to(outside)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")

            with self.assertRaisesRegex(ValidationError, "invalid type|symlink"):
                validate_workspace(workspace)

    def test_rejects_non_utf8_session_fact(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace)
            (workspace / "sessions/record-session-001.json").write_bytes(b"\xff\xfe")

            with self.assertRaisesRegex(ValidationError, "UTF-8"):
                validate_workspace(workspace)

    def test_rejects_plan_record_in_sessions_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace)
            path = workspace / "sessions/record-plan-001.json"
            path.write_text(json.dumps(plan_fact()), encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "record_type"):
                validate_workspace(workspace)

    def test_rejects_state_evidence_not_present_in_active_facts(self):
        session = session_fact(observations=[knowledge_observation()])
        state = state_from_facts(sessions=[session])
        state = copy.deepcopy(state)
        target = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        target["evidence_ids"].append("evidence-missing")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace, sessions=[session], state=state)

            with self.assertRaisesRegex(ValidationError, "derived|evidence|subjects"):
                validate_workspace(workspace)

    def test_rejects_non_json_entry_in_fact_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            create_workspace(workspace)
            (workspace / "sessions/note.txt").write_text("not a fact", encoding="utf-8")

            with self.assertRaisesRegex(ValidationError, "JSON|json|entry"):
                validate_workspace(workspace)

    def test_cli_reports_invalid_workspace_without_traceback(self):
        mutations = (
            "counter",
            "non-utf8-session",
            "required-child-symlink",
            "session-fact-symlink",
            "wrong-record-type",
            "missing-evidence",
            "non-json-entry",
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                workspace = root / "student-a"
                create_workspace(workspace)
                if mutation == "counter":
                    state_path = workspace / "state.json"
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    state["process"]["recorded_sessions"] = 1
                    state_path.write_text(json.dumps(state), encoding="utf-8")
                elif mutation == "non-utf8-session":
                    (workspace / "sessions/bad.json").write_bytes(b"\xff\xfe")
                elif mutation == "required-child-symlink":
                    target = workspace / "summaries"
                    target.rmdir()
                    outside = root / "outside-summaries"
                    outside.mkdir()
                    try:
                        target.symlink_to(outside, target_is_directory=True)
                    except (NotImplementedError, OSError) as error:
                        self.skipTest(f"symlinks are unavailable: {error}")
                elif mutation == "session-fact-symlink":
                    outside = root / "outside-session.json"
                    outside.write_text(
                        json.dumps(session_fact()),
                        encoding="utf-8",
                    )
                    try:
                        (workspace / "sessions/record-session-001.json").symlink_to(
                            outside
                        )
                    except (NotImplementedError, OSError) as error:
                        self.skipTest(f"symlinks are unavailable: {error}")
                elif mutation == "wrong-record-type":
                    (workspace / "sessions/record-plan-001.json").write_text(
                        json.dumps(plan_fact()),
                        encoding="utf-8",
                    )
                elif mutation == "missing-evidence":
                    session = session_fact(observations=[knowledge_observation()])
                    (workspace / "sessions/record-session-001.json").write_text(
                        json.dumps(session),
                        encoding="utf-8",
                    )
                    state = state_from_facts(sessions=[session])
                    target = state["subjects"]["mathematics"][
                        "knowledge_units"
                    ]["mathematics.geometry.dihedral-angle"]
                    target["evidence_ids"].append("evidence-missing")
                    (workspace / "state.json").write_text(
                        json.dumps(state),
                        encoding="utf-8",
                    )
                else:
                    (workspace / "sessions/note.txt").write_text(
                        "not a fact",
                        encoding="utf-8",
                    )

                self.assert_cli_invalid(workspace)


if __name__ == "__main__":
    unittest.main()
