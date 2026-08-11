import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
INIT = SCRIPTS / "init_student.py"
COMMIT = SCRIPTS / "commit_learning_state.py"
sys.path.insert(0, str(SCRIPTS))

import commit_learning_state  # noqa: E402
from commit_learning_state import commit_fact  # noqa: E402
from validate_student_data import ValidationError, validate_workspace  # noqa: E402
from tests.workspace_fixtures import (  # noqa: E402
    knowledge_observation,
    plan_fact,
    session_fact,
)


NOW = "2026-08-06T12:00:00+00:00"
LATER = "2026-08-06T13:00:00+00:00"


class CommitLearningStateTest(unittest.TestCase):
    def initialize_workspace(self, root):
        result = subprocess.run(
            [sys.executable, str(INIT), "--root", str(root), "student-a"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return root / "student-a"

    def run_cli(self, workspace, fact):
        record_id = fact.get("record_id", "invalid-fact")
        fact_file = workspace.parent / (record_id + "-input.json")
        fact_file.write_text(json.dumps(fact, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(COMMIT),
                str(workspace),
                "--fact-file",
                str(fact_file),
            ],
            capture_output=True,
            text=True,
        )

    def test_session_commit_publishes_fact_and_reconciles_state(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))

            published = commit_fact(workspace, fact, now=NOW)
            snapshot = validate_workspace(workspace)

            self.assertTrue(published)
            self.assertTrue(
                (workspace / "sessions/record-session-001.json").is_file()
            )
            self.assertEqual(1, snapshot.state["process"]["recorded_sessions"])
            unit = snapshot.state["subjects"]["mathematics"]["knowledge_units"][
                "mathematics.geometry.dihedral-angle"
            ]
            self.assertEqual("confirmed_gap", unit["status"])

    def test_completed_plan_revision_requires_and_counts_matching_evidence(self):
        session = session_fact(observations=[knowledge_observation()])
        pending = plan_fact()
        completed = plan_fact(
            record_id="record-plan-002",
            supersedes_record_id="record-plan-001",
            status="completed",
            completion_evidence_id="evidence-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))

            commit_fact(workspace, session, now=NOW)
            commit_fact(workspace, pending, now=NOW)
            commit_fact(workspace, completed, now=NOW)
            snapshot = validate_workspace(workspace)

            self.assertEqual(1, snapshot.state["process"]["completed_plan_items"])
            self.assertEqual(
                {"record-plan-001.json", "record-plan-002.json"},
                {path.name for path in (workspace / "plan-items").iterdir()},
            )

    def test_identical_record_retry_is_noop(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            first = self.run_cli(workspace, fact)
            self.assertEqual(0, first.returncode, first.stderr)
            before = validate_workspace(workspace).state["updated_at"]

            second = self.run_cli(workspace, fact)
            after = validate_workspace(workspace).state["updated_at"]

            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual("COMMITTED: record-session-001\n", first.stdout)
            self.assertEqual("NO-OP: record-session-001\n", second.stdout)
            self.assertEqual(before, after)
            self.assertEqual(
                ["record-session-001.json"],
                sorted(path.name for path in (workspace / "sessions").iterdir()),
            )

    def test_conflicting_record_reuse_is_rejected(self):
        original = session_fact(observations=[knowledge_observation()])
        conflicting = session_fact(
            student_attempt="different fictional attempt",
            observations=[knowledge_observation()],
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, original, now=NOW)
            fact_path = workspace / "sessions/record-session-001.json"
            original_bytes = fact_path.read_bytes()
            state_bytes = (workspace / "state.json").read_bytes()

            with self.assertRaisesRegex(ValidationError, "record_id|conflict"):
                commit_fact(workspace, conflicting, now=LATER)

            self.assertEqual(original_bytes, fact_path.read_bytes())
            self.assertEqual(state_bytes, (workspace / "state.json").read_bytes())

    def test_interrupted_fact_write_never_exposes_final_name(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            fact_directory = workspace / "sessions"
            final_path = fact_directory / "record-session-001.json"
            temporary_names = []

            def interrupt_fact_write(file_fd, data):
                self.assertFalse(final_path.exists())
                names = [path.name for path in fact_directory.iterdir()]
                self.assertEqual(1, len(names))
                self.assertRegex(
                    names[0],
                    r"^\.record-session-001-[0-9a-f]{32}\.tmp$",
                )
                temporary_names.extend(names)
                raise OSError("fictional interrupted fact write")

            with mock.patch.object(
                commit_learning_state,
                "_write_all",
                side_effect=interrupt_fact_write,
            ):
                with self.assertRaisesRegex(OSError, "interrupted fact write"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertFalse(final_path.exists())
            self.assertTrue(temporary_names)
            self.assertEqual(
                [],
                [
                    name
                    for name in temporary_names
                    if (fact_directory / name).exists()
                ],
            )

    def test_cross_type_record_id_conflict_preserves_workspace(self):
        session = session_fact(observations=[knowledge_observation()])
        plan = plan_fact(record_id=session["record_id"])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, session, now=NOW)
            plan_directory = workspace / "plan-items"
            plan_before = {
                path.name: path.read_bytes() for path in plan_directory.iterdir()
            }
            state_before = (workspace / "state.json").read_bytes()

            with self.assertRaisesRegex(ValidationError, "duplicate record_id"):
                commit_fact(workspace, plan, now=LATER)

            self.assertEqual(
                plan_before,
                {path.name: path.read_bytes() for path in plan_directory.iterdir()},
            )
            self.assertEqual(
                state_before,
                (workspace / "state.json").read_bytes(),
            )
            validate_workspace(workspace)

    def test_state_replace_failure_is_recoverable(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            old_state = (workspace / "state.json").read_bytes()

            with mock.patch.object(
                commit_learning_state.os,
                "replace",
                side_effect=OSError("fictional pre-replace failure"),
            ):
                with self.assertRaisesRegex(OSError, "pre-replace"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertTrue(
                (workspace / "sessions/record-session-001.json").is_file()
            )
            self.assertEqual(old_state, (workspace / "state.json").read_bytes())
            self.assertEqual(
                [],
                [path.name for path in workspace.iterdir() if path.name.endswith(".tmp")],
            )

            published = commit_fact(workspace, fact, now=LATER)
            snapshot = validate_workspace(workspace)

            self.assertFalse(published)
            self.assertEqual(1, snapshot.state["process"]["recorded_sessions"])
            self.assertEqual(LATER, snapshot.state["updated_at"])

    def test_state_write_failure_cleans_owned_temporary_file(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            old_state = (workspace / "state.json").read_bytes()
            real_write_all = commit_learning_state._write_all
            calls = 0

            def fail_state_write(file_fd, data):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("fictional state write failure")
                return real_write_all(file_fd, data)

            with mock.patch.object(
                commit_learning_state,
                "_write_all",
                side_effect=fail_state_write,
            ):
                with self.assertRaisesRegex(OSError, "state write"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertEqual(old_state, (workspace / "state.json").read_bytes())
            self.assertEqual(
                [],
                [path.name for path in workspace.iterdir() if path.name.endswith(".tmp")],
            )

    def test_two_concurrent_session_commits_preserve_both_facts(self):
        first = session_fact(
            record_id="record-session-001",
            session_id="session-001",
            observations=[knowledge_observation(evidence_id="evidence-001")],
        )
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:01:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    target_id="mathematics.geometry.line-plane-perpendicular",
                    target_name="线面垂直",
                )
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            inputs = []
            for fact in (first, second):
                path = Path(tmp) / (fact["record_id"] + "-input.json")
                path.write_text(json.dumps(fact, ensure_ascii=False), encoding="utf-8")
                inputs.append(path)

            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(COMMIT),
                        str(workspace),
                        "--fact-file",
                        str(path),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for path in inputs
            ]
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=10)
                results.append((process.returncode, stdout, stderr))

            self.assertEqual([0, 0], sorted(result[0] for result in results), results)
            snapshot = validate_workspace(workspace)
            self.assertEqual(2, snapshot.state["process"]["recorded_sessions"])
            self.assertEqual(
                {"record-session-001.json", "record-session-002.json"},
                {path.name for path in (workspace / "sessions").iterdir()},
            )

    def test_cli_rejects_invalid_fact_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            result = self.run_cli(workspace, {"record_type": "session"})

            self.assertEqual(1, result.returncode)
            self.assertTrue(result.stderr.startswith("ERROR:"), result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
