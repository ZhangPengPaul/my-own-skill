#!/usr/bin/env python3
"""Validate a study-coach workspace through held directory descriptors."""

import argparse
from dataclasses import dataclass
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import sys

from learning_state import (
    SUBJECTS,
    ValidationError,
    reconcile_state,
    require,
    validate_observation_fact,
    validate_plan_fact,
    validate_session_fact,
)


STUDENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
REQUIRED_REGULAR_FILES = ("profile.md", "state.json", ".workspace.lock")
REQUIRED_DIRECTORIES = ("sessions", "plan-items", "summaries", "materials", "observations")


@dataclass(frozen=True)
class WorkspaceSnapshot:
    state: dict
    sessions: tuple
    plan_items: tuple
    observations: tuple = ()


def _directory_flags():
    require(
        hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"),
        "descriptor-safe workspace access is unavailable",
    )
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _regular_flags(writable=False):
    require(
        hasattr(os, "O_NOFOLLOW"),
        "descriptor-safe workspace access is unavailable",
    )
    access = os.O_RDWR if writable else os.O_RDONLY
    return access | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _open_child(parent_fd, name, expected_directory, writable=False):
    expected = stat.S_ISDIR if expected_directory else stat.S_ISREG
    expected_label = "directory" if expected_directory else "regular file"
    try:
        entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise ValidationError(f"required child cannot be inspected: {name}: {error}") from error
    require(
        expected(entry.st_mode),
        f"required child has invalid type; expected {expected_label}: {name}",
    )
    flags = _directory_flags() if expected_directory else _regular_flags(writable)
    try:
        child_fd = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise ValidationError(f"required child cannot be opened: {name}: {error}") from error
    try:
        opened = os.fstat(child_fd)
        require(
            expected(opened.st_mode)
            and (opened.st_dev, opened.st_ino) == (entry.st_dev, entry.st_ino),
            f"required child identity changed: {name}",
        )
    except BaseException:
        os.close(child_fd)
        raise
    return child_fd


def _open_existing_regular(parent_fd, name, writable=False):
    """Open one verified regular child without following symlinks."""
    return _open_child(parent_fd, name, False, writable=writable)


def _open_existing_directory(parent_fd, name):
    """Open one verified directory child without following symlinks."""
    return _open_child(parent_fd, name, True)


def _read_all(file_fd):
    chunks = []
    while True:
        chunk = os.read(file_fd, 65536)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _read_utf8(file_fd, label):
    try:
        return _read_all(file_fd).decode("utf-8")
    except OSError as error:
        raise ValidationError(f"cannot read {label}: {error}") from error
    except UnicodeError as error:
        raise ValidationError(f"{label} is not valid UTF-8") from error


def _read_json_fd(file_fd, label):
    text = _read_utf8(file_fd, label)
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ValidationError(f"{label} is not valid JSON: {error}") from error


def _read_fact_directory(directory_fd, label, validator, record_type):
    try:
        names = sorted(os.listdir(directory_fd))
    except OSError as error:
        raise ValidationError(f"cannot enumerate {label}: {error}") from error
    facts = []
    for name in names:
        require(name.endswith(".json"), f"invalid non-JSON entry in {label}: {name}")
        file_fd = _open_existing_regular(directory_fd, name)
        body_failed = False
        try:
            fact = _read_json_fd(file_fd, f"{label}/{name}")
        except BaseException:
            body_failed = True
            raise
        finally:
            try:
                os.close(file_fd)
            except BaseException:
                if not body_failed:
                    raise
        require(
            isinstance(fact, dict),
            f"{label}/{name} must contain a JSON object",
        )
        require(
            fact.get("record_type") == record_type,
            f"record_type is invalid for {label}/{name}",
        )
        validator(fact)
        require(
            name == fact["record_id"] + ".json",
            f"fact filename must match record_id in {label}: {name}",
        )
        facts.append(fact)
    return tuple(facts)


def _close_all(file_descriptors):
    first_error = None
    for file_fd in file_descriptors:
        try:
            os.close(file_fd)
        except BaseException as error:
            if first_error is None:
                first_error = error
    if first_error is not None:
        raise first_error


def _cleanup_lock_descriptor(lock_fd):
    first_error = None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
    except BaseException as error:
        first_error = error
    try:
        os.close(lock_fd)
    except BaseException as error:
        if first_error is None:
            first_error = error
    if first_error is not None:
        raise first_error


def _cleanup_workspace_descriptors(root_fd, lock_fd, child_fds=()):
    """Attempt all cleanup operations and propagate the first cleanup failure."""
    first_error = None
    try:
        _close_all(child_fds)
    except BaseException as error:
        first_error = error
    if lock_fd is not None:
        try:
            _cleanup_lock_descriptor(lock_fd)
        except BaseException as error:
            if first_error is None:
                first_error = error
    try:
        os.close(root_fd)
    except BaseException as error:
        if first_error is None:
            first_error = error
    if first_error is not None:
        raise first_error


