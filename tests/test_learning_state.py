from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from learning_state import (  # noqa: E402
    SUBJECT_MODULES,
    ValidationError,
    parse_timestamp,
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
EXPECTED_SUBJECT_MODULES = {
    "chinese": {
        "language-and-accumulation",
        "classical-texts",
        "modern-reading",
        "writing",
        "integrated-expression",
    },
    "mathematics": {
        "sets-and-logic",
        "algebra-and-functions",
        "geometry",
        "probability-and-statistics",
        "modeling-and-applications",
    },
    "english": {
        "vocabulary-and-grammar",
        "reading",
        "translation",
        "writing",
        "integrated-language-use",
    },
    "politics": {
        "concepts-and-principles",
        "material-analysis",
        "reasoning-and-argument",
        "answer-organization",
    },
    "history": {
        "chronology-and-facts",
        "source-analysis",
        "causation-and-change",
        "comparison-and-evaluation",
        "historical-expression",
    },
    "geography": {
        "maps-and-space",
        "data-and-charts",
        "processes-and-mechanisms",
        "regional-analysis",
        "human-environment",
    },
}


class FactSchemaTest(unittest.TestCase):
    def test_runtime_subject_modules_match_reference_contract(self):
        self.assertEqual(EXPECTED_SUBJECT_MODULES, SUBJECT_MODULES)

    def test_completed_session_may_record_direct_explanation_without_evidence(self):
        validate_session_fact(session_fact(student_attempt=None, observations=[]))

    def test_zulu_timestamps_are_accepted_by_all_consumers(self):
        session = session_fact(
            completed_at="2026-08-06T10:00:00Z",
            observations=[
                knowledge_observation(
                    next_review_at="2026-08-13T10:00:00Z"
                )
            ],
        )

        validate_session_fact(session)
        validate_plan_fact(plan_fact(due_at="2026-08-13T10:00:00Z"))
        reconcile_state("student-a", [session], [], now="2026-08-06T12:00:00Z")

    def test_public_timestamp_parser_treats_z_and_offset_as_same_instant(self):
        self.assertEqual(
            parse_timestamp(
                "2026-08-06T12:00:00Z",
                "timestamp",
            ),
            parse_timestamp(
                "2026-08-06T13:00:00+01:00",
                "timestamp",
            ),
        )

    def test_timestamps_reject_date_only_and_naive_values(self):
        for value in ("2026-08-06", "2026-08-06T10:00:00"):
            with self.subTest(field="completed_at", value=value):
                with self.assertRaisesRegex(ValidationError, "completed_at"):
                    validate_session_fact(session_fact(completed_at=value))
            with self.subTest(field="next_review_at", value=value):
                fact = session_fact(
                    observations=[knowledge_observation(next_review_at=value)]
                )
                with self.assertRaisesRegex(ValidationError, "next_review_at"):
                    validate_session_fact(fact)
            with self.subTest(field="due_at", value=value):
                with self.assertRaisesRegex(ValidationError, "due_at"):
                    validate_plan_fact(plan_fact(due_at=value))
            with self.subTest(field="now", value=value):
                with self.assertRaisesRegex(ValidationError, "now"):
                    reconcile_state("student-a", [], [], now=value)

    def test_session_requires_valid_task_id(self):
        for task_id in ("", "../task"):
            with self.subTest(task_id=task_id):
                with self.assertRaisesRegex(ValidationError, "task_id"):
                    validate_session_fact(session_fact(task_id=task_id))

    def test_mode_transition_requires_exact_fields(self):
        for transition in (
            {"from_mode": "assessment", "to_mode": "practice"},
            {
                "from_mode": "assessment",
                "to_mode": "practice",
                "reason": "diagnosis completed",
                "unexpected": True,
            },
        ):
            with self.subTest(transition=transition):
                with self.assertRaisesRegex(ValidationError, "mode transition"):
                    validate_session_fact(
                        session_fact(mode_transitions=[transition])
                    )

    def test_mode_transition_requires_defined_distinct_modes(self):
        for transition in (
            {
                "from_mode": "unknown",
                "to_mode": "practice",
                "reason": "diagnosis completed",
            },
            {
                "from_mode": "assessment",
                "to_mode": "unknown",
                "reason": "diagnosis completed",
            },
            {
                "from_mode": "practice",
                "to_mode": "practice",
                "reason": "diagnosis completed",
            },
        ):
            with self.subTest(transition=transition):
                with self.assertRaisesRegex(ValidationError, "mode transition"):
                    validate_session_fact(
                        session_fact(mode_transitions=[transition])
                    )

    def test_mode_transition_requires_nonempty_reason(self):
        transition = {
            "from_mode": "assessment",
            "to_mode": "practice",
            "reason": "",
        }

        with self.assertRaisesRegex(ValidationError, "reason"):
            validate_session_fact(session_fact(mode_transitions=[transition]))

    def test_valid_mode_transition_is_accepted(self):
        validate_session_fact(
            session_fact(
                mode_transitions=[
                    {
                        "from_mode": "assessment",
                        "to_mode": "explanation",
                        "reason": "diagnosis completed",
                    },
                    {
                        "from_mode": "explanation",
                        "to_mode": "practice",
                        "reason": "guided explanation completed",
                    }
                ]
            )
        )

    def test_mode_transition_chain_must_be_contiguous(self):
        transitions = [
            {
                "from_mode": "assessment",
                "to_mode": "explanation",
                "reason": "diagnosis completed",
            },
            {
                "from_mode": "grading",
                "to_mode": "practice",
                "reason": "practice selected",
            },
        ]

        with self.assertRaisesRegex(ValidationError, "mode transition chain"):
            validate_session_fact(session_fact(mode_transitions=transitions))

    def test_last_mode_transition_must_match_task_mode(self):
        transition = {
            "from_mode": "assessment",
            "to_mode": "explanation",
            "reason": "diagnosis completed",
        }

        with self.assertRaisesRegex(ValidationError, "task_mode"):
            validate_session_fact(session_fact(mode_transitions=[transition]))

    def test_completed_session_observations_require_source_description(self):
        fact = session_fact(
            source_materials=[],
            observations=[knowledge_observation()],
        )

        with self.assertRaisesRegex(ValidationError, "source_materials"):
            validate_session_fact(fact)

    def test_completed_session_observations_require_student_attempt(self):
        for student_attempt in (None, ""):
            with self.subTest(student_attempt=student_attempt):
                fact = session_fact(
                    student_attempt=student_attempt,
                    observations=[knowledge_observation()],
                )
                with self.assertRaisesRegex(ValidationError, "student_attempt"):
                    validate_session_fact(fact)

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

    def test_optional_observation_strings_reject_empty_values(self):
        for field in ("student_explanation", "uncertainty"):
            with self.subTest(field=field):
                fact = session_fact(
                    observations=[knowledge_observation(**{field: ""})]
                )
                with self.assertRaisesRegex(ValidationError, field):
                    validate_session_fact(fact)

    def test_next_review_at_must_be_null_or_iso_timestamp(self):
        fact = session_fact(
            observations=[knowledge_observation(next_review_at="tomorrow")]
        )

        with self.assertRaisesRegex(ValidationError, "next_review_at"):
            validate_session_fact(fact)

    def test_observation_module_must_belong_to_session_subject(self):
        valid_modules = {
            "chinese": "modern-reading",
            "mathematics": "geometry",
            "english": "reading",
            "politics": "material-analysis",
            "history": "source-analysis",
            "geography": "maps-and-space",
        }
        for subject, module_id in valid_modules.items():
            observation = knowledge_observation(
                module_id=module_id,
                target_id=f"{subject}.{module_id}.target",
            )
            with self.subTest(subject=subject, module_id=module_id):
                validate_session_fact(
                    session_fact(subject=subject, observations=[observation])
                )

        fact = session_fact(
            observations=[knowledge_observation(module_id="reading")]
        )
        with self.assertRaisesRegex(ValidationError, "module_id"):
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
    def test_equal_instants_use_session_identity_tie_breakers(self):
        local = session_fact(
            record_id="record-local",
            session_id="session-001",
            completed_at="2026-08-06T10:00:00+08:00",
            observations=[knowledge_observation(evidence_id="evidence-local")],
        )
        utc = session_fact(
            record_id="record-utc",
            session_id="session-002",
            completed_at="2026-08-06T02:00:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-utc")],
        )

        state = reconcile_state("student-a", [utc, local], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual(
            ["evidence-local", "evidence-utc"],
            unit["evidence_ids"],
        )

    def test_completed_sessions_sort_by_absolute_instant(self):
        earlier = session_fact(
            record_id="record-earlier",
            session_id="session-002",
            completed_at="2026-08-06T10:00:00+08:00",
            observations=[knowledge_observation(evidence_id="evidence-earlier")],
        )
        later = session_fact(
            record_id="record-later",
            session_id="session-001",
            completed_at="2026-08-06T03:00:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-later")],
        )

        state = reconcile_state("student-a", [later, earlier], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual(
            ["evidence-earlier", "evidence-later"],
            unit["evidence_ids"],
        )

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

    def test_single_diagnostic_error_remains_suspected(self):
        fact = session_fact(observations=[knowledge_observation()])

        state = reconcile_state("student-a", [fact], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("suspected_gap", unit["status"])

    def test_first_error_after_unassessed_success_remains_suspected(self):
        success = session_fact(
            observations=[
                knowledge_observation(
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

        state = reconcile_state("student-a", [success, failure], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("suspected_gap", unit["status"])

    def test_second_matching_error_confirms_gap(self):
        first = session_fact(
            observations=[
                knowledge_observation(evidence_type="initial_attempt")
            ]
        )
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-002")],
        )

        state = reconcile_state("student-a", [first, second], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("confirmed_gap", unit["status"])

    def test_failed_mastery_check_after_prior_error_confirms_gap(self):
        first = session_fact(
            observations=[
                knowledge_observation(evidence_type="initial_attempt")
            ]
        )
        correction = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="correction",
                    outcome="correct",
                    hint_level="principle",
                    first_substantive_error=None,
                )
            ],
        )
        target_id = "mathematics.geometry.dihedral-angle"
        corrected = reconcile_state(
            "student-a", [first, correction], [], now=NOW
        )
        self.assertEqual(
            "strengthening",
            corrected["subjects"]["mathematics"]["knowledge_units"][
                target_id
            ]["status"],
        )

        for evidence_type in ("delayed_retest", "transfer"):
            with self.subTest(evidence_type=evidence_type):
                failed_check = session_fact(
                    record_id="record-session-003",
                    session_id="session-003",
                    completed_at="2026-08-06T10:20:00+00:00",
                    observations=[
                        knowledge_observation(
                            evidence_id="evidence-003",
                            evidence_type=evidence_type,
                        )
                    ],
                )
                state = reconcile_state(
                    "student-a",
                    [first, correction, failed_check],
                    [],
                    now=NOW,
                )
                unit = state["subjects"]["mathematics"]["knowledge_units"][
                    target_id
                ]
                self.assertEqual("confirmed_gap", unit["status"])

    def test_initial_or_diagnostic_success_does_not_claim_provisional_mastery(self):
        for evidence_type in ("initial_attempt", "diagnostic"):
            with self.subTest(evidence_type=evidence_type):
                fact = session_fact(
                    observations=[
                        knowledge_observation(
                            evidence_type=evidence_type,
                            outcome="correct",
                            hint_level="none",
                            first_substantive_error=None,
                        )
                    ]
                )
                state = reconcile_state("student-a", [fact], [], now=NOW)
                unit = state["subjects"]["mathematics"]["knowledge_units"][
                    "mathematics.geometry.dihedral-angle"
                ]
                self.assertEqual("unassessed", unit["status"])

    def test_successful_variant_requires_prior_gap_or_strengthening(self):
        variant = knowledge_observation(
            evidence_type="variant",
            outcome="correct",
            hint_level="none",
            first_substantive_error=None,
        )
        without_prior_gap = session_fact(observations=[variant])
        state = reconcile_state(
            "student-a", [without_prior_gap], [], now=NOW
        )
        target_id = "mathematics.geometry.dihedral-angle"
        self.assertEqual(
            "unassessed",
            state["subjects"]["mathematics"]["knowledge_units"][target_id][
                "status"
            ],
        )

        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        after_gap = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                dict(variant, evidence_id="evidence-002")
            ],
        )
        state = reconcile_state("student-a", [gap, after_gap], [], now=NOW)
        self.assertEqual(
            "provisionally_mastered",
            state["subjects"]["mathematics"]["knowledge_units"][target_id][
                "status"
            ],
        )

    def test_successful_variant_does_not_lower_stable(self):
        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        variant = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        delayed = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-003",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        later_variant = session_fact(
            record_id="record-session-004",
            session_id="session-004",
            completed_at="2026-08-06T10:30:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-004",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )

        state = reconcile_state(
            "student-a", [gap, variant, delayed, later_variant], [], now=NOW
        )

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("stable", unit["status"])

    def test_delayed_retest_requires_prior_provisional_mastery(self):
        delayed = session_fact(
            observations=[
                knowledge_observation(
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )

        state = reconcile_state("student-a", [delayed], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("unassessed", unit["status"])

    def test_hinted_delayed_retest_does_not_promote_provisional_mastery(self):
        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        variant = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        hinted_retest = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-003",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="principle",
                    first_substantive_error=None,
                )
            ],
        )

        state = reconcile_state(
            "student-a", [gap, variant, hinted_retest], [], now=NOW
        )

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("provisionally_mastered", unit["status"])

    def test_transfer_requires_prior_stable_state(self):
        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        variant = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        transfer = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-003",
                    evidence_type="transfer",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                    student_explanation="fictional explanation",
                )
            ],
        )

        state = reconcile_state(
            "student-a", [gap, variant, transfer], [], now=NOW
        )
        target_id = "mathematics.geometry.dihedral-angle"
        self.assertEqual(
            "provisionally_mastered",
            state["subjects"]["mathematics"]["knowledge_units"][target_id][
                "status"
            ],
        )

        delayed = session_fact(
            record_id="record-session-004",
            session_id="session-004",
            completed_at="2026-08-06T10:30:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-004",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        later_transfer = session_fact(
            record_id="record-session-005",
            session_id="session-005",
            completed_at="2026-08-06T10:40:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-005",
                    evidence_type="transfer",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                    student_explanation="fictional explanation",
                )
            ],
        )
        state = reconcile_state(
            "student-a",
            [gap, variant, delayed, later_transfer],
            [],
            now=NOW,
        )
        self.assertEqual(
            "transferable",
            state["subjects"]["mathematics"]["knowledge_units"][target_id][
                "status"
            ],
        )

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

    def test_completed_plan_rejects_missing_or_mismatched_evidence(self):
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
        invalid_plans = (
            {"completion_evidence_id": "evidence-missing"},
            {"subject": "english", "target_id": "english.reading.inference"},
            {"target_kind": "pattern"},
            {"target_id": "mathematics.geometry.line-plane-perpendicular"},
        )
        for overrides in invalid_plans:
            with self.subTest(overrides=overrides):
                plan = plan_fact(
                    **{
                        "status": "completed",
                        "completion_evidence_id": "evidence-001",
                        **overrides,
                    }
                )
                with self.assertRaisesRegex(
                    ValidationError, "completion evidence"
                ):
                    reconcile_state("student-a", [session], [plan], now=NOW)

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

    def test_cross_type_record_id_is_rejected(self):
        session = session_fact()
        plan = plan_fact(record_id=session["record_id"])

        with self.assertRaisesRegex(ValidationError, "duplicate record_id"):
            reconcile_state("student-a", [session], [plan], now=NOW)

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

    def test_duplicate_session_id_across_unrelated_roots_is_rejected(self):
        first = session_fact(record_id="record-first")
        second = session_fact(record_id="record-second")

        with self.assertRaisesRegex(ValidationError, "session-001"):
            reconcile_state("student-a", [first, second], [], now=NOW)

    def test_target_kind_name_and_module_are_globally_stable(self):
        first = session_fact(observations=[knowledge_observation()])
        changes = (
            {"target_kind": "pattern"},
            {"target_name": "Changed canonical name"},
            {"module_id": "algebra-and-functions"},
        )
        for index, change in enumerate(changes, start=2):
            with self.subTest(change=change):
                second = session_fact(
                    record_id=f"record-session-00{index}",
                    session_id=f"session-00{index}",
                    completed_at="2026-08-06T10:10:00+00:00",
                    observations=[
                        knowledge_observation(
                            evidence_id=f"evidence-00{index}",
                            **change,
                        )
                    ],
                )
                with self.assertRaisesRegex(ValidationError, "target identity"):
                    reconcile_state("student-a", [first, second], [], now=NOW)

    def test_target_aliases_are_merged_as_sorted_union(self):
        first = session_fact(
            observations=[knowledge_observation(aliases=["beta", "alpha"])]
        )
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    aliases=["gamma", "alpha"],
                )
            ],
        )

        state = reconcile_state("student-a", [first, second], [], now=NOW)

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual(["alpha", "beta", "gamma"], unit["aliases"])

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
        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        variant = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )
        stable = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-003",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ]
        )
        failure = session_fact(
            record_id="record-session-004",
            session_id="session-004",
            completed_at="2026-08-06T10:30:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-004")],
        )

        state = reconcile_state(
            "student-a", [gap, variant, stable, failure], [], now=NOW
        )

        unit = state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]
        self.assertEqual("confirmed_gap", unit["status"])

    def test_single_initial_error_preserves_higher_mastery(self):
        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        variant = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        stable = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-003",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        transfer = session_fact(
            record_id="record-session-004",
            session_id="session-004",
            completed_at="2026-08-06T10:30:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-004",
                    evidence_type="transfer",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                    student_explanation="I selected the method from its conditions.",
                )
            ],
        )
        scenarios = (
            ("provisionally_mastered", [gap, variant], "2026-08-06T10:15:00+00:00"),
            ("stable", [gap, variant, stable], "2026-08-06T10:25:00+00:00"),
            (
                "transferable",
                [gap, variant, stable, transfer],
                "2026-08-06T10:35:00+00:00",
            ),
        )
        for expected, prior_facts, completed_at in scenarios:
            with self.subTest(expected=expected):
                failure = session_fact(
                    record_id="record-session-005",
                    session_id="session-005",
                    completed_at=completed_at,
                    observations=[
                        knowledge_observation(
                            evidence_id="evidence-005",
                            evidence_type="initial_attempt",
                        )
                    ],
                )

                state = reconcile_state(
                    "student-a", prior_facts + [failure], [], now=NOW
                )

                unit = state["subjects"]["mathematics"]["knowledge_units"][
                    "mathematics.geometry.dihedral-angle"
                ]
                self.assertEqual(expected, unit["status"])

    def test_failed_mastery_checks_lower_higher_mastery(self):
        gap = session_fact(
            observations=[knowledge_observation(evidence_type="initial_attempt")]
        )
        variant = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    evidence_type="variant",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        stable = session_fact(
            record_id="record-session-003",
            session_id="session-003",
            completed_at="2026-08-06T10:20:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-003",
                    evidence_type="delayed_retest",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                )
            ],
        )
        transfer = session_fact(
            record_id="record-session-004",
            session_id="session-004",
            completed_at="2026-08-06T10:30:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-004",
                    evidence_type="transfer",
                    outcome="correct",
                    hint_level="none",
                    first_substantive_error=None,
                    student_explanation="I selected the method from its conditions.",
                )
            ],
        )
        scenarios = (
            ("variant", [gap, variant], "2026-08-06T10:15:00+00:00"),
            (
                "delayed_retest",
                [gap, variant, stable],
                "2026-08-06T10:25:00+00:00",
            ),
            (
                "transfer",
                [gap, variant, stable, transfer],
                "2026-08-06T10:35:00+00:00",
            ),
        )
        for evidence_type, prior_facts, completed_at in scenarios:
            with self.subTest(evidence_type=evidence_type):
                failure = session_fact(
                    record_id="record-session-005",
                    session_id="session-005",
                    completed_at=completed_at,
                    observations=[
                        knowledge_observation(
                            evidence_id="evidence-005",
                            evidence_type=evidence_type,
                        )
                    ],
                )

                state = reconcile_state(
                    "student-a", prior_facts + [failure], [], now=NOW
                )

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
