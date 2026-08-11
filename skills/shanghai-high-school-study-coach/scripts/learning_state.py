"""Validate structured learning facts and their evidence records."""

from datetime import datetime, timezone
import re


SUBJECTS = (
    "chinese",
    "mathematics",
    "english",
    "politics",
    "history",
    "geography",
)
TASK_MODES = (
    "assessment",
    "explanation",
    "practice",
    "grading",
    "review",
    "planning",
)
CONTENT_STATES = (
    "unassessed",
    "suspected_gap",
    "confirmed_gap",
    "strengthening",
    "provisionally_mastered",
    "stable",
    "transferable",
)
PATTERN_STATES = (
    "observed_once",
    "recurring",
    "improving",
    "controlled",
)
EVIDENCE_TYPES = (
    "initial_attempt",
    "diagnostic",
    "correction",
    "variant",
    "delayed_retest",
    "transfer",
)
HINT_LEVELS = (
    "none",
    "locate",
    "principle",
    "next_step",
    "worked_example",
)

ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def _require_id(value, field):
    require(isinstance(value, str) and ID.fullmatch(value), f"{field} is invalid")


def _require_timestamp(value, field, allow_none=False):
    if allow_none and value is None:
        return
    require(isinstance(value, str) and value.strip(), f"{field} is required")
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(
            f"{field} must be an ISO-8601 timestamp"
        ) from error


def _require_exact_keys(value, expected, label):
    require(
        set(value) == expected,
        f"{label} fields are invalid: {sorted(set(value) ^ expected)}",
    )


def validate_observation(observation, subject):
    require(isinstance(observation, dict), "observation must be an object")
    _require_exact_keys(
        observation,
        {
            "evidence_id",
            "target_kind",
            "module_id",
            "target_id",
            "target_name",
            "aliases",
            "evidence_type",
            "outcome",
            "hint_level",
            "student_response",
            "first_substantive_error",
            "student_explanation",
            "next_review_at",
            "uncertainty",
        },
        "observation",
    )
    _require_id(observation.get("evidence_id"), "evidence_id")
    require(
        observation.get("target_kind") in ("knowledge_unit", "pattern"),
        "target_kind is invalid",
    )
    _require_id(observation.get("module_id"), "module_id")
    target_id = observation.get("target_id")
    require(
        isinstance(target_id, str) and target_id.startswith(subject + "."),
        "target_id must match session subject",
    )
    require(
        isinstance(observation.get("target_name"), str)
        and observation["target_name"].strip(),
        "target_name is required",
    )
    require(
        isinstance(observation.get("aliases"), list)
        and all(
            isinstance(value, str) and value.strip()
            for value in observation["aliases"]
        ),
        "aliases is invalid",
    )
    require(
        observation.get("evidence_type") in EVIDENCE_TYPES,
        "evidence_type is invalid",
    )
    require(
        observation.get("outcome") in ("correct", "incorrect"),
        "outcome is invalid",
    )
    require(
        observation.get("hint_level") in HINT_LEVELS,
        "hint_level is invalid",
    )
    require(
        isinstance(observation.get("student_response"), str)
        and observation["student_response"].strip(),
        "student_response is required",
    )
    if observation["outcome"] == "incorrect":
        require(
            isinstance(observation.get("first_substantive_error"), str)
            and observation["first_substantive_error"].strip(),
            "first_substantive_error is required for incorrect evidence",
        )
    else:
        require(
            observation.get("first_substantive_error") is None,
            "first_substantive_error must be null for correct evidence",
        )
    if (
        observation["evidence_type"] == "transfer"
        and observation["outcome"] == "correct"
    ):
        require(
            observation["hint_level"] == "none"
            and isinstance(observation.get("student_explanation"), str)
            and observation["student_explanation"].strip(),
            "correct transfer evidence requires no hint and a student explanation",
        )


