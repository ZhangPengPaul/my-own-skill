import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPTS_DIR = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "shanghai-high-school-study-coach"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS_DIR))
VALIDATOR_SCRIPT = SCRIPTS_DIR / "validate_student_data.py"

from validate_student_data import ValidationError, validate_state, validate_workspace


SUBJECTS = {
    "chinese": "high-stakes",
    "mathematics": "high-stakes",
    "english": "high-stakes",
    "politics": "high-stakes",
    "history": "high-stakes",
    "geography": "high-stakes",
    "physics": "qualification",
    "chemistry": "qualification",
    "biology": "qualification",
}


def valid_state():
    subjects = {}
    for subject, goal_type in SUBJECTS.items():
        data = {
            "goal_type": goal_type,
            "assessments": [],
            "knowledge_units": {},
        }
        if goal_type == "qualification":
            data["qualification_risk"] = "unassessed"
        subjects[subject] = data

    return {
        "schema_version": 1,
        "student_id": "student-a",
        "updated_at": None,
        "subjects": subjects,
        "process": {
            "completed_plan_items": 0,
            "recorded_sessions": 0,
        },
    }


def state_with_evidence(evidence_path):
    state = valid_state()
    state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
        "status": "developing",
        "evidence": [evidence_path],
        "last_reviewed_at": "2026-08-06",
        "next_review_at": "2026-08-13",
    }
    return state


def write_complete_workspace(workspace, state, create_sessions=True):
    (workspace / "profile.md").touch()
    (workspace / "plans").mkdir()
    (workspace / "plans" / "current.md").touch()
    for directory in ("mistakes", "materials"):
        (workspace / directory).mkdir()
    if create_sessions:
        (workspace / "sessions").mkdir()
    (workspace / "state.json").write_text(json.dumps(state), encoding="utf-8")


