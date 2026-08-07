from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from learning_state import (  # noqa: E402
    ValidationError,
    validate_fact,
    validate_plan_fact,
    validate_session_fact,
)
from tests.workspace_fixtures import (  # noqa: E402
    knowledge_observation,
    plan_fact,
    session_fact,
)


class FactSchemaTest(unittest.TestCase):
    def test_completed_session_may_record_direct_explanation_without_evidence(self):
        validate_session_fact(session_fact(student_attempt=None, observations=[]))

    def test_observation_requires_nonempty_student_response(self):
        fact = session_fact(
            observations=[knowledge_observation(student_response="")]
        )
        with self.assertRaisesRegex(ValidationError, "student_response"):
            validate_session_fact(fact)

    def test_transfer_requires_no_hint_and_student_explanation(self):
        fact = session_fact(
            observations=[
                knowledge_observation(
                    evidence_type="transfer",
                    outcome="correct",
                    hint_level="principle",
                    first_substantive_error=None,
                    student_explanation=None,
                )
            ]
        )
        with self.assertRaisesRegex(ValidationError, "transfer"):
            validate_session_fact(fact)

    def test_record_and_stable_ids_reject_path_characters(self):
        with self.assertRaisesRegex(ValidationError, "record_id"):
            validate_session_fact(session_fact(record_id="../escape"))

    def test_pending_and_completed_plan_facts_are_valid(self):
        validate_plan_fact(plan_fact())
        validate_fact(
            plan_fact(
                status="completed",
                completion_evidence_id="evidence-001",
            )
        )

    def test_completed_plan_requires_completion_evidence(self):
        with self.assertRaisesRegex(ValidationError, "completion_evidence_id"):
            validate_plan_fact(plan_fact(status="completed"))

    def test_pending_plan_rejects_completion_evidence(self):
        with self.assertRaisesRegex(ValidationError, "pending"):
            validate_plan_fact(plan_fact(completion_evidence_id="evidence-001"))

    def test_validate_fact_rejects_unknown_record_type(self):
        with self.assertRaisesRegex(ValidationError, "record_type"):
            validate_fact({"record_type": "unknown"})


if __name__ == "__main__":
    unittest.main()
