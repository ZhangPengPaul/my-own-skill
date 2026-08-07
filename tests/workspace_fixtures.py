"""Canonical fictional learning-state fixtures shared by repository tests."""


def session_fact(**overrides):
    value = {
        "schema_version": 2,
        "record_type": "session",
        "record_id": "record-session-001",
        "session_id": "session-001",
        "supersedes_record_id": None,
        "status": "completed",
        "subject": "mathematics",
        "task_mode": "practice",
        "completed_at": "2026-08-06T10:00:00+00:00",
        "source_materials": ["fictional prompt"],
        "student_attempt": "fictional student attempt",
        "observations": [],
        "remaining_uncertainty": [],
    }
    value.update(overrides)
    return value


def knowledge_observation(**overrides):
    value = {
        "evidence_id": "evidence-001",
        "target_kind": "knowledge_unit",
        "module_id": "geometry",
        "target_id": "mathematics.geometry.dihedral-angle",
        "target_name": "二面角的平面角",
        "aliases": [],
        "evidence_type": "diagnostic",
        "outcome": "incorrect",
        "hint_level": "principle",
        "student_response": "fictional response",
        "first_substantive_error": "fictional first error",
        "student_explanation": None,
        "next_review_at": None,
        "uncertainty": None,
    }
    value.update(overrides)
    return value


def pattern_observation(**overrides):
    value = knowledge_observation(
        target_kind="pattern",
        module_id="reasoning",
        target_id="mathematics.pattern.method-selection",
        target_name="方法选择",
    )
    value.update(overrides)
    return value


def plan_fact(**overrides):
    value = {
        "schema_version": 2,
        "record_type": "plan_item",
        "record_id": "record-plan-001",
        "item_id": "item-001",
        "supersedes_record_id": None,
        "status": "pending",
        "subject": "mathematics",
        "target_kind": "knowledge_unit",
        "target_id": "mathematics.geometry.dihedral-angle",
        "task": "Complete one fictional targeted practice task.",
        "estimated_minutes": 15,
        "due_at": "2026-08-13T10:00:00+00:00",
        "priority": 1,
        "completion_evidence_id": None,
    }
    value.update(overrides)
    return value
