#!/usr/bin/env python3
"""Render validated evidence-based learning priorities as Markdown."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import sys

from learning_state import SUBJECTS, parse_timestamp
from validate_student_data import ValidationError, validate_workspace


CONTENT_LABELS = (
    ("unassessed", "未评估"),
    ("suspected_gap", "待确认薄弱"),
    ("confirmed_gap", "已确认薄弱"),
    ("strengthening", "强化中"),
    ("provisionally_mastered", "暂时掌握"),
    ("stable", "稳定"),
    ("transferable", "可迁移"),
)
PATTERN_LABELS = {
    "recurring": "重复出现",
    "improving": "改善中",
}

# These task types explicitly test a target. An initial attempt is another
# occurrence, while a correction may still depend on the just-given teaching;
# neither closes an unresolved interaction observation.
VALIDATION_EVIDENCE_TYPES = frozenset(
    ("diagnostic", "variant", "delayed_retest", "transfer")
)


def _escape_markdown_line(value):
    escaped = []
    for character in str(value):
        codepoint = ord(character)
        if codepoint < 0x20 or codepoint == 0x7F:
            escaped.append("\\u%04X" % codepoint)
        else:
            escaped.append(character)
    return "".join(escaped)


def _active_pending_plan_items(plan_items):
    superseded = {
        item["supersedes_record_id"]
        for item in plan_items
        if item["supersedes_record_id"] is not None
    }
    active = [
        item
        for item in plan_items
        if item["record_id"] not in superseded and item["status"] == "pending"
    ]
    return sorted(
        active,
        key=lambda item: (
            item["priority"],
            item["due_at"] is None,
            parse_timestamp(item["due_at"], "due_at")
            if item["due_at"] is not None
            else None,
            item["item_id"],
        ),
    )


def _active_completed_sessions(sessions):
    superseded = {
        session["supersedes_record_id"]
        for session in sessions
        if session["supersedes_record_id"] is not None
    }
    return tuple(
        session
        for session in sessions
        if session["record_id"] not in superseded
        and session["status"] == "completed"
    )


def _latest_validation_times(sessions):
    latest_by_signal = {}
    for session in _active_completed_sessions(sessions):
        completed_at = parse_timestamp(session["completed_at"], "completed_at")
        for evidence in session["observations"]:
            if evidence["evidence_type"] not in VALIDATION_EVIDENCE_TYPES:
                continue
            for signal_kind in evidence.get(
                "resolves_observation_signal_kinds", ()
            ):
                target_signal = (
                    session["subject"],
                    evidence["module_id"],
                    evidence["target_kind"],
                    evidence["target_id"],
                    signal_kind,
                )
                existing = latest_by_signal.get(target_signal)
                if existing is None or completed_at > existing:
                    latest_by_signal[target_signal] = completed_at
    return latest_by_signal


def _observation_summaries(observations, sessions):
    latest_validation = _latest_validation_times(sessions)
    groups = {}
    for observation in observations:
        if observation["target_id"] == "pending-normalization":
            continue
        target = (
            observation["subject"],
            observation["module_id"],
            observation["target_kind"],
            observation["target_id"],
            observation["signal_kind"],
        )
        resolved_at = latest_validation.get(target)
        if (
            resolved_at is not None
            and resolved_at
            > parse_timestamp(observation["occurred_at"], "occurred_at")
        ):
            continue
        key = (
            observation["subject"],
            observation["module_id"],
            observation["target_kind"],
            observation["target_id"],
            observation["signal_kind"],
        )
        groups.setdefault(key, []).append(observation)

    singletons = []
    pending = []
    for key, group in groups.items():
        by_interaction = {}
        for observation in group:
            interaction_id = observation["interaction_id"]
            existing = by_interaction.get(interaction_id)
            if existing is None or (
                parse_timestamp(observation["occurred_at"], "occurred_at"),
                observation["record_id"],
            ) > (
                parse_timestamp(existing["occurred_at"], "occurred_at"),
                existing["record_id"],
            ):
                by_interaction[interaction_id] = observation
        unique = sorted(
            by_interaction.values(),
            key=lambda item: (
                parse_timestamp(item["occurred_at"], "occurred_at"),
                item["interaction_id"],
                item["record_id"],
            ),
        )
        latest = unique[-1]
        summary = {
            "subject": key[0],
            "module_id": key[1],
            "target_kind": key[2],
            "target_id": key[3],
            "target_name": latest["target_name"],
            "signal_kind": key[4],
            "observation_count": len(unique),
            "latest_occurred_at": latest["occurred_at"],
            "signal": latest["signal"],
            "uncertainties": sorted(
                {item["uncertainty"] for item in unique if item["uncertainty"]}
            ),
            "member_observations": tuple(
                {
                    "signal": item["signal"],
                    "student_action": item["student_action"],
                    "uncertainty": item["uncertainty"],
                }
                for item in unique
            ),
        }
        (singletons if len(unique) == 1 else pending).append(summary)

    def sort_key(item):
        return (
            item["subject"],
            item["module_id"],
            item["target_kind"],
            item["target_id"],
            item["signal_kind"],
        )

    return tuple(sorted(singletons, key=sort_key)), tuple(
        sorted(pending, key=sort_key)
    )


def _render_subject(lines, subject_name, subject, now):
    lines.extend(("### %s" % subject_name, ""))
    units = subject["knowledge_units"]
    counts = Counter(unit["status"] for unit in units.values())
    lines.append(
        "- "
        + "；".join(
            "%s: %d" % (label, counts[state])
            for state, label in CONTENT_LABELS
        )
    )

    for target_id, target in sorted(units.items()):
        due = target["next_review_at"]
        due_label = ""
        if due is not None and parse_timestamp(due, "next_review_at") <= now:
            due_label = "；到期复测"
        evidence_ids = ", ".join(
            _escape_markdown_line(evidence_id)
            for evidence_id in target["evidence_ids"]
        )
        lines.append(
            "- %s [%s%s; evidence: %s]"
            % (
                _escape_markdown_line(target["name"]),
                _escape_markdown_line(target["status"]),
                due_label,
                evidence_ids,
            )
        )

    patterns = [
        (target_id, target)
        for target_id, target in subject["patterns"].items()
        if target["status"] in PATTERN_LABELS
    ]
    for target_id, target in sorted(patterns):
        evidence_ids = ", ".join(
            _escape_markdown_line(evidence_id)
            for evidence_id in target["evidence_ids"]
        )
        lines.append(
            "- 模式：%s [%s; evidence: %s]"
            % (
                _escape_markdown_line(target["name"]),
                _escape_markdown_line(PATTERN_LABELS[target["status"]]),
                evidence_ids,
            )
        )
    lines.append("")


def render(workspace, now=None, expected_student_id=None):
    workspace = Path(workspace)
    if expected_student_id is None:
        snapshot = validate_workspace(workspace)
    else:
        snapshot = validate_workspace(
            workspace,
            expected_student_id=expected_student_id,
        )
    state = snapshot.state
    current = parse_timestamp(
        now or datetime.now(timezone.utc).isoformat(),
        "now",
    )
    lines = [
        "# 学习进度摘要",
        "",
        "- student_id: %s" % _escape_markdown_line(state["student_id"]),
        "- updated_at: %s" % _escape_markdown_line(state["updated_at"]),
        "- 已完成计划项目: %d" % state["process"]["completed_plan_items"],
        "- 记录会话: %d" % state["process"]["recorded_sessions"],
        "",
        "## 学科状态",
        "",
    ]
    for subject_name in SUBJECTS:
        _render_subject(lines, subject_name, state["subjects"][subject_name], current)

    lines.extend(("## 当前计划", ""))
    pending = _active_pending_plan_items(snapshot.plan_items)
    if not pending:
        lines.append("- 无待办项目")
    for item in pending:
        due = _escape_markdown_line(item["due_at"] or "未设日期")
        lines.append(
            "- 优先级 %d｜%s｜%s"
            % (item["priority"], due, _escape_markdown_line(item["task"]))
        )
    singleton_observations, pending_observations = _observation_summaries(
        snapshot.observations,
        snapshot.sessions,
    )
    lines.extend(("", "## 未解决单次弱线索", ""))
    if not singleton_observations:
        lines.append("- 无未解决单次弱线索")
    for item in singleton_observations:
        uncertainty = "; ".join(
            _escape_markdown_line(value)
            for value in item["uncertainties"]
        ) or "无"
        lines.append(
            "- subject: %s｜module: %s｜target_kind: %s｜target_id: %s｜"
            "target_name: %s｜"
            "signal_kind: %s｜signal: %s｜time: %s｜uncertainty: %s"
            % (
                _escape_markdown_line(item["subject"]),
                _escape_markdown_line(item["module_id"]),
                _escape_markdown_line(item["target_kind"]),
                _escape_markdown_line(item["target_id"]),
                _escape_markdown_line(item["target_name"]),
                _escape_markdown_line(item["signal_kind"]),
                _escape_markdown_line(item["signal"]),
                _escape_markdown_line(item["latest_occurred_at"]),
                uncertainty,
            )
        )
    lines.extend(("", "## 待验证观察", ""))
    if not pending_observations:
        lines.append("- 无待验证观察")
    for item in pending_observations:
        uncertainty = "; ".join(
            _escape_markdown_line(value)
            for value in item["uncertainties"]
        ) or "无"
        lines.append(
            "- subject: %s｜module: %s｜target_kind: %s｜target_id: %s｜"
            "target_name: %s｜signal_kind: %s｜signal: %s｜"
            "出现 %d 次｜latest: %s｜不确定性: %s"
            % (
                _escape_markdown_line(item["subject"]),
                _escape_markdown_line(item["module_id"]),
                _escape_markdown_line(item["target_kind"]),
                _escape_markdown_line(item["target_id"]),
                _escape_markdown_line(item["target_name"]),
                _escape_markdown_line(item["signal_kind"]),
                _escape_markdown_line(item["signal"]),
                item["observation_count"],
                _escape_markdown_line(item["latest_occurred_at"]),
                uncertainty,
            )
        )
        for index, member in enumerate(item["member_observations"], start=1):
            lines.append(
                "  - 成员观察 %d｜signal: %s｜student_action: %s｜uncertainty: %s"
                % (
                    index,
                    _escape_markdown_line(member["signal"]),
                    _escape_markdown_line(member["student_action"]),
                    _escape_markdown_line(member["uncertainty"] or "无"),
                )
            )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--student-id", required=True)
    args = parser.parse_args()
    try:
        print(
            render(args.workspace, expected_student_id=args.student_id),
            end="",
        )
    except (OSError, ValidationError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
