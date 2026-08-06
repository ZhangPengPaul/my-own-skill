#!/usr/bin/env python3
"""Initialize a private local student workspace without overwriting data."""

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile

from validate_student_data import STUDENT_ID, ValidationError, validate_workspace


TEMPLATE = Path(__file__).resolve().parents[1] / "assets/student-workspace-template"
PROFILE_PLACEHOLDER = "__STUDENT_ID__"
DARWIN_RENAME_EXCL = 0x00000004
LINUX_AT_FDCWD = -100
LINUX_RENAME_NOREPLACE = 0x00000001


def _read_text_template(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ValidationError("template is not valid UTF-8: %s" % path.name) from exc


def _load_templates():
    profile = _read_text_template(TEMPLATE / "profile.md")
    if profile.count(PROFILE_PLACEHOLDER) != 1:
        raise ValidationError(
            "profile template must contain exactly one %s placeholder"
            % PROFILE_PLACEHOLDER
        )

    state_text = _read_text_template(TEMPLATE / "state.json")
    try:
        state = json.loads(state_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("state template is not valid JSON: %s" % exc) from exc
    if not isinstance(state, dict):
        raise ValidationError("state template must contain a JSON object")

    current_plan = _read_text_template(TEMPLATE / "plans/current.md")
    for filename in ("session-record-template.md", "mistake-record-template.md"):
        _read_text_template(TEMPLATE.parent / filename)
    return profile, state, current_plan


def _raise_publish_error(error_number, destination):
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        raise ValidationError("workspace already exists: %s" % destination)
    unavailable = {errno.ENOSYS, errno.EINVAL}
    for name in ("ENOTSUP", "EOPNOTSUPP"):
        value = getattr(errno, name, None)
        if value is not None:
            unavailable.add(value)
    if error_number in unavailable:
        raise ValidationError(
            "atomic no-clobber publish is unavailable on this platform"
        )
    raise OSError(error_number, os.strerror(error_number), os.fspath(destination))


def _publish_no_replace(source, destination):
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)

    if sys.platform == "darwin":
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            rename = libc.renamex_np
        except (AttributeError, OSError) as exc:
            raise ValidationError(
                "atomic no-clobber publish is unavailable on this platform"
            ) from exc
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = rename(source_bytes, destination_bytes, DARWIN_RENAME_EXCL)
    elif sys.platform.startswith("linux"):
        try:
            libc = ctypes.CDLL(None, use_errno=True)
            rename = libc.renameat2
        except (AttributeError, OSError) as exc:
            raise ValidationError(
                "atomic no-clobber publish is unavailable on this platform"
            ) from exc
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = rename(
            LINUX_AT_FDCWD,
            source_bytes,
            LINUX_AT_FDCWD,
            destination_bytes,
            LINUX_RENAME_NOREPLACE,
        )
    elif sys.platform == "win32":
        try:
            os.rename(source, destination)
        except OSError as exc:
            if exc.errno in (errno.EEXIST, errno.ENOTEMPTY) or getattr(
                exc, "winerror", None
            ) in (80, 183):
                raise ValidationError(
                    "workspace already exists: %s" % destination
                ) from exc
            raise
        return
    else:
        raise ValidationError(
            "atomic no-clobber publish is unavailable on this platform"
        )

    if result != 0:
        _raise_publish_error(ctypes.get_errno(), destination)


def _cleanup_owned_temporary(temporary, identity):
    try:
        current = temporary.lstat()
    except OSError:
        return
    if (
        stat.S_ISDIR(current.st_mode)
        and current.st_dev == identity[0]
        and current.st_ino == identity[1]
    ):
        shutil.rmtree(temporary, ignore_errors=True)


def initialize(root, student_id):
    if not STUDENT_ID.fullmatch(student_id):
        raise ValidationError("invalid student_id")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValidationError("workspace root must be a directory")
    profile, state, current_plan = _load_templates()

    destination = root / student_id
    if destination.exists():
        raise ValidationError("workspace already exists: %s" % destination)

    temporary = Path(tempfile.mkdtemp(prefix=".%s-" % student_id, dir=str(root)))
    identity = None
    published = False
    try:
        created = temporary.lstat()
        if not stat.S_ISDIR(created.st_mode):
            raise ValidationError("temporary workspace is not a directory")
        identity = (created.st_dev, created.st_ino)
        (temporary / "plans").mkdir()
        for directory in ("mistakes", "sessions", "materials"):
            (temporary / directory).mkdir()
        (temporary / "profile.md").write_text(
            profile.replace(PROFILE_PLACEHOLDER, student_id), encoding="utf-8"
        )
        state["student_id"] = student_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        (temporary / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temporary / "plans/current.md").write_text(
            current_plan, encoding="utf-8"
        )
        validate_workspace(temporary)
        _publish_no_replace(temporary, destination)
        published = True
    except BaseException:
        if not published and identity is not None:
            _cleanup_owned_temporary(temporary, identity)
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
