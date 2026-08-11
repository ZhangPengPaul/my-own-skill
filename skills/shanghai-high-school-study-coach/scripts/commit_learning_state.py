#!/usr/bin/env python3
"""Commit one immutable learning fact and reconcile derived state."""

import argparse
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
    open_workspace_descriptor,
    read_workspace_snapshot_fd,
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
    if (
        expected_identity is None
        or _name_identity(directory_fd, name) != expected_identity
    ):
        return False
    os.unlink(name, dir_fd=directory_fd)
    return True


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
    owns_temporary = False
    temporary_identity = None
    invalid_final_identity = None
    final_link_matches_temporary = False
    final_link_persisted = False
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
        os.close(file_fd)
        file_fd = None

        if _name_identity(directory_fd, temporary_name) != temporary_identity:
            raise ValidationError("temporary fact identity changed before publish")

        try:
            os.link(
                temporary_name,
                filename,
                src_dir_fd=directory_fd,
                dst_dir_fd=directory_fd,
                follow_symlinks=False,
            )
            final_identity = _name_identity(directory_fd, filename)
            if final_identity != temporary_identity:
                invalid_final_identity = final_identity
                raise ValidationError("published fact identity changed during link")
            final_link_matches_temporary = True
            os.fsync(directory_fd)
            final_link_persisted = True
            published = True
        except FileExistsError:
            existing_fd = _open_existing_regular(directory_fd, filename)
            try:
                existing = _read_all(existing_fd)
            finally:
                os.close(existing_fd)
            if existing != data:
                raise ValidationError(
                    "record_id conflicts with an existing immutable fact: %s"
                    % fact["record_id"]
                )
            published = False

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
            try:
                os.close(file_fd)
            except OSError:
                pass
        directory_changed = False
        if invalid_final_identity is not None:
            try:
                directory_changed = _unlink_if_identity_matches(
                    directory_fd,
                    filename,
                    invalid_final_identity,
                )
            except OSError:
                pass
        if owns_temporary and (
            not final_link_matches_temporary or final_link_persisted
        ):
            try:
                directory_changed = (
                    _unlink_if_identity_matches(
                        directory_fd,
                        temporary_name,
                        temporary_identity,
                    )
                    or directory_changed
                )
            except OSError:
                pass
        if directory_changed:
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
        os.close(file_fd)
        file_fd = None
        os.replace(
            temporary_name,
            "state.json",
            src_dir_fd=root_fd,
            dst_dir_fd=root_fd,
        )
        os.fsync(root_fd)
    except BaseException:
        if file_fd is not None:
            try:
                os.close(file_fd)
            except OSError:
                pass
        try:
            os.unlink(temporary_name, dir_fd=root_fd)
        except OSError:
            pass
        raise


def commit_fact(workspace, fact, now=None):
    """Publish one immutable fact and reconcile state under one exclusive lock."""
    validate_fact(fact)
    root_fd = open_workspace_descriptor(workspace)
    lock_fd = None
    fact_directory_fd = None
    try:
        lock_fd = _open_existing_regular(root_fd, ".workspace.lock", writable=True)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        snapshot = read_workspace_snapshot_fd(
            root_fd,
            require_consistent_state=False,
        )
        directory_name = (
            "sessions" if fact["record_type"] == "session" else "plan-items"
        )
        other_facts = (
            snapshot.plan_items
            if fact["record_type"] == "session"
            else snapshot.sessions
        )
        if any(
            existing["record_id"] == fact["record_id"]
            for existing in other_facts
        ):
            raise ValidationError(
                "duplicate record_id: %s" % fact["record_id"]
            )
        fact_directory_fd = _open_existing_directory(root_fd, directory_name)
        published = _publish_fact_no_clobber(fact_directory_fd, fact)

        snapshot = read_workspace_snapshot_fd(
            root_fd, require_consistent_state=False
        )
        candidate = reconcile_state(
            snapshot.state["student_id"],
            snapshot.sessions,
            snapshot.plan_items,
            previous_state=snapshot.state,
            now=now or datetime.now(timezone.utc).isoformat(),
        )
        validate_state(candidate, snapshot.sessions, snapshot.plan_items)
        if candidate != snapshot.state:
            _replace_state_atomically(root_fd, candidate)
        read_workspace_snapshot_fd(root_fd, require_consistent_state=True)
        return published
    finally:
        if fact_directory_fd is not None:
            os.close(fact_directory_fd)
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)
        os.close(root_fd)


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
