#!/usr/bin/env python3
"""Delete local interaction observations matching explicit filters."""

import argparse
import fcntl
import os
from pathlib import Path
import sys

from learning_state import ValidationError, parse_timestamp
from validate_student_data import (
    _cleanup_workspace_descriptors,
    _open_existing_directory,
    _read_workspace_snapshot_fd_unlocked,
    _open_existing_regular,
    _require_expected_student,
    _require_expected_student_fd_unlocked,
    _validate_expected_student_id,
    migrate_workspace_fd,
    open_workspace_descriptor,
)


def _opened_observation_identity(directory_fd, name):
    file_fd = _open_existing_regular(directory_fd, name)
    body_failed = False
    try:
        entry = os.fstat(file_fd)
        return (entry.st_dev, entry.st_ino)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            os.close(file_fd)
        except BaseException:
            if not body_failed:
                raise


def _capture_observation_identities(directory_fd):
    try:
        names = sorted(os.listdir(directory_fd))
    except OSError as error:
        raise ValidationError(
            "cannot enumerate observations: %s" % error
        ) from error
    return {
        name: _opened_observation_identity(directory_fd, name)
        for name in names
    }


def _require_observation_identity(directory_fd, name, expected_identity):
    try:
        current_identity = _opened_observation_identity(directory_fd, name)
    except (OSError, ValidationError) as error:
        raise ValidationError(
            "observation identity changed: %s" % name
        ) from error
    if expected_identity is None or current_identity != expected_identity:
        raise ValidationError("observation identity changed: %s" % name)


def delete_observations(
    workspace,
    subject=None,
    target_id=None,
    before=None,
    expected_student_id=None,
):
    """Delete matching observation fact files and return the number removed."""
    _validate_expected_student_id(expected_student_id)
    workspace = Path(workspace)
    if before is not None:
        before_value = parse_timestamp(before, "before")
    else:
        before_value = None
    root_fd = open_workspace_descriptor(workspace)
    lock_fd = None
    directory_fd = None
    body_failed = False
    try:
        migrate_workspace_fd(root_fd, expected_student_id=expected_student_id)
        lock_fd = _open_existing_regular(root_fd, ".workspace.lock", writable=True)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _require_expected_student_fd_unlocked(root_fd, expected_student_id)
        directory_fd = _open_existing_directory(root_fd, "observations")
        observation_identities = _capture_observation_identities(directory_fd)
        snapshot = _read_workspace_snapshot_fd_unlocked(root_fd, True)
        _require_expected_student(snapshot, expected_student_id)
        candidate_names = []
        for observation in snapshot.observations:
            if subject is not None and observation["subject"] != subject:
                continue
            if target_id is not None and observation["target_id"] != target_id:
                continue
            if before_value is not None and not (
                parse_timestamp(observation["occurred_at"], "occurred_at")
                < before_value
            ):
                continue
            candidate_names.append(observation["record_id"] + ".json")

        for name in candidate_names:
            _require_observation_identity(
                directory_fd,
                name,
                observation_identities.get(name),
            )

        for name in candidate_names:
            _require_observation_identity(
                directory_fd,
                name,
                observation_identities[name],
            )
            os.unlink(name, dir_fd=directory_fd)
        if candidate_names:
            os.fsync(directory_fd)
        return len(candidate_names)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            _cleanup_workspace_descriptors(
                root_fd, lock_fd,
                (directory_fd,) if directory_fd is not None else (),
            )
        except BaseException:
            if not body_failed:
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--subject")
    parser.add_argument("--target-id")
    parser.add_argument("--before")
    parser.add_argument("--student-id", required=True)
    args = parser.parse_args()
    try:
        removed = delete_observations(
            args.workspace,
            subject=args.subject,
            target_id=args.target_id,
            before=args.before,
            expected_student_id=args.student_id,
        )
    except (OSError, ValidationError, ValueError) as error:
        print("ERROR: %s" % error, file=sys.stderr)
        return 1
    print(removed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
