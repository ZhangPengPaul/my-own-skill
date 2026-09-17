"""Fault injection at OS boundaries keeps real workspace cleanup observable."""
from contextlib import ExitStack
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

import delete_observations  # noqa: E402
import validate_student_data  # noqa: E402
from learning_state import ValidationError  # noqa: E402
from tests.workspace_fixtures import create_workspace, interaction_observation  # noqa: E402


class WorkspaceCleanupTest(unittest.TestCase):
    def check_cleanup(self, operation, failures, primary=False):
        module = validate_student_data if operation == "migrate" else delete_observations
        action = module.migrate_workspace if operation == "migrate" else module.delete_observations
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "student-a"
            observations = [interaction_observation()] if operation == "delete" else []
            create_workspace(workspace, observations=observations)
            if operation == "migrate":
                (workspace / "observations").rmdir()
            descriptors = {}
            close_attempts = []
            unlock_attempts = []
            errors = {name: OSError("injected " + name) for name in failures}
            primary_error = ValidationError("injected primary failure")
            real_root = module.open_workspace_descriptor
            real_regular = module._open_existing_regular
            real_directory = module._open_existing_directory
            real_close = os.close
            real_flock = module.fcntl.flock
            real_fsync = os.fsync

            def open_root(path):
                fd = real_root(path)
                descriptors["root"] = fd
                return fd

            def open_regular(parent, name, **kwargs):
                fd = real_regular(parent, name, **kwargs)
                if name == ".workspace.lock" and "lock" not in descriptors:
                    descriptors["lock"] = fd
                return fd

            def open_directory(parent, name):
                fd = real_directory(parent, name)
                descriptors["directory"] = fd
                return fd

            def close(fd):
                close_attempts.append(fd)
                real_close(fd)
                for name, tracked in descriptors.items():
                    if fd == tracked and name in failures:
                        raise errors[name]

            def flock(fd, mode):
                real_flock(fd, mode)
                if fd == descriptors.get("lock") and mode == module.fcntl.LOCK_UN:
                    unlock_attempts.append(fd)
                    if "unlock" in failures:
                        raise errors["unlock"]

            def fsync(fd):
                if primary and fd == descriptors.get("root"):
                    raise primary_error
                return real_fsync(fd)

            ordered_errors = ("directory", "unlock", "lock", "root")
            expected = primary_error if primary else next(
                errors[name] for name in ordered_errors if name in failures
            )
            try:
                with ExitStack() as patches:
                    patches.enter_context(mock.patch.object(module, "open_workspace_descriptor", side_effect=open_root))
                    patches.enter_context(mock.patch.object(module, "_open_existing_regular", side_effect=open_regular))
                    # Snapshot reads use the validator's own helpers; only deletion's
                    # separately held observations directory is tracked here.
                    if operation == "delete":
                        patches.enter_context(mock.patch.object(module, "_open_existing_directory", side_effect=open_directory))
                    patches.enter_context(mock.patch.object(module.os, "close", side_effect=close))
                    patches.enter_context(mock.patch.object(module.fcntl, "flock", side_effect=flock))
                    if primary and operation == "delete":
                        patches.enter_context(mock.patch.object(module.os, "unlink", side_effect=primary_error))
                    elif primary:
                        patches.enter_context(mock.patch.object(module.os, "fsync", side_effect=fsync))
                    # A caller's active exception must not suppress cleanup errors.
                    try:
                        raise ValueError("outer caller context")
                    except ValueError:
                        with self.assertRaises(Exception) as raised:
                            action(workspace)
                    self.assertIs(expected, raised.exception)
                self.assertIn(descriptors["lock"], unlock_attempts)
                for fd in descriptors.values():
                    self.assertIn(fd, close_attempts)
                    with self.assertRaises(OSError):
                        os.fstat(fd)
            finally:
                for fd in set(descriptors.values()):
                    try:
                        real_close(fd)
                    except OSError:
                        pass

    def test_migration_attempts_all_cleanup_and_preserves_first_error(self):
        for failures in ({"unlock"}, {"lock"}, {"root"}, {"unlock", "lock", "root"}):
            with self.subTest(failures=failures):
                self.check_cleanup("migrate", failures)

    def test_migration_preserves_primary_error_over_cleanup_failures(self):
        self.check_cleanup("migrate", {"unlock", "lock", "root"}, primary=True)

    def test_deletion_attempts_all_cleanup_and_preserves_first_error(self):
        for failures in ({"directory"}, {"unlock"}, {"lock"}, {"root"},
                         {"directory", "unlock", "lock", "root"}):
            with self.subTest(failures=failures):
                self.check_cleanup("delete", failures)

    def test_deletion_preserves_primary_error_over_cleanup_failures(self):
        self.check_cleanup("delete", {"directory", "unlock", "lock", "root"}, primary=True)


if __name__ == "__main__":
    unittest.main()
