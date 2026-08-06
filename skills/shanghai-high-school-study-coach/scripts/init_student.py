#!/usr/bin/env python3
"""Initialize a private local student workspace without overwriting data."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from validate_student_data import STUDENT_ID, ValidationError, validate_workspace


TEMPLATE = Path(__file__).resolve().parents[1] / "assets/student-workspace-template"


def initialize(root, student_id):
    if not STUDENT_ID.fullmatch(student_id):
        raise ValidationError("invalid student_id")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / student_id
    if destination.exists():
        raise ValidationError("workspace already exists: %s" % destination)

    temporary = Path(tempfile.mkdtemp(prefix=".%s-" % student_id, dir=str(root)))
    try:
        (temporary / "plans").mkdir()
        for directory in ("mistakes", "sessions", "materials"):
            (temporary / directory).mkdir()
        profile = (TEMPLATE / "profile.md").read_text(encoding="utf-8")
        (temporary / "profile.md").write_text(
            profile.replace("__STUDENT_ID__", student_id), encoding="utf-8"
        )
        state = json.loads((TEMPLATE / "state.json").read_text(encoding="utf-8"))
        state["student_id"] = student_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        (temporary / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(TEMPLATE / "plans/current.md", temporary / "plans/current.md")
        validate_workspace(temporary)
        os.replace(temporary, destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        destination = initialize(args.root, args.student_id)
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
