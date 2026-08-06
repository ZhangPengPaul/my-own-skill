#!/usr/bin/env python3
"""Validate a Shanghai high-school study coach student workspace."""

import argparse
import json
from pathlib import Path
import re
import sys


EXPECTED_SUBJECTS = {
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
MASTERY_LEVELS = {
    "unassessed",
    "emerging",
    "developing",
    "stable",
    "transferable",
}
QUALIFICATION_RISKS = {"unassessed", "low", "medium", "high"}
STUDENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ValidationError(ValueError):
    """Raised when student data does not satisfy the workspace contract."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def validate_state(state, workspace=None):
    require(isinstance(state, dict), "state must be an object")
    require(state.get("schema_version") == 1, "schema_version must be 1")

    student_id = state.get("student_id")
    require(
        isinstance(student_id, str) and STUDENT_ID.fullmatch(student_id),
        "student_id must use lowercase letters, digits, and hyphens",
    )
    require(
        state.get("updated_at") is None or isinstance(state.get("updated_at"), str),
        "updated_at must be null or a string",
    )

    subjects = state.get("subjects")
    require(isinstance(subjects, dict), "subjects must be an object")
    require(
        set(subjects) == set(EXPECTED_SUBJECTS),
        "subjects must contain exactly the nine supported subjects",
    )

    workspace_path = Path(workspace) if workspace is not None else None
    for subject, expected_goal_type in EXPECTED_SUBJECTS.items():
        subject_state = subjects[subject]
        require(isinstance(subject_state, dict), f"subjects.{subject} must be an object")
        require(
            subject_state.get("goal_type") == expected_goal_type,
            f"subjects.{subject}.goal_type must be {expected_goal_type}",
        )
        require(
            isinstance(subject_state.get("assessments"), list),
            f"subjects.{subject}.assessments must be a list",
        )

        knowledge_units = subject_state.get("knowledge_units")
        require(
            isinstance(knowledge_units, dict),
            f"subjects.{subject}.knowledge_units must be an object",
        )

        if expected_goal_type == "qualification":
            require(
                subject_state.get("qualification_risk") in QUALIFICATION_RISKS,
                f"subjects.{subject}.qualification_risk is invalid",
            )
        else:
            require(
                "qualification_risk" not in subject_state,
                f"subjects.{subject}.qualification_risk is not allowed",
            )

        for unit_name, unit in knowledge_units.items():
            prefix = f"subjects.{subject}.knowledge_units.{unit_name}"
            require(isinstance(unit, dict), f"{prefix} must be an object")
            require(unit.get("status") in MASTERY_LEVELS, f"{prefix}.status is invalid")

            evidence = unit.get("evidence")
            require(
                isinstance(evidence, list)
                and all(isinstance(path, str) for path in evidence),
                f"{prefix}.evidence must be a list of strings",
            )
            if unit["status"] != "unassessed":
                require(evidence, f"{prefix}.evidence is required for assessed mastery")

            for date_field in ("last_reviewed_at", "next_review_at"):
                value = unit.get(date_field)
                require(
                    value is None or isinstance(value, str),
                    f"{prefix}.{date_field} must be null or a string",
                )

            if workspace_path is not None:
                for evidence_path in evidence:
                    require(
                        evidence_path.startswith("sessions/"),
                        f"{prefix}.evidence path must start with sessions/: {evidence_path}",
                    )
                    require(
                        (workspace_path / evidence_path).is_file(),
                        f"{prefix}.evidence file is missing: {evidence_path}",
                    )

    process = state.get("process")
    require(isinstance(process, dict), "process must be an object")
    for field in ("completed_plan_items", "recorded_sessions"):
        value = process.get(field)
        require(
            isinstance(value, int) and not isinstance(value, bool) and value >= 0,
            f"process.{field} must be a non-negative integer",
        )


def validate_workspace(workspace):
    workspace = Path(workspace)
    for relative_path in ("profile.md", "state.json", "plans/current.md"):
        require(
            (workspace / relative_path).is_file(),
            f"required file is missing: {relative_path}",
        )
    for relative_path in ("mistakes", "sessions", "materials"):
        require(
            (workspace / relative_path).is_dir(),
            f"required directory is missing: {relative_path}",
        )

    try:
        state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValidationError(f"cannot read state.json: {error}") from error

    validate_state(state, workspace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()

    try:
        validate_workspace(args.workspace)
    except ValidationError as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1

    print(f"VALID: {args.workspace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
