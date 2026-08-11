#!/usr/bin/env python3
"""Commit one immutable learning fact and reconcile derived state."""

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import fcntl
import json
import os
from pathlib import Path
import stat
import sys
import uuid

from learning_state import ValidationError, reconcile_state, validate_fact
from validate_student_data import (
    _open_existing_directory,
    _open_existing_regular,
    _read_workspace_snapshot_fd_unlocked,
    open_workspace_descriptor,
    validate_state,
)


def _canonical_json(value):
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _write_all(file_fd, data):
    offset = 0
    while offset < len(data):
        written = os.write(file_fd, data[offset:])
        if written == 0:
            raise OSError(errno.EIO, "write returned zero bytes")
        offset += written


def _read_all(file_fd):
    chunks = []
    while True:
        chunk = os.read(file_fd, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _entry_identity(entry):
    return (entry.st_dev, entry.st_ino, stat.S_IFMT(entry.st_mode))


def _name_identity(directory_fd, name):
    try:
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return _entry_identity(entry)


def _unlink_if_identity_matches(directory_fd, name, expected_identity):
    # Callers rely on the workspace flock and UUID names for cooperative
    # concurrency; only entries matching at check time are cleaned up here.
    if (
        expected_identity is None
        or _name_identity(directory_fd, name) != expected_identity
    ):
        return False
    os.unlink(name, dir_fd=directory_fd)
    return True


def _publish_held_file_no_clobber(source_fd, directory_fd, filename):
    if sys.platform != "darwin":
        raise ValidationError(
            "atomic held-file publish is unavailable on this platform"
        )
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        clone_file = libc.fclonefileat
    except (AttributeError, OSError) as error:
        raise ValidationError(
            "atomic held-file publish is unavailable on this platform"
        ) from error

    clone_file.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    clone_file.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = clone_file(
        source_fd,
        directory_fd,
        os.fsencode(filename),
        0,
    )
    if result == 0:
        return

    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise FileExistsError(
            error_number,
            os.strerror(error_number),
            filename,
        )
    unavailable = {errno.ENOSYS, errno.EINVAL}
    for name in ("ENOTSUP", "EOPNOTSUPP"):
        value = getattr(errno, name, None)
        if value is not None:
            unavailable.add(value)
    if error_number in unavailable:
        raise ValidationError(
            "atomic held-file publish is unavailable on this platform"
        )
    raise OSError(error_number, os.strerror(error_number), filename)


def _publish_fact_no_clobber(directory_fd, fact):
    data = _canonical_json(fact)
    filename = fact["record_id"] + ".json"
    temporary_name = ".%s-%s.tmp" % (
        fact["record_id"],
        uuid.uuid4().hex,
    )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = None
    source_fd = None
    published_fd = None
    published_identity = None
    owns_temporary = False
    temporary_identity = None
    try:
        file_fd = os.open(
            temporary_name,
            flags,
            0o600,
            dir_fd=directory_fd,
        )
        owns_temporary = True
        opened_entry = os.fstat(file_fd)
        if not stat.S_ISREG(opened_entry.st_mode):
            raise ValidationError("temporary fact must be a regular file")
        temporary_identity = _entry_identity(opened_entry)
        _write_all(file_fd, data)
        os.fsync(file_fd)
        written_entry = os.fstat(file_fd)
        if (
            not stat.S_ISREG(written_entry.st_mode)
            or _entry_identity(written_entry) != temporary_identity
        ):
            raise ValidationError("temporary fact identity changed while writing")
        closing_fd = file_fd
        file_fd = None
        os.close(closing_fd)

        source_fd = _open_existing_regular(directory_fd, temporary_name)
        if _entry_identity(os.fstat(source_fd)) != temporary_identity:
            raise ValidationError("temporary fact identity changed before publish")

        try:
            _publish_held_file_no_clobber(
                source_fd,
                directory_fd,
                filename,
            )
            published = True
        except FileExistsError:
            existing_fd = _open_existing_regular(directory_fd, filename)
            try:
                existing = _read_all(existing_fd)
                if existing != data:
                    raise ValidationError(
                        "record_id conflicts with an existing immutable fact: %s"
                        % fact["record_id"]
                    )
                os.fsync(existing_fd)
            finally:
                os.close(existing_fd)
            published = False

        if published:
            published_fd = _open_existing_regular(directory_fd, filename)
            published_identity = _entry_identity(os.fstat(published_fd))
            published_data = _read_all(published_fd)
            if published_data != data:
                raise ValidationError(
                    "published fact content or identity changed"
                )
            os.fsync(published_fd)

        closing_fd = source_fd
        source_fd = None
        os.close(closing_fd)
        if published:
            os.fsync(directory_fd)
            if _name_identity(directory_fd, filename) != published_identity:
                raise ValidationError("published fact identity changed")
            closing_fd = published_fd
            published_fd = None
            os.close(closing_fd)
        if not _unlink_if_identity_matches(
            directory_fd,
            temporary_name,
            temporary_identity,
        ):
            raise ValidationError("temporary fact identity changed before cleanup")
        owns_temporary = False
        os.fsync(directory_fd)
        return published
    except BaseException:
        if file_fd is not None:
            closing_fd = file_fd
            file_fd = None
            try:
                os.close(closing_fd)
            except OSError:
                pass
        if source_fd is not None:
            closing_fd = source_fd
            source_fd = None
            try:
                os.close(closing_fd)
            except OSError:
                pass
        if published_fd is not None:
            closing_fd = published_fd
            published_fd = None
            try:
                os.close(closing_fd)
            except OSError:
                pass
        if owns_temporary:
            try:
                _unlink_if_identity_matches(
                    directory_fd,
                    temporary_name,
                    temporary_identity,
                )
            except OSError:
                pass
        if owns_temporary:
            try:
                os.fsync(directory_fd)
            except OSError:
                pass
        raise


def _replace_state_atomically(root_fd, state):
    data = _canonical_json(state)
    temporary_name = ".state-%s.tmp" % uuid.uuid4().hex
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = None
    try:
        file_fd = os.open(temporary_name, flags, 0o600, dir_fd=root_fd)
        _write_all(file_fd, data)
        os.fsync(file_fd)
        closing_fd = file_fd
        file_fd = None
        os.close(closing_fd)
        os.replace(
            temporary_name,
            "state.json",
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )
        os.fsync(root_fd)
    except BaseException:
        if file_fd is not None:
            closing_fd = file_fd
            file_fd = None
            try:
                os.close(closing_fd)
            except OSError:
                pass
        try:
            os.unlink(temporary_name, dir_fd=root_fd)
        except OSError:
            pass
        raise


def _cleanup_commit_descriptors(fact_directory_fd, lock_fd, root_fd):
    first_error = None

    def attempt(operation):
        nonlocal first_error
        try:
            operation()
        except BaseException as error:
            if first_error is None:
                first_error = error

    if fact_directory_fd is not None:
        attempt(lambda: os.close(fact_directory_fd))
    if lock_fd is not None:
        attempt(lambda: fcntl.flock(lock_fd, fcntl.LOCK_UN))
        attempt(lambda: os.close(lock_fd))
    if root_fd is not None:
        attempt(lambda: os.close(root_fd))
    if first_error is not None:
        raise first_error


def commit_fact(workspace, fact, now=None):
    """Publish one immutable fact and reconcile state under one exclusive lock."""
    validate_fact(fact)
    root_fd = open_workspace_descriptor(workspace)
    lock_fd = None
    fact_directory_fd = None
    body_failed = False
    try:
        lock_fd = _open_existing_regular(root_fd, ".workspace.lock", writable=True)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        snapshot = _read_workspace_snapshot_fd_unlocked(
            root_fd,
            require_consistent_state=False,
        )
        existing_by_record_id = {}
        for existing in snapshot.sessions + snapshot.plan_items:
            record_id = existing["record_id"]
            if record_id in existing_by_record_id:
                raise ValidationError("duplicate record_id: %s" % record_id)
            existing_by_record_id[record_id] = existing

        existing = existing_by_record_id.get(fact["record_id"])
        if existing is not None:
            if existing["record_type"] != fact["record_type"]:
                raise ValidationError(
                    "duplicate record_id: %s" % fact["record_id"]
                )
            if _canonical_json(existing) != _canonical_json(fact):
                raise ValidationError(
                    "record_id conflicts with an existing immutable fact: %s"
                    % fact["record_id"]
                )
        commit_time = now or datetime.now(timezone.utc).isoformat()
        prospective_sessions = list(snapshot.sessions)
        prospective_plan_items = list(snapshot.plan_items)
        if existing is None:
            prospective = (
                prospective_sessions
                if fact["record_type"] == "session"
                else prospective_plan_items
            )
            prospective.append(fact)
        candidate = reconcile_state(
            snapshot.state["student_id"],
            prospective_sessions,
            prospective_plan_items,
            previous_state=snapshot.state,
            now=commit_time,
        )
        validate_state(
            candidate,
            prospective_sessions,
            prospective_plan_items,
        )

        directory_name = (
            "sessions" if fact["record_type"] == "session" else "plan-items"
        )
        fact_directory_fd = _open_existing_directory(root_fd, directory_name)
        published = _publish_fact_no_clobber(fact_directory_fd, fact)

        snapshot = _read_workspace_snapshot_fd_unlocked(
            root_fd, require_consistent_state=False
        )
        candidate = reconcile_state(
            snapshot.state["student_id"],
            snapshot.sessions,
            snapshot.plan_items,
            previous_state=snapshot.state,
            now=commit_time,
        )
        validate_state(candidate, snapshot.sessions, snapshot.plan_items)
        if candidate != snapshot.state:
            _replace_state_atomically(root_fd, candidate)
        _read_workspace_snapshot_fd_unlocked(
            root_fd,
            require_consistent_state=True,
        )
        return published
    except BaseException:
        body_failed = True
        raise
    finally:
        closing_fact_directory_fd = fact_directory_fd
        fact_directory_fd = None
        closing_lock_fd = lock_fd
        lock_fd = None
        closing_root_fd = root_fd
        root_fd = None
        try:
            _cleanup_commit_descriptors(
                closing_fact_directory_fd,
                closing_lock_fd,
                closing_root_fd,
            )
        except BaseException:
            if not body_failed:
                raise


def _read_fact_file(path):
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ValidationError("cannot read fact file: %s" % error) from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError("fact file is not valid JSON: %s" % error) from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--fact-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        fact = _read_fact_file(args.fact_file)
        published = commit_fact(args.workspace, fact)
    except (OSError, ValidationError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    action = "COMMITTED" if published else "NO-OP"
    print("%s: %s" % (action, fact["record_id"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
