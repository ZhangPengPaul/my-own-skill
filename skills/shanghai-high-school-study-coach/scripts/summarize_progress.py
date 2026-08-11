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


def render(workspace, now=None):
    workspace = Path(workspace)
    snapshot = validate_workspace(workspace)
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
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        print(render(args.workspace), end="")
    except (OSError, ValidationError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
