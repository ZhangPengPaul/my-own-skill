#!/usr/bin/env python3
"""Initialize a private local student workspace without overwriting data."""

import argparse
import ctypes
from datetime import datetime, timezone
import errno
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from validate_student_data import (
    STUDENT_ID,
    ValidationError,
    migrate_workspace_fd,
    validate_workspace_fd,
)


TEMPLATE = Path(__file__).resolve().parents[1] / "assets/student-workspace-template"
PROFILE_PLACEHOLDER = "__STUDENT_ID__"
DARWIN_RENAME_EXCL = 0x00000004
LINUX_AT_FDCWD = -100
LINUX_RENAME_NOREPLACE = 0x00000001
ROOT_ENVIRONMENT_VARIABLE = "SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT"
DEFAULT_ROOT_RELATIVE_PATH = Path(
    ".local/share/shanghai-high-school-study-coach/student-workspaces"
)


class WorkspaceExistsError(ValidationError):
    """Raised when create-only initialization finds an existing workspace."""


def resolve_root(explicit_root=None):
    """Choose the workspace root, preserving explicit relative-root support."""
    if explicit_root is not None:
        return Path(explicit_root)

    configured_root = os.environ.get(ROOT_ENVIRONMENT_VARIABLE)
    if configured_root is not None:
        if not configured_root:
            raise ValidationError("%s must not be empty" % ROOT_ENVIRONMENT_VARIABLE)
        root = Path(configured_root)
        if not root.is_absolute():
            raise ValidationError("%s must be an absolute path" % ROOT_ENVIRONMENT_VARIABLE)
        return root

    return Path.home() / DEFAULT_ROOT_RELATIVE_PATH


def _read_text_template(path):
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError as exc:
        raise ValidationError("template is not valid UTF-8: %s" % path.name) from exc


def _load_templates():
    profile = _read_text_template(TEMPLATE / "profile.md")
    if profile.count(PROFILE_PLACEHOLDER) != 1:
        raise ValidationError(
            "profile template must contain exactly one %s marker"
            % PROFILE_PLACEHOLDER
        )

    state_text = _read_text_template(TEMPLATE / "state.json")
    try:
        state = json.loads(state_text)
    except json.JSONDecodeError as exc:
        raise ValidationError("state template is not valid JSON: %s" % exc) from exc
    if not isinstance(state, dict):
        raise ValidationError("state template must contain a JSON object")

    return profile, state


def _raise_publish_error(error_number, destination):
    if error_number in (errno.EEXIST, errno.ENOTEMPTY):
        raise WorkspaceExistsError("workspace already exists: %s" % destination)
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


def _close_no_raise(file_descriptor):
    if file_descriptor is None:
        return
    try:
        os.close(file_descriptor)
    except BaseException:
        pass


def _directory_open_flags():
    if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
        raise OSError(errno.ENOTSUP, "descriptor-safe directory cleanup unavailable")
    return (
        os.O_RDONLY
        | os.O_DIRECTORY
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )


def _mkdir_at(parent_fd, name):
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    child_fd = os.open(name, _directory_open_flags(), dir_fd=parent_fd)
    try:
        opened = os.fstat(child_fd)
        if not stat.S_ISDIR(opened.st_mode):
            raise ValidationError("created child is not a directory: %s" % name)
        return child_fd
    except BaseException:
        _close_no_raise(child_fd)
        raise


def _write_new_file(parent_fd, name, content, mode=0o600):
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = os.open(name, flags, mode, dir_fd=parent_fd)
    body_failed = False
    try:
        data = content.encode("utf-8") if isinstance(content, str) else content
        offset = 0
        while offset < len(data):
            written = os.write(file_fd, data[offset:])
            if written == 0:
                raise OSError(errno.EIO, "write returned zero bytes")
            offset += written
        os.fsync(file_fd)
    except BaseException:
        body_failed = True
        raise
    finally:
        try:
            os.close(file_fd)
        except BaseException:
            if not body_failed:
                raise


