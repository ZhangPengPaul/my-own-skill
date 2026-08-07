from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from learning_state import (  # noqa: E402
    ValidationError,
    reconcile_state,
    validate_fact,
    validate_plan_fact,
    validate_session_fact,
)
from tests.workspace_fixtures import (  # noqa: E402
    knowledge_observation,
    pattern_observation,
    plan_fact,
    session_fact,
)


NOW = "2026-08-06T12:00:00+00:00"


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


class ReconciliationTest(unittest.TestCase):
    def test_single_initial_error_is_only_suspected(self):
        fact = session_fact(
            observations=[
                knowledge_observation(
                    evidence_type="initial_attempt",
                    outcome="incorrect",
                )
            ]
        )

        state = reconcile_state("student-a", [fact], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("suspected_gap", unit["status"])

    def test_diagnostic_error_confirms_gap_and_variant_does_not_skip_hint_rule(self):
        first = session_fact(observations=[knowledge_observation()])
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="principle",
                    first_substantive_error=None,
                )
            ],
        )

        state = reconcile_state("student-a", [first, second], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("strengthening", unit["status"])

    def test_delayed_no_hint_success_is_stable(self):
        fact = session_fact(
            observations=[
                knowledge_observation(
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )

        state = reconcile_state("student-a", [fact], [], now=NOW)

        self.assertEqual(
            "stable",
            state["subjects"]["mathematics"]["knowledge_units"][
                "mathematics.geometry.dihedral-angle"
            ]["status"],
        )

    def test_plan_completion_requires_matching_active_evidence(self):
        session = session_fact(
            observations=[
                knowledge_observation(
                    outcome="correct",
                    evidence_type="variant",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )
        plan = plan_fact(
            status="completed",
            completion_evidence_id="evidence-001",
        )

        state = reconcile_state("student-a", [session], [plan], now=NOW)

        self.assertEqual(1, state["process"]["completed_plan_items"])

    def test_mismatched_plan_completion_evidence_is_not_counted(self):
        session = session_fact(
            observations=[
                knowledge_observation(
                    outcome="correct",
                    evidence_type="variant",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )
        for mismatch in (
            {"subject": "english", "target_id": "english.reading.inference"},
            {"target_kind": "pattern"},
            {"target_id": "mathematics.geometry.line-plane-perpendicular"},
        ):
            with self.subTest(mismatch=mismatch):
                plan = plan_fact(
                    status="completed",
                    completion_evidence_id="evidence-001",
                    **mismatch,
                )
                state = reconcile_state("student-a", [session], [plan], now=NOW)
                self.assertEqual(0, state["process"]["completed_plan_items"])

    def test_revision_chain_rejects_fork(self):
        root = session_fact(status="incomplete")
        left = session_fact(
            record_id="record-left",
            supersedes_record_id=root["record_id"],
        )
        right = session_fact(
            record_id="record-right",
            supersedes_record_id=root["record_id"],
        )

        with self.assertRaisesRegex(ValidationError, "fork"):
            reconcile_state("student-a", [root, left, right], [], now=NOW)

    def test_duplicate_record_id_is_rejected(self):
        first = session_fact()
        second = session_fact(session_id="session-002")

        with self.assertRaisesRegex(ValidationError, "duplicate record_id"):
            reconcile_state("student-a", [first, second], [], now=NOW)

    def test_revision_cycle_is_rejected(self):
        first = session_fact(
            record_id="record-first",
            supersedes_record_id="record-second",
        )
        second = session_fact(
            record_id="record-second",
            supersedes_record_id="record-first",
        )

        with self.assertRaisesRegex(ValidationError, "cycle"):
            reconcile_state("student-a", [first, second], [], now=NOW)

    def test_revision_cannot_change_session_id(self):
        root = session_fact(status="incomplete")
        child = session_fact(
            record_id="record-child",
            session_id="session-002",
            supersedes_record_id=root["record_id"],
        )

        with self.assertRaisesRegex(ValidationError, "stable id"):
            reconcile_state("student-a", [root, child], [], now=NOW)

    def test_duplicate_active_evidence_id_is_rejected(self):
        first = session_fact(observations=[knowledge_observation()])
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[knowledge_observation()],
        )

        with self.assertRaisesRegex(ValidationError, "evidence_id"):
            reconcile_state("student-a", [first, second], [], now=NOW)

    def test_pattern_progresses_from_once_to_recurring_to_controlled(self):
        first = session_fact(observations=[pattern_observation()])
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[pattern_observation(evidence_id="evidence-002")],
        )
        third = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                pattern_observation(
                    evidence_id="evidence-003",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        target_id = "mathematics.pattern.method-selection"

        states = []
        for facts in ([first], [first, second], [first, second, third]):
            state = reconcile_state("student-a", facts, [], now=NOW)
            states.append(
                state["subjects"]["mathematics"]["patterns"][target_id][
                    "status"
                ]
            )

        self.assertEqual(["observed_once", "recurring", "controlled"], states)

    def test_later_diagnostic_failure_lowers_stable_mastery(self):
        stable = session_fact(
            observations=[
                knowledge_observation(
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )
        failure = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-002")],
        )

        state = reconcile_state("student-a", [stable, failure], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("confirmed_gap", unit["status"])

    def test_incomplete_active_session_is_ignored(self):
        fact = session_fact(
            status="incomplete",
            completed_at=None,
            observations=[knowledge_observation()],
        )

        state = reconcile_state("student-a", [fact], [], now=NOW)

        self.assertEqual(0, state["process"]["recorded_sessions"])
        self.assertEqual({}, state["subjects"]["mathematics"]["knowledge_units"])

    def test_active_revision_replaces_completed_parent(self):
        parent = session_fact(observations=[knowledge_observation()])
        child = session_fact(
            record_id="record-session-002",
            supersedes_record_id=parent["record_id"],
            status="incomplete",
            completed_at=None,
            observations=[],
        )

        state = reconcile_state("student-a", [parent, child], [], now=NOW)

        self.assertEqual(0, state["process"]["recorded_sessions"])
        self.assertEqual({}, state["subjects"]["mathematics"]["knowledge_units"])

    def test_reconciliation_is_idempotent_and_preserves_updated_at(self):
        fact = session_fact(observations=[knowledge_observation()])
        first = reconcile_state("student-a", [fact], [], now=NOW)

        second = reconcile_state(
            "student-a",
            [fact],
            [],
            previous_state=first,
            now="2026-08-07T12:00:00+00:00",
        )

        self.assertEqual(first, second)
        self.assertEqual(NOW, second["updated_at"])


if __name__ == "__main__":
    unittest.main()
