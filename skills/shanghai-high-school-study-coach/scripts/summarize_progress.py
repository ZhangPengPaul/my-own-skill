#!/usr/bin/env python3
"""Render recorded student progress as deterministic Markdown."""

import argparse
from collections import Counter
from pathlib import Path
import sys

from validate_student_data import (
    EXPECTED_SUBJECTS,
    ValidationError,
    validate_workspace,
)


def _escape_markdown_line(value):
    escaped = []
    for character in value:
        codepoint = ord(character)
        if codepoint < 0x20 or codepoint == 0x7F:
            escaped.append("\\u%04X" % codepoint)
        else:
            escaped.append(character)
    return "".join(escaped)


def render(workspace):
    workspace = Path(workspace)
    state = validate_workspace(workspace)
    lines = [
        "# 学习进度摘要",
        "",
        "- student_id: %s" % state["student_id"],
        "- updated_at: %s"
        % _escape_markdown_line(state["updated_at"] or "未记录"),
        "- 已完成计划项目: %d" % state["process"]["completed_plan_items"],
        "- 记录会话: %d" % state["process"]["recorded_sessions"],
        "",
        "## 学科状态",
        "",
    ]
    for subject_name in EXPECTED_SUBJECTS:
        subject = state["subjects"][subject_name]
        counts = Counter(
            unit["status"] for unit in subject["knowledge_units"].values()
        )
        facts = ", ".join(
            "%s=%d" % (level, counts[level]) for level in sorted(counts)
        ) or "unassessed=0"
        suffix = ""
        if subject["goal_type"] == "qualification":
            suffix = ", qualification_risk=%s" % subject["qualification_risk"]
        lines.append("- %s: %s%s" % (subject_name, facts, suffix))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        print(render(args.workspace), end="")
    except (OSError, ValidationError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
