import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from commit_learning_state import commit_fact  # noqa: E402
from summarize_progress import render  # noqa: E402
from tests.workspace_fixtures import interaction_observation, session_fact  # noqa: E402


class InteractionObservationE2ETest(unittest.TestCase):
    def test_observation_memory_survives_independent_cli_sessions_without_raw_content(self):
        """A second process finds only structured observations in the shared workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private-workspaces"
            phase_one = Path(tmp) / "phase-one"
            phase_two = Path(tmp) / "phase-two"
            phase_one.mkdir()
            phase_two.mkdir()
            environment = os.environ.copy()
            environment["SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT"] = str(root)

            initialized = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_student.py"),
                    "--ensure",
                    "student-cross-session",
                ],
                cwd=phase_one,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            workspace = root / "student-cross-session"
            state_before = (workspace / "state.json").read_bytes()

            raw_question = "the original question must not persist"
            raw_answer = "the original answer must not persist"
            unsafe_fact = interaction_observation(
                record_id="unsafe-cross-session-observation",
                interaction_id="unsafe-cross-session-interaction",
                occurred_at="2026-08-06T09:00:00+00:00",
            )
            unsafe_fact["original_question"] = raw_question
            unsafe_fact["original_answer"] = raw_answer
            unsafe_fact_file = phase_one / "unsafe-observation.json"
            unsafe_fact_file.write_text(
                json.dumps(unsafe_fact, ensure_ascii=False),
                encoding="utf-8",
            )
            unsafe_commit = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "commit_learning_state.py"),
                    str(workspace),
                    "--fact-file",
                    str(unsafe_fact_file),
                    "--student-id",
                    "student-cross-session",
                ],
                cwd=phase_one,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(0, unsafe_commit.returncode)
            self.assertFalse(
                (workspace / "observations" / "unsafe-cross-session-observation.json").exists()
            )
            self.assertEqual(state_before, (workspace / "state.json").read_bytes())

            first_fact = phase_one / "observation.json"
            first_fact.write_text(
                json.dumps(
                    interaction_observation(
                        record_id="cross-session-observation-001",
                        interaction_id="cross-session-interaction-001",
                        occurred_at="2026-08-06T10:00:00+00:00",
                    ),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            first_commit = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "commit_learning_state.py"),
                    str(workspace),
                    "--fact-file",
                    str(first_fact),
                    "--student-id",
                    "student-cross-session",
                ],
                cwd=phase_one,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, first_commit.returncode, first_commit.stderr)
            self.assertEqual(state_before, (workspace / "state.json").read_bytes())
            first_summary = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "summarize_progress.py"),
                    str(workspace),
                    "--student-id",
                    "student-cross-session",
                ],
                cwd=phase_one,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, first_summary.returncode, first_summary.stderr)
            self.assertIn("- 无待验证观察", first_summary.stdout)
            shutil.rmtree(phase_one)

            ensured_again = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_student.py"),
                    "--ensure",
                    "student-cross-session",
                ],
                cwd=phase_two,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, ensured_again.returncode, ensured_again.stderr)
            self.assertEqual(state_before, (workspace / "state.json").read_bytes())

            second_fact = phase_two / "observation.json"
            second_fact.write_text(
                json.dumps(
                    interaction_observation(
                        record_id="cross-session-observation-002",
                        interaction_id="cross-session-interaction-002",
                        occurred_at="2026-08-07T10:00:00+00:00",
                    ),
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            second_commit = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "commit_learning_state.py"),
                    str(workspace),
                    "--fact-file",
                    str(second_fact),
                    "--student-id",
                    "student-cross-session",
                ],
                cwd=phase_two,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, second_commit.returncode, second_commit.stderr)
            self.assertEqual(state_before, (workspace / "state.json").read_bytes())
            second_summary = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "summarize_progress.py"),
                    str(workspace),
                    "--student-id",
                    "student-cross-session",
                ],
                cwd=phase_two,
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, second_summary.returncode, second_summary.stderr)
            self.assertIn("出现 2 次", second_summary.stdout)

            persisted = b"".join(
                path.read_bytes()
                for path in workspace.rglob("*")
                if path.is_file() and path.name != ".workspace.lock"
            )
            self.assertNotIn(raw_question.encode("utf-8"), persisted)
            self.assertNotIn(raw_answer.encode("utf-8"), persisted)

    def test_observations_escalate_then_validation_updates_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "init_student.py"), "--root", str(root), "student-a"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, result.stderr)
            workspace = root / "student-a"
            state_before = (workspace / "state.json").read_bytes()

            first = interaction_observation(
                record_id="observation-001",
                interaction_id="interaction-001",
                occurred_at="2026-08-06T10:00:00+00:00",
            )
            second = interaction_observation(
                record_id="observation-002",
                interaction_id="interaction-002",
                occurred_at="2026-08-07T10:00:00+00:00",
            )
            self.assertTrue(commit_fact(workspace, first, now="2026-08-06T12:00:00+00:00"))
            self.assertTrue(commit_fact(workspace, second, now="2026-08-07T12:00:00+00:00"))
            self.assertEqual(state_before, (workspace / "state.json").read_bytes())

            summary = render(workspace, now="2026-08-07T12:00:00+00:00")
            self.assertIn("## 待验证观察", summary)
            self.assertIn("出现 2 次", summary)
            self.assertIn("cannot identify the relevant angle", summary)

            validation = session_fact(
                record_id="record-session-validation",
                session_id="session-validation",
                completed_at="2026-08-08T10:00:00+00:00",
                observations=[
                    {
                        "evidence_id": "evidence-validation",
                        "target_kind": "knowledge_unit",
                        "module_id": "geometry",
                        "target_id": "mathematics.geometry.dihedral-angle",
                        "target_name": "二面角的平面角",
                        "aliases": [],
                        "evidence_type": "diagnostic",
                        "outcome": "incorrect",
                        "hint_level": "none",
                        "student_response": "fictional validation response",
                        "first_substantive_error": "fictional validation error",
                        "student_explanation": None,
                        "next_review_at": None,
                        "uncertainty": "needs another independent check",
                        "resolves_observation_signal_kinds": ["content_gap"],
                    }
                ],
            )
            self.assertTrue(commit_fact(workspace, validation, now="2026-08-08T12:00:00+00:00"))
            state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
            unit = state["subjects"]["mathematics"]["knowledge_units"][
                "mathematics.geometry.dihedral-angle"
            ]
            self.assertEqual("suspected_gap", unit["status"])
            self.assertEqual(["evidence-validation"], unit["evidence_ids"])
            self.assertEqual(1, state["process"]["recorded_sessions"])
            summary = render(workspace, now="2026-08-08T12:00:00+00:00")
            self.assertIn("- 无未解决单次弱线索", summary)
            self.assertIn("- 无待验证观察", summary)


if __name__ == "__main__":
    unittest.main()
