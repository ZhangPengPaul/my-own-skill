#!/usr/bin/env python3
"""Render recorded student progress as deterministic Markdown."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from validate_student_data import ValidationError, validate_workspace


def render(workspace):
    workspace = Path(workspace)
    validate_workspace(workspace)
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    lines = [
        "# 学习进度摘要",
        "",
        "- student_id: %s" % state["student_id"],
        "- updated_at: %s" % (state["updated_at"] or "未记录"),
        "- 已完成计划项目: %d" % state["process"]["completed_plan_items"],
        "- 记录会话: %d" % state["process"]["recorded_sessions"],
        "",
        "## 学科状态",
        "",
    ]
    for subject_name, subject in state["subjects"].items():
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
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