def validate_session_fact(fact):
    require(isinstance(fact, dict), "session fact must be an object")
    _require_exact_keys(
        fact,
        {
            "schema_version",
            "record_type",
            "record_id",
            "session_id",
            "supersedes_record_id",
            "status",
            "subject",
            "task_mode",
            "completed_at",
            "source_materials",
            "student_attempt",
            "observations",
            "remaining_uncertainty",
        },
        "session fact",
    )
    require(
        fact.get("schema_version") == 2
        and type(fact.get("schema_version")) is int,
        "schema_version must be the integer 2",
    )
    require(fact.get("record_type") == "session", "record_type must be session")
    _require_id(fact.get("record_id"), "record_id")
    _require_id(fact.get("session_id"), "session_id")
    supersedes = fact.get("supersedes_record_id")
    require(
        supersedes is None
        or (isinstance(supersedes, str) and ID.fullmatch(supersedes)),
        "supersedes_record_id is invalid",
    )
    require(
        fact.get("status") in ("incomplete", "completed"),
        "status is invalid",
    )
    require(fact.get("subject") in SUBJECTS, "subject is invalid")
    require(fact.get("task_mode") in TASK_MODES, "task_mode is invalid")
    _require_timestamp(
        fact.get("completed_at"),
        "completed_at",
        allow_none=fact["status"] == "incomplete",
    )
    require(
        isinstance(fact.get("source_materials"), list)
        and all(
            isinstance(value, str) and value.strip()
            for value in fact["source_materials"]
        ),
        "source_materials is invalid",
    )
    require(
        fact.get("student_attempt") is None
        or isinstance(fact.get("student_attempt"), str),
        "student_attempt must be null or a string",
    )
    require(
        isinstance(fact.get("observations"), list),
        "observations must be a list",
    )
    require(
        isinstance(fact.get("remaining_uncertainty"), list)
        and all(
            isinstance(value, str) and value.strip()
            for value in fact["remaining_uncertainty"]
        ),
        "remaining_uncertainty is invalid",
    )
    for observation in fact["observations"]:
        validate_observation(observation, fact["subject"])
    evidence_ids = [item["evidence_id"] for item in fact["observations"]]
    require(
        len(evidence_ids) == len(set(evidence_ids)),
        "evidence_id values must be unique within a session",
    )


def validate_plan_fact(fact):
    require(isinstance(fact, dict), "plan fact must be an object")
    _require_exact_keys(
        fact,
        {
            "schema_version",
            "record_type",
            "record_id",
            "item_id",
            "supersedes_record_id",
            "status",
            "subject",
            "target_kind",
            "target_id",
            "task",
            "estimated_minutes",
            "due_at",
            "priority",
            "completion_evidence_id",
        },
        "plan fact",
    )
    require(
        fact.get("schema_version") == 2
        and type(fact.get("schema_version")) is int,
        "schema_version must be the integer 2",
    )
    require(
        fact.get("record_type") == "plan_item",
        "record_type must be plan_item",
    )
    _require_id(fact.get("record_id"), "record_id")
    _require_id(fact.get("item_id"), "item_id")
    supersedes = fact.get("supersedes_record_id")
    require(
        supersedes is None
        or (isinstance(supersedes, str) and ID.fullmatch(supersedes)),
        "supersedes_record_id is invalid",
    )
    require(
        fact.get("status") in ("pending", "completed"),
        "status is invalid",
    )
    require(fact.get("subject") in SUBJECTS, "subject is invalid")
    require(
        fact.get("target_kind") in ("knowledge_unit", "pattern"),
        "target_kind is invalid",
    )
    require(
        isinstance(fact.get("target_id"), str)
        and fact["target_id"].startswith(fact["subject"] + "."),
        "target_id must match plan subject",
    )
    require(
        isinstance(fact.get("task"), str) and fact["task"].strip(),
        "task is required",
    )
    require(
        type(fact.get("estimated_minutes")) is int
        and fact["estimated_minutes"] > 0,
        "estimated_minutes must be a positive integer",
    )
    _require_timestamp(fact.get("due_at"), "due_at", allow_none=True)
    require(
        type(fact.get("priority")) is int and 1 <= fact["priority"] <= 4,
        "priority must be an integer from 1 to 4",
    )
    if fact["status"] == "completed":
        _require_id(
            fact.get("completion_evidence_id"),
            "completion_evidence_id",
        )
    else:
        require(
            fact.get("completion_evidence_id") is None,
            "pending plan item cannot have completion evidence",
        )


def validate_fact(fact):
    require(isinstance(fact, dict), "fact must be an object")
    if fact.get("record_type") == "session":
        validate_session_fact(fact)
    elif fact.get("record_type") == "plan_item":
        validate_plan_fact(fact)
    else:
        raise ValidationError("record_type is invalid")


def _active_revisions(records, stable_field, validator):
    by_record_id = {}
    children = {}
    for record in records:
        validator(record)
        record_id = record["record_id"]
        require(
            record_id not in by_record_id,
            f"duplicate record_id: {record_id}",
        )
        by_record_id[record_id] = record
    for record in records:
        parent_id = record["supersedes_record_id"]
        if parent_id is None:
            continue
        require(
            parent_id in by_record_id,
            f"missing superseded record: {parent_id}",
        )
        parent = by_record_id[parent_id]
        require(
            parent[stable_field] == record[stable_field],
            "revision must preserve stable id",
        )
        require(parent_id not in children, f"revision fork at {parent_id}")
        children[parent_id] = record["record_id"]
    for record in records:
        seen = set()
        current = record
        while current["supersedes_record_id"] is not None:
            require(
                current["record_id"] not in seen,
                "revision cycle detected",
            )
            seen.add(current["record_id"])
            current = by_record_id[current["supersedes_record_id"]]
    leaves = {}
    for record in records:
        if record["record_id"] not in children:
            stable_id = record[stable_field]
            require(
                stable_id not in leaves,
                f"multiple active revisions for {stable_id}",
            )
            leaves[stable_id] = record
    return leaves