def _first_state_mismatch(state, candidate):
    ordered = ("schema_version", "student_id", "updated_at", "subjects", "process")
    for field in ordered:
        if state.get(field) != candidate.get(field):
            return field
    if set(state) != set(candidate):
        return "fields"
    return None


def validate_state(state, sessions, plan_items):
    """Validate schema-v2 shape, evidence references, and derived consistency."""
    require(isinstance(state, dict), "state must be an object")
    require(
        set(state) == {"schema_version", "student_id", "updated_at", "subjects", "process"},
        "state fields are invalid",
    )
    require(
        type(state.get("schema_version")) is int and state["schema_version"] == 2,
        "schema_version must be the integer 2",
    )
    require(
        isinstance(state.get("student_id"), str)
        and STUDENT_ID.fullmatch(state["student_id"]),
        "student_id must use lowercase letters, digits, and hyphens",
    )
    require(
        isinstance(state.get("updated_at"), str) and state["updated_at"].strip(),
        "updated_at must be an ISO-8601 timestamp",
    )
    require(isinstance(state.get("subjects"), dict), "subjects must be an object")
    require(set(state["subjects"]) == set(SUBJECTS), "subjects must contain exactly six subjects")
    require(isinstance(state.get("process"), dict), "process must be an object")

    candidate = reconcile_state(
        state["student_id"],
        list(sessions),
        list(plan_items),
        now=state["updated_at"],
    )
    mismatch = _first_state_mismatch(state, candidate)
    require(mismatch is None, f"state is not derived from active facts: {mismatch}")
    return state


def open_workspace_descriptor(workspace):
    """Resolve once and return a no-follow directory descriptor."""
    try:
        resolved = Path(workspace).resolve(strict=True)
        return os.open(os.fspath(resolved), _directory_flags())
    except (OSError, RuntimeError) as error:
        raise ValidationError(f"workspace cannot be opened: {error}") from error


def _read_workspace_snapshot_fd_unlocked(
    root_fd, require_consistent_state=True, include_observations=True
):
    """Read required children while the caller holds the workspace lock."""
    opened_files = []
    opened_directories = []
    body_failed = False
    try:
        for name in REQUIRED_REGULAR_FILES:
            opened_files.append((name, _open_existing_regular(root_fd, name)))
        directory_names = REQUIRED_DIRECTORIES
        if not include_observations:
            directory_names = tuple(
                name for name in REQUIRED_DIRECTORIES if name != "observations"
            )
        for name in directory_names:
            opened_directories.append((name, _open_existing_directory(root_fd, name)))

        file_descriptors = dict(opened_files)
        directory_descriptors = dict(opened_directories)
        _read_utf8(file_descriptors["profile.md"], "profile.md")
        state = _read_json_fd(file_descriptors["state.json"], "state.json")
        require(isinstance(state, dict), "state must be an object")
        sessions = _read_fact_directory(
            directory_descriptors["sessions"],
            "sessions",
            validate_session_fact,
            "session",
        )
        plan_items = _read_fact_directory(
            directory_descriptors["plan-items"],
            "plan-items",
            validate_plan_fact,
            "plan_item",
        )
        observations = ()
        if include_observations:
            observations = _read_fact_directory(
                directory_descriptors["observations"],
                "observations",
                validate_observation_fact,
                "interaction_observation",
            )
        record_ids = set()
        for fact in (*sessions, *plan_items, *observations):
            record_id = fact["record_id"]
            require(record_id not in record_ids, f"duplicate record_id: {record_id}")
            record_ids.add(record_id)
        if require_consistent_state:
            validate_state(state, sessions, plan_items)
        return WorkspaceSnapshot(state, sessions, plan_items, observations)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            _close_all(
                [file_fd for _, file_fd in opened_files]
                + [directory_fd for _, directory_fd in opened_directories]
            )
        except BaseException:
            if not body_failed:
                raise


def _validate_expected_student_id(expected_student_id):
    if expected_student_id is None:
        return None
    require(
        isinstance(expected_student_id, str)
        and STUDENT_ID.fullmatch(expected_student_id),
        "expected student_id is invalid",
    )
    return expected_student_id


def _read_workspace_student_id_fd_unlocked(root_fd):
    """Read only the state identity while the caller holds the workspace lock."""
    state_fd = _open_existing_regular(root_fd, "state.json")
    body_failed = False
    try:
        state = _read_json_fd(state_fd, "state.json")
        require(isinstance(state, dict), "state must be an object")
        student_id = state.get("student_id")
        require(
            isinstance(student_id, str) and STUDENT_ID.fullmatch(student_id),
            "student_id must use lowercase letters, digits, and hyphens",
        )
        return student_id
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            os.close(state_fd)
        except BaseException:
            if not body_failed:
                raise


