import copy
from pathlib import Path
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

from validate_student_data import ValidationError, validate_state


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


class ValidateStudentDataTest(unittest.TestCase):
    def test_accepts_initial_state(self):
        validate_state(valid_state())

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


if __name__ == "__main__":
    unittest.main()