def _content_status(observation):
    if observation["outcome"] == "incorrect":
        if observation["evidence_type"] == "initial_attempt":
            return "suspected_gap"
        return "confirmed_gap"
    if (
        observation["hint_level"] != "none"
        or observation["evidence_type"] == "correction"
    ):
        return "strengthening"
    if observation["evidence_type"] in (
        "initial_attempt",
        "diagnostic",
        "variant",
    ):
        return "provisionally_mastered"
    if observation["evidence_type"] == "delayed_retest":
        return "stable"
    return "transferable"


def _pattern_status(observation, prior_incorrect_count):
    if observation["outcome"] == "incorrect":
        return "recurring" if prior_incorrect_count >= 1 else "observed_once"
    if (
        observation["evidence_type"] in ("delayed_retest", "transfer")
        and observation["hint_level"] == "none"
    ):
        return "controlled"
    return "improving"


def _new_target(observation):
    return {
        "name": observation["target_name"],
        "module_id": observation["module_id"],
        "aliases": list(observation["aliases"]),
        "status": None,
        "evidence_ids": [],
        "last_evidence_at": None,
        "next_review_at": None,
    }


def _normalized_state(state):
    normalized = dict(state)
    normalized["updated_at"] = None
    return normalized


def reconcile_state(
    student_id,
    sessions,
    plan_items,
    previous_state=None,
    now=None,
):
    _require_id(student_id, "student_id")
    sessions = tuple(sessions)
    plan_items = tuple(plan_items)
    record_ids = set()
    for record in sessions + plan_items:
        require(isinstance(record, dict), "fact must be an object")
        record_id = record.get("record_id")
        _require_id(record_id, "record_id")
        require(
            record_id not in record_ids,
            f"duplicate record_id: {record_id}",
        )
        record_ids.add(record_id)
    active_sessions = _active_revisions(
        sessions,
        "session_id",
        validate_session_fact,
    )
    active_plan_items = _active_revisions(
        plan_items,
        "item_id",
        validate_plan_fact,
    )
    completed_sessions = sorted(
        (
            fact
            for fact in active_sessions.values()
            if fact["status"] == "completed"
        ),
        key=lambda fact: (
            fact["completed_at"],
            fact["session_id"],
            fact["record_id"],
        ),
    )
    subjects = {
        subject: {"knowledge_units": {}, "patterns": {}}
        for subject in SUBJECTS
    }
    evidence_by_id = {}
    pattern_incorrect_counts = {}

    for fact in completed_sessions:
        for observation in fact["observations"]:
            evidence_id = observation["evidence_id"]
            require(
                evidence_id not in evidence_by_id,
                f"duplicate active evidence_id: {evidence_id}",
            )
            evidence_by_id[evidence_id] = (fact, observation)
            collection_name = (
                "knowledge_units"
                if observation["target_kind"] == "knowledge_unit"
                else "patterns"
            )
            collection = subjects[fact["subject"]][collection_name]
            target_id = observation["target_id"]
            target = collection.setdefault(
                target_id,
                _new_target(observation),
            )
            target["name"] = observation["target_name"]
            target["module_id"] = observation["module_id"]
            target["aliases"] = list(observation["aliases"])
            target["evidence_ids"].append(evidence_id)
            target["last_evidence_at"] = fact["completed_at"]
            target["next_review_at"] = observation["next_review_at"]

            if observation["target_kind"] == "knowledge_unit":
                target["status"] = _content_status(observation)
            else:
                prior_count = pattern_incorrect_counts.get(target_id, 0)
                target["status"] = _pattern_status(observation, prior_count)
                if observation["outcome"] == "incorrect":
                    pattern_incorrect_counts[target_id] = prior_count + 1

    completed_plan_items = 0
    for plan_item in active_plan_items.values():
        if plan_item["status"] != "completed":
            continue
        evidence = evidence_by_id.get(plan_item["completion_evidence_id"])
        if evidence is None:
            continue
        session, observation = evidence
        if (
            session["subject"] == plan_item["subject"]
            and observation["target_kind"] == plan_item["target_kind"]
            and observation["target_id"] == plan_item["target_id"]
        ):
            completed_plan_items += 1

    candidate = {
        "schema_version": 2,
        "student_id": student_id,
        "updated_at": None,
        "subjects": subjects,
        "process": {
            "completed_plan_items": completed_plan_items,
            "recorded_sessions": len(completed_sessions),
        },
    }
    if (
        isinstance(previous_state, dict)
        and _normalized_state(previous_state) == candidate
    ):
        return previous_state

    updated_at = now or datetime.now(timezone.utc).isoformat()
    _require_timestamp(updated_at, "now")
    candidate["updated_at"] = updated_at
    return candidate