class ValidateStudentDataTest(unittest.TestCase):
    def test_accepts_initial_state(self):
        validate_state(valid_state())

    def test_validate_workspace_returns_validated_state(self):
        state = valid_state()
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_complete_workspace(workspace, state)

            validated_state = validate_workspace(workspace)

        self.assertEqual(state, validated_state)

    def test_rejects_unknown_schema_version(self):
        state = valid_state()
        state["schema_version"] = 2

        with self.assertRaisesRegex(ValidationError, "schema_version"):
            validate_state(state)

    def test_rejects_missing_subject(self):
        state = valid_state()
        del state["subjects"]["geography"]

        with self.assertRaisesRegex(ValidationError, "subjects"):
            validate_state(state)

    def test_requires_evidence_for_mastery(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "stable",
            "evidence": [],
            "last_reviewed_at": None,
            "next_review_at": None,
        }

        with self.assertRaisesRegex(ValidationError, "evidence"):
            validate_state(state)

    def test_accepts_existing_session_evidence(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "developing",
            "evidence": ["sessions/2026-08-06-mathematics-s1.md"],
            "last_reviewed_at": "2026-08-06",
            "next_review_at": "2026-08-13",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "sessions").mkdir()
            (workspace / "sessions" / "2026-08-06-mathematics-s1.md").touch()

            validate_state(state, workspace)

    def test_rejects_nonexistent_evidence_path(self):
        state = copy.deepcopy(valid_state())
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "developing",
            "evidence": ["sessions/missing.md"],
            "last_reviewed_at": "2026-08-06",
            "next_review_at": "2026-08-13",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "sessions").mkdir()

            with self.assertRaisesRegex(ValidationError, "missing"):
                validate_state(state, workspace)

    def test_rejects_qualification_risk_on_high_stakes_subject(self):
        state = valid_state()
        state["subjects"]["english"]["qualification_risk"] = "low"

        with self.assertRaisesRegex(ValidationError, "qualification_risk"):
            validate_state(state)

    def test_rejects_traversal_evidence_even_when_target_exists(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "developing",
            "evidence": ["sessions/../../outside.md"],
            "last_reviewed_at": "2026-08-06",
            "next_review_at": "2026-08-13",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            (workspace / "sessions").mkdir(parents=True)
            (root / "outside.md").touch()

            with self.assertRaisesRegex(
                ValidationError, "evidence|path|sessions|outside"
            ):
                validate_state(state, workspace)

    def test_rejects_evidence_symlink_that_escapes_sessions(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "developing",
            "evidence": ["sessions/escape.md"],
            "last_reviewed_at": "2026-08-06",
            "next_review_at": "2026-08-13",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            sessions = workspace / "sessions"
            sessions.mkdir(parents=True)
            outside = root / "outside.md"
            outside.touch()
            try:
                (sessions / "escape.md").symlink_to(outside)
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")

            with self.assertRaisesRegex(
                ValidationError, "evidence|path|sessions|outside"
            ):
                validate_state(state, workspace)

    def test_rejects_absolute_evidence_without_workspace(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "developing",
            "evidence": ["/tmp/outside.md"],
            "last_reviewed_at": "2026-08-06",
            "next_review_at": "2026-08-13",
        }

        with self.assertRaisesRegex(ValidationError, "evidence|path|sessions"):
            validate_state(state)

    def test_rejects_non_string_mastery_status_with_validation_error(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": {"level": "developing"},
            "evidence": [],
            "last_reviewed_at": None,
            "next_review_at": None,
        }

        with self.assertRaisesRegex(ValidationError, "status"):
            validate_state(state)

    def test_rejects_non_string_qualification_risk_with_validation_error(self):
        state = valid_state()
        state["subjects"]["physics"]["qualification_risk"] = ["low"]

        with self.assertRaisesRegex(ValidationError, "qualification_risk"):
            validate_state(state)

    def test_rejects_boolean_schema_version(self):
        state = valid_state()
        state["schema_version"] = True

        with self.assertRaisesRegex(ValidationError, "schema_version"):
            validate_state(state)

    def test_cli_reports_non_utf8_state_as_validation_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            (workspace / "profile.md").touch()
            (workspace / "plans").mkdir()
            (workspace / "plans" / "current.md").touch()
            for directory in ("mistakes", "sessions", "materials"):
                (workspace / directory).mkdir()
            (workspace / "state.json").write_bytes(b"\xff\xfe")

            result = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(workspace)],
                capture_output=True,
                text=True,
            )

        self.assertEqual(1, result.returncode)
        self.assertTrue(
            result.stderr.startswith("INVALID:"),
            f"unexpected stderr: {result.stderr!r}",
        )
        self.assertNotIn("Traceback", result.stderr)

    def test_rejects_sessions_directory_symlink_outside_workspace(self):
        state = state_with_evidence("sessions/evidence.md")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            external_sessions = root / "external-sessions"
            external_sessions.mkdir()
            (external_sessions / "evidence.md").touch()
            try:
                (workspace / "sessions").symlink_to(
                    external_sessions, target_is_directory=True
                )
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")

            with self.assertRaisesRegex(
                ValidationError, "evidence|path|sessions|outside"
            ):
                validate_state(state, workspace)

    def test_cli_rejects_sessions_directory_symlink_without_traceback(self):
        state = state_with_evidence("sessions/evidence.md")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            external_sessions = root / "external-sessions"
            external_sessions.mkdir()
            (external_sessions / "evidence.md").touch()
            try:
                (workspace / "sessions").symlink_to(
                    external_sessions, target_is_directory=True
                )
            except (NotImplementedError, OSError) as error:
                self.skipTest(f"symlinks are unavailable: {error}")
            write_complete_workspace(workspace, state, create_sessions=False)

            result = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(workspace)],
                capture_output=True,
                text=True,
            )

        self.assertEqual(1, result.returncode)
        self.assertTrue(
            result.stderr.startswith("INVALID:"),
            f"unexpected stderr: {result.stderr!r}",
        )
        self.assertNotIn("Traceback", result.stderr)

    def test_rejects_nul_in_evidence_path_with_validation_error(self):
        state = state_with_evidence("sessions/\x00bad.md")

        with self.assertRaisesRegex(ValidationError, "evidence|path"):
            validate_state(state)

    def test_cli_rejects_nul_evidence_path_without_traceback(self):
        state = state_with_evidence("sessions/\x00bad.md")

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            write_complete_workspace(workspace, state)

            result = subprocess.run(
                [sys.executable, str(VALIDATOR_SCRIPT), str(workspace)],
                capture_output=True,
                text=True,
            )

        self.assertEqual(1, result.returncode)
        self.assertTrue(
            result.stderr.startswith("INVALID:"),
            f"unexpected stderr: {result.stderr!r}",
        )
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