def _same_identity(file_stat, identity, expected_type):
    return (
        expected_type(file_stat.st_mode)
        and file_stat.st_dev == identity[0]
        and file_stat.st_ino == identity[1]
    )


def _unlink_verified_file(parent_fd, name, identity):
    file_descriptor = None
    try:
        flags = (
            os.O_RDONLY
            | os.O_NOFOLLOW
            | getattr(os, "O_CLOEXEC", 0)
            | getattr(os, "O_NONBLOCK", 0)
        )
        file_descriptor = os.open(name, flags, dir_fd=parent_fd)
        opened = os.fstat(file_descriptor)
        if not _same_identity(opened, identity, stat.S_ISREG):
            return
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if _same_identity(current, identity, stat.S_ISREG):
            os.unlink(name, dir_fd=parent_fd)
    except OSError:
        return
    finally:
        _close_no_raise(file_descriptor)


def _clear_directory_fd(directory_fd):
    for name in os.listdir(directory_fd):
        try:
            entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except OSError:
            continue
        identity = (entry.st_dev, entry.st_ino)
        if stat.S_ISREG(entry.st_mode):
            _unlink_verified_file(directory_fd, name, identity)
        elif stat.S_ISDIR(entry.st_mode):
            _remove_verified_directory(directory_fd, name, identity)


def _remove_verified_directory(parent_fd, name, identity):
    directory_fd = None
    try:
        directory_fd = os.open(
            name, _directory_open_flags(), dir_fd=parent_fd
        )
        opened = os.fstat(directory_fd)
        if not _same_identity(opened, identity, stat.S_ISDIR):
            return
        _clear_directory_fd(directory_fd)
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if _same_identity(current, identity, stat.S_ISDIR):
            os.rmdir(name, dir_fd=parent_fd)
    except OSError:
        return
    finally:
        _close_no_raise(directory_fd)


def _require_named_identity(
    root_fd, path, temporary_fd, identity, operation
):
    try:
        held = os.fstat(temporary_fd)
        named = os.stat(path.name, dir_fd=root_fd, follow_symlinks=False)
        path_stat = os.stat(os.fspath(path), follow_symlinks=False)
    except OSError as exc:
        raise ValidationError(
            "temporary workspace identity changed %s" % operation
        ) from exc
    if (
        not _same_identity(held, identity, stat.S_ISDIR)
        or not _same_identity(named, identity, stat.S_ISDIR)
        or not _same_identity(path_stat, identity, stat.S_ISDIR)
    ):
        raise ValidationError("temporary workspace identity changed %s" % operation)


def _publish_verified_workspace(
    root_fd, temporary, destination, temporary_fd, identity
):
    _require_named_identity(
        root_fd,
        temporary,
        temporary_fd,
        identity,
        "before publication",
    )
    os.fsync(temporary_fd)
    _publish_no_replace(temporary, destination)
    try:
        _require_named_identity(
            root_fd,
            destination,
            temporary_fd,
            identity,
            "after publication",
        )
    except ValidationError as identity_error:
        try:
            _publish_no_replace(destination, temporary)
            os.fsync(root_fd)
        except BaseException as rollback_error:
            raise ValidationError(
                "published workspace identity mismatch; manual inspection required: %s"
                % destination
            ) from rollback_error
        raise ValidationError(
            "temporary workspace identity changed during publication"
        ) from identity_error
    os.fsync(root_fd)


def _cleanup_owned_temporary(
    root_fd, temporary_fd, identity, candidate_names
):
    try:
        held = os.fstat(temporary_fd)
        if not _same_identity(held, identity, stat.S_ISDIR):
            return

        _clear_directory_fd(temporary_fd)
        for name in dict.fromkeys(candidate_names):
            try:
                current = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
            except OSError:
                continue
            if _same_identity(current, identity, stat.S_ISDIR):
                try:
                    os.rmdir(name, dir_fd=root_fd)
                except OSError:
                    continue
        os.fsync(root_fd)
    except BaseException:
        return


