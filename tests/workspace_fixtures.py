"""Canonical fictional learning-state fixtures shared by repository tests."""

import json


def session_fact(**overrides):
    value = {
        "schema_version": 2,
        "record_type": "session",
        "record_id": "record-session-001",
        "session_id": "session-001",
        "supersedes_record_id": None,
        "status": "completed",
        "subject": "mathematics",
        "task_id": "task-001",
        "task_mode": "practice",
        "mode_transitions": [],
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
        module_id="geometry",
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


def state_from_facts(
    student_id="student-a",
    sessions=(),
    plan_items=(),
    now="2026-08-06T12:00:00+00:00",
):
    from learning_state import reconcile_state

    return reconcile_state(
        student_id,
        list(sessions),
        list(plan_items),
        now=now,
    )


def create_workspace(
    workspace,
    sessions=(),
    plan_items=(),
    state=None,
):
    workspace.mkdir(parents=True)
    (workspace / "profile.md").write_text("# Fictional student\n", encoding="utf-8")
    (workspace / ".workspace.lock").touch()
    for name in ("sessions", "plan-items", "summaries", "materials"):
        (workspace / name).mkdir()

    session_values = list(sessions)
    plan_values = list(plan_items)
    for fact in session_values:
        path = workspace / "sessions" / f"{fact['record_id']}.json"
        path.write_text(
            json.dumps(fact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    for fact in plan_values:
        path = workspace / "plan-items" / f"{fact['record_id']}.json"
        path.write_text(
            json.dumps(fact, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    if state is None:
        state = state_from_facts(
            student_id=workspace.name,
            sessions=session_values,
            plan_items=plan_values,
        )
    (workspace / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return state