def _require_expected_student_fd_unlocked(root_fd, expected_student_id):
    expected_student_id = _validate_expected_student_id(expected_student_id)
    if expected_student_id is None:
        return None
    require(
        _read_workspace_student_id_fd_unlocked(root_fd) == expected_student_id,
        "workspace state student_id does not match requested student_id",
    )
    return expected_student_id


def read_workspace_snapshot_fd(
    root_fd,
    require_consistent_state=True,
    expected_student_id=None,
):
    """Read one snapshot while holding the workspace's shared lock."""
    _validate_expected_student_id(expected_student_id)
    lock_fd = _open_existing_regular(root_fd, ".workspace.lock")
    body_failed = False
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_SH)
        _require_expected_student_fd_unlocked(root_fd, expected_student_id)
        snapshot = _read_workspace_snapshot_fd_unlocked(
            root_fd,
            require_consistent_state,
        )
        return _require_expected_student(snapshot, expected_student_id)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            _cleanup_lock_descriptor(lock_fd)
        except BaseException:
            if not body_failed:
                raise


def _require_expected_student(snapshot, expected_student_id):
    expected_student_id = _validate_expected_student_id(expected_student_id)
    if expected_student_id is None:
        return snapshot
    require(
        snapshot.state["student_id"] == expected_student_id,
        "workspace state student_id does not match requested student_id",
    )
    return snapshot


def read_workspace_snapshot(
    workspace,
    require_consistent_state=True,
    expected_student_id=None,
):
    """Return an immutable snapshot read from one held workspace descriptor."""
    _validate_expected_student_id(expected_student_id)
    root_fd = open_workspace_descriptor(workspace)
    body_failed = False
    try:
        # Legacy workspaces predate the observation store. Inspect and migrate
        # relative to the same held descriptor used for the final snapshot.
        try:
            os.stat("observations", dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            snapshot = migrate_workspace_fd(
                root_fd,
                expected_student_id=expected_student_id,
            )
        else:
            snapshot = read_workspace_snapshot_fd(
                root_fd,
                require_consistent_state,
                expected_student_id=expected_student_id,
            )
        return _require_expected_student(snapshot, expected_student_id)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            os.close(root_fd)
        except BaseException:
            if not body_failed:
                raise


def validate_workspace(workspace, expected_student_id=None):
    return read_workspace_snapshot(
        workspace,
        require_consistent_state=True,
        expected_student_id=expected_student_id,
    )


def validate_workspace_fd(root_fd, expected_student_id=None):
    return read_workspace_snapshot_fd(
        root_fd,
        require_consistent_state=True,
        expected_student_id=expected_student_id,
    )


def migrate_workspace(workspace, expected_student_id=None):
    """Add newly introduced workspace directories without replacing data."""
    _validate_expected_student_id(expected_student_id)
    root_fd = open_workspace_descriptor(workspace)
    body_failed = False
    try:
        migrate_workspace_fd(
            root_fd,
            expected_student_id=expected_student_id,
        )
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            os.close(root_fd)
        except BaseException:
            if not body_failed:
                raise


def migrate_workspace_fd(root_fd, expected_student_id=None):
    """Migrate one held workspace directory without resolving its path again."""
    _validate_expected_student_id(expected_student_id)
    lock_fd = None
    body_failed = False
    try:
        lock_fd = _open_existing_regular(root_fd, ".workspace.lock", writable=True)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _require_expected_student_fd_unlocked(root_fd, expected_student_id)
        try:
            os.stat("observations", dir_fd=root_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            directory_fd = _open_existing_directory(root_fd, "observations")
            os.close(directory_fd)
            if expected_student_id is None:
                return None
            snapshot = _read_workspace_snapshot_fd_unlocked(
                root_fd,
                require_consistent_state=False,
            )
            return _require_expected_student(snapshot, expected_student_id)

        legacy_snapshot = _read_workspace_snapshot_fd_unlocked(
            root_fd,
            require_consistent_state=True,
            include_observations=False,
        )
        _require_expected_student(legacy_snapshot, expected_student_id)
        try:
            os.mkdir("observations", mode=0o700, dir_fd=root_fd)
        except FileExistsError:
            # Re-open with O_NOFOLLOW and verify the existing entry is a directory.
            directory_fd = _open_existing_directory(root_fd, "observations")
            os.close(directory_fd)
        os.fsync(root_fd)
        return _require_expected_student(
            _read_workspace_snapshot_fd_unlocked(
                root_fd, require_consistent_state=True
            ),
            expected_student_id,
        )
    except BaseException:
        body_failed = True
        raise
    finally:
        if lock_fd is not None:
            try:
                _cleanup_lock_descriptor(lock_fd)
            except BaseException:
                if not body_failed:
                    raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--student-id", required=True)
    args = parser.parse_args()
    try:
        validate_workspace(args.workspace, expected_student_id=args.student_id)
    except (OSError, ValidationError) as error:
        print(f"INVALID: {error}", file=sys.stderr)
        return 1
    print(f"VALID: {args.workspace}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