def _raise_if_destination_exists(root_fd, student_id, destination):
    try:
        entry = os.stat(student_id, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(entry.st_mode):
        raise ValidationError(
            "workspace path must not be a symbolic link: %s" % destination
        )
    raise WorkspaceExistsError("workspace already exists: %s" % destination)


def _open_existing_workspace(root_fd, student_id, destination):
    try:
        entry = os.stat(student_id, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError as exc:
        raise ValidationError("workspace disappeared: %s" % destination) from exc
    if stat.S_ISLNK(entry.st_mode):
        raise ValidationError(
            "workspace path must not be a symbolic link: %s" % destination
        )
    if not stat.S_ISDIR(entry.st_mode):
        raise ValidationError("workspace path must be a directory: %s" % destination)

    try:
        workspace_fd = os.open(
            student_id, _directory_open_flags(), dir_fd=root_fd
        )
    except OSError as exc:
        raise ValidationError("workspace cannot be opened: %s" % destination) from exc
    try:
        opened = os.fstat(workspace_fd)
        if not _same_identity(opened, (entry.st_dev, entry.st_ino), stat.S_ISDIR):
            raise ValidationError("workspace identity changed: %s" % destination)
        return workspace_fd
    except BaseException:
        _close_no_raise(workspace_fd)
        raise


def _migrate_legacy_workspace_fd(workspace_fd, student_id):
    try:
        os.stat("observations", dir_fd=workspace_fd, follow_symlinks=False)
    except FileNotFoundError:
        return migrate_workspace_fd(workspace_fd, student_id)
    return None


def _prepare_root(root):
    root = Path(root)
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValidationError("workspace root must be a directory")
    return root


def _verify_workspace_identity(root_fd, student_id, destination, identity):
    workspace_fd = _open_existing_workspace(root_fd, student_id, destination)
    try:
        held = os.fstat(workspace_fd)
        if not _same_identity(held, identity, stat.S_ISDIR):
            raise ValidationError("workspace identity changed: %s" % destination)
        current = os.stat(student_id, dir_fd=root_fd, follow_symlinks=False)
        if not _same_identity(current, identity, stat.S_ISDIR):
            raise ValidationError("workspace identity changed: %s" % destination)
    finally:
        _close_no_raise(workspace_fd)


def initialize(root, student_id):
    if not STUDENT_ID.fullmatch(student_id):
        raise ValidationError("invalid student_id")
    root = _prepare_root(root)
    root_fd = os.open(os.fspath(root), _directory_open_flags())
    try:
        destination, _ = _initialize_with_root_fd(root, root_fd, student_id)
        return destination
    finally:
        _close_no_raise(root_fd)


def _initialize_with_root_fd(root, root_fd, student_id):
    destination = root / student_id
    _raise_if_destination_exists(root_fd, student_id, destination)
    profile, state = _load_templates()

    reserve_fd = None
    temporary = None
    temporary_fd = None
    identity = None
    try:
        flags = _directory_open_flags()
        reserve_fd = os.dup(root_fd)

        temporary = Path(
            tempfile.mkdtemp(prefix=".%s-" % student_id, dir=str(root))
        )
        named = os.stat(
            temporary.name,
            dir_fd=root_fd,
            follow_symlinks=False,
        )
        if not stat.S_ISDIR(named.st_mode):
            raise ValidationError("temporary workspace is not a directory")
        identity = (named.st_dev, named.st_ino)
        try:
            temporary_fd = os.open(temporary.name, flags, dir_fd=root_fd)
        except OSError as error:
            if (
                error.errno not in (errno.EMFILE, errno.ENFILE)
                or reserve_fd is None
            ):
                raise
            closing_fd = reserve_fd
            reserve_fd = None
            _close_no_raise(closing_fd)
            temporary_fd = os.open(temporary.name, flags, dir_fd=root_fd)
        if reserve_fd is not None:
            closing_fd = reserve_fd
            reserve_fd = None
            _close_no_raise(closing_fd)
        created = os.fstat(temporary_fd)
        if not _same_identity(created, identity, stat.S_ISDIR):
            raise ValidationError("temporary workspace identity changed after open")

        _require_named_identity(
            root_fd,
            temporary,
            temporary_fd,
            identity,
            "before workspace construction",
        )
        for directory in ("sessions", "plan-items", "summaries", "materials", "observations"):
            child_fd = _mkdir_at(temporary_fd, directory)
            os.close(child_fd)
        _write_new_file(
            temporary_fd,
            "profile.md",
            profile.replace(PROFILE_PLACEHOLDER, student_id),
        )
        state["student_id"] = student_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_new_file(
            temporary_fd,
            "state.json",
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        )
        _write_new_file(temporary_fd, ".workspace.lock", b"")

        _require_named_identity(
            root_fd,
            temporary,
            temporary_fd,
            identity,
            "after workspace construction",
        )
        _require_named_identity(
            root_fd,
            temporary,
            temporary_fd,
            identity,
            "before validation",
        )
        validate_workspace_fd(temporary_fd)
        _require_named_identity(
            root_fd,
            temporary,
            temporary_fd,
            identity,
            "after validation",
        )
        _publish_verified_workspace(
            root_fd, temporary, destination, temporary_fd, identity
        )
    except BaseException:
        if root_fd is not None and temporary_fd is not None and identity is not None:
            candidate_names = [destination.name]
            if temporary is not None:
                candidate_names.insert(0, temporary.name)
            _cleanup_owned_temporary(
                root_fd, temporary_fd, identity, candidate_names
            )
        raise
    finally:
        _close_no_raise(reserve_fd)
        _close_no_raise(temporary_fd)
    return destination, identity


def ensure_workspace_with_status(root, student_id):
    """Return the canonical workspace and whether it was created, migrated, or existing."""
    if not STUDENT_ID.fullmatch(student_id):
        raise ValidationError("invalid student_id")
    root = _prepare_root(root)
    root_fd = os.open(os.fspath(root), _directory_open_flags())
    destination = root / student_id
    workspace_fd = None
    try:
        try:
            destination, created_identity = _initialize_with_root_fd(
                root, root_fd, student_id
            )
        except WorkspaceExistsError:
            workspace_fd = None
            try:
                _raise_if_destination_exists(root_fd, student_id, destination)
            except WorkspaceExistsError:
                workspace_fd = _open_existing_workspace(
                    root_fd, student_id, destination
                )
                snapshot = _migrate_legacy_workspace_fd(
                    workspace_fd, student_id
                )
                status = "migrated" if snapshot is not None else "existing"
                if snapshot is None:
                    snapshot = validate_workspace_fd(
                        workspace_fd,
                        expected_student_id=student_id,
                    )
                if snapshot.state["student_id"] != student_id:
                    raise ValidationError(
                        "workspace state student_id does not match requested student_id"
                    )
                held = os.fstat(workspace_fd)
                current = os.stat(
                    student_id, dir_fd=root_fd, follow_symlinks=False
                )
                if not _same_identity(
                    current, (held.st_dev, held.st_ino), stat.S_ISDIR
                ):
                    raise ValidationError("workspace identity changed: %s" % destination)
                return destination, status
            raise ValidationError("workspace disappeared: %s" % destination)

        _verify_workspace_identity(
            root_fd, student_id, destination, created_identity
        )
        return destination, "created"
    finally:
        _close_no_raise(workspace_fd)
        _close_no_raise(root_fd)


def ensure_workspace(root, student_id):
    """Create a workspace or validate the existing workspace without changing it."""
    destination, _ = ensure_workspace_with_status(root, student_id)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id")
    parser.add_argument("--root", type=Path)
    parser.add_argument("--ensure", action="store_true")
    parser.add_argument("--report-status", action="store_true")
    args = parser.parse_args()
    if args.report_status and not args.ensure:
        parser.error("--report-status requires --ensure")
    try:
        root = resolve_root(args.root)
        if args.ensure:
            if args.report_status:
                destination, status = ensure_workspace_with_status(
                    root, args.student_id
                )
            else:
                destination = ensure_workspace(root, args.student_id)
        else:
            destination = initialize(root, args.student_id)
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    if args.report_status:
        print(
            json.dumps(
                {"status": status, "workspace": str(destination)},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    else:
        print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
