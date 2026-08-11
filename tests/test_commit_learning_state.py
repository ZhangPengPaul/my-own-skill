import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
INIT = SCRIPTS / "init_student.py"
COMMIT = SCRIPTS / "commit_learning_state.py"
sys.path.insert(0, str(SCRIPTS))

import commit_learning_state  # noqa: E402
from commit_learning_state import commit_fact  # noqa: E402
from validate_student_data import ValidationError, validate_workspace  # noqa: E402
from tests.workspace_fixtures import (  # noqa: E402
    knowledge_observation,
    plan_fact,
    session_fact,
)


NOW = "2026-08-06T12:00:00+00:00"
LATER = "2026-08-06T13:00:00+00:00"


class CommitLearningStateTest(unittest.TestCase):
    def initialize_workspace(self, root):
        result = subprocess.run(
            [sys.executable, str(INIT), "--root", str(root), "student-a"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return root / "student-a"

    def run_cli(self, workspace, fact):
        record_id = fact.get("record_id", "invalid-fact")
        fact_file = workspace.parent / (record_id + "-input.json")
        fact_file.write_text(json.dumps(fact, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(COMMIT),
                str(workspace),
                "--fact-file",
                str(fact_file),
            ],
            capture_output=True,
            text=True,
        )

    def test_session_commit_publishes_fact_and_reconciles_state(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))

            published = commit_fact(workspace, fact, now=NOW)
            snapshot = validate_workspace(workspace)

            self.assertTrue(published)
            self.assertTrue(
                (workspace / "sessions/record-session-001.json").is_file()
            )
            self.assertEqual(1, snapshot.state["process"]["recorded_sessions"])
            unit = snapshot.state["subjects"]["mathematics"]["knowledge_units"][
                "mathematics.geometry.dihedral-angle"
            ]
            self.assertEqual("suspected_gap", unit["status"])

    def test_implicit_commit_time_is_computed_once_and_reused(self):
        fact = session_fact(observations=[knowledge_observation()])
        first_clock_value = mock.Mock()
        first_clock_value.isoformat.return_value = NOW
        second_clock_value = mock.Mock()
        second_clock_value.isoformat.return_value = LATER
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))

            with mock.patch.object(
                commit_learning_state,
                "datetime",
            ) as datetime_type, mock.patch.object(
                commit_learning_state,
                "reconcile_state",
                wraps=commit_learning_state.reconcile_state,
            ) as reconcile:
                datetime_type.now.side_effect = [
                    first_clock_value,
                    second_clock_value,
                ]
                commit_fact(workspace, fact)

            datetime_type.now.assert_called_once_with(
                commit_learning_state.timezone.utc
            )
            self.assertEqual(2, reconcile.call_count)
            self.assertEqual(
                [NOW, NOW],
                [call.kwargs["now"] for call in reconcile.call_args_list],
            )

    def test_completed_plan_revision_requires_and_counts_matching_evidence(self):
        session = session_fact(observations=[knowledge_observation()])
        pending = plan_fact()
        completed = plan_fact(
            record_id="record-plan-002",
            supersedes_record_id="record-plan-001",
            status="completed",
            completion_evidence_id="evidence-001",
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))

            commit_fact(workspace, session, now=NOW)
            commit_fact(workspace, pending, now=NOW)
            commit_fact(workspace, completed, now=NOW)
            snapshot = validate_workspace(workspace)

            self.assertEqual(1, snapshot.state["process"]["completed_plan_items"])
            self.assertEqual(
                {"record-plan-001.json", "record-plan-002.json"},
                {path.name for path in (workspace / "plan-items").iterdir()},
            )

    def test_identical_record_retry_is_noop(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            first = self.run_cli(workspace, fact)
            self.assertEqual(0, first.returncode, first.stderr)
            before = validate_workspace(workspace).state["updated_at"]

            second = self.run_cli(workspace, fact)
            after = validate_workspace(workspace).state["updated_at"]

            self.assertEqual(0, second.returncode, second.stderr)
            self.assertEqual("COMMITTED: record-session-001\n", first.stdout)
            self.assertEqual("NO-OP: record-session-001\n", second.stdout)
            self.assertEqual(before, after)
            self.assertEqual(
                ["record-session-001.json"],
                sorted(path.name for path in (workspace / "sessions").iterdir()),
            )

    def test_conflicting_record_reuse_is_rejected(self):
        original = session_fact(observations=[knowledge_observation()])
        conflicting = session_fact(
            student_attempt="different fictional attempt",
            observations=[knowledge_observation()],
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, original, now=NOW)
            fact_path = workspace / "sessions/record-session-001.json"
            original_bytes = fact_path.read_bytes()
            state_bytes = (workspace / "state.json").read_bytes()

            with mock.patch.object(
                commit_learning_state,
                "_publish_fact_no_clobber",
                wraps=commit_learning_state._publish_fact_no_clobber,
            ) as publish:
                with self.assertRaisesRegex(ValidationError, "record_id|conflict"):
                    commit_fact(workspace, conflicting, now=LATER)

            publish.assert_not_called()
            self.assertEqual(original_bytes, fact_path.read_bytes())
            self.assertEqual(state_bytes, (workspace / "state.json").read_bytes())

    def test_interrupted_fact_write_never_exposes_final_name(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            fact_directory = workspace / "sessions"
            final_path = fact_directory / "record-session-001.json"
            temporary_names = []

            def interrupt_fact_write(file_fd, data):
                written = os.write(file_fd, data[: len(data) // 2])
                self.assertGreater(written, 0)
                self.assertLess(written, len(data))
                self.assertFalse(final_path.exists())
                names = [path.name for path in fact_directory.iterdir()]
                self.assertEqual(1, len(names))
                self.assertRegex(
                    names[0],
                    r"^\.record-session-001-[0-9a-f]{32}\.tmp$",
                )
                temporary_names.extend(names)
                raise OSError("fictional interrupted fact write")

            with mock.patch.object(
                commit_learning_state,
                "_write_all",
                side_effect=interrupt_fact_write,
            ):
                with self.assertRaisesRegex(OSError, "interrupted fact write"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertFalse(final_path.exists())
            self.assertTrue(temporary_names)
            self.assertEqual(
                [],
                [
                    name
                    for name in temporary_names
                    if (fact_directory / name).exists()
                ],
            )

    def test_successful_publish_fsyncs_final_before_directory_and_cleanup(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            fact_directory = Path(tmp)
            directory_fd = os.open(
                fact_directory,
                os.O_RDONLY | os.O_DIRECTORY,
            )
            events = []
            real_fsync = os.fsync
            real_unlink = os.unlink
            real_publish = commit_learning_state._publish_held_file_no_clobber
            final_path = fact_directory / "record-session-001.json"

            def tracked_publish(source_fd, target_directory_fd, filename):
                result = real_publish(source_fd, target_directory_fd, filename)
                events.append("publish-final")
                return result

            def tracked_fsync(file_fd):
                result = real_fsync(file_fd)
                if file_fd == directory_fd:
                    events.append("fsync-directory")
                elif final_path.exists():
                    final_entry = final_path.stat()
                    synced_entry = os.fstat(file_fd)
                    if (
                        synced_entry.st_dev,
                        synced_entry.st_ino,
                    ) == (
                        final_entry.st_dev,
                        final_entry.st_ino,
                    ):
                        events.append("fsync-final")
                return result

            def tracked_unlink(path, *args, **kwargs):
                result = real_unlink(path, *args, **kwargs)
                if kwargs.get("dir_fd") == directory_fd:
                    events.append("unlink-temporary")
                return result

            try:
                with mock.patch.object(
                    commit_learning_state,
                    "_publish_held_file_no_clobber",
                    side_effect=tracked_publish,
                ), mock.patch.object(
                    commit_learning_state.os,
                    "fsync",
                    side_effect=tracked_fsync,
                ), mock.patch.object(
                    commit_learning_state.os,
                    "unlink",
                    side_effect=tracked_unlink,
                ):
                    published = commit_learning_state._publish_fact_no_clobber(
                        directory_fd,
                        fact,
                    )
            finally:
                os.close(directory_fd)

            self.assertTrue(published)
            self.assertEqual(
                [
                    "publish-final",
                    "fsync-final",
                    "fsync-directory",
                    "unlink-temporary",
                    "fsync-directory",
                ],
                events,
            )
            self.assertEqual(
                commit_learning_state._canonical_json(fact),
                (fact_directory / "record-session-001.json").read_bytes(),
            )

    def test_post_link_directory_fsync_failure_is_recoverable(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            fact_directory = workspace / "sessions"
            directory_entry = fact_directory.stat()
            directory_identity = (
                directory_entry.st_dev,
                directory_entry.st_ino,
            )
            old_state = (workspace / "state.json").read_bytes()
            real_fsync = os.fsync
            failed_directory_fsync = False

            def fail_first_fact_directory_fsync(file_fd):
                nonlocal failed_directory_fsync
                entry = os.fstat(file_fd)
                if (
                    not failed_directory_fsync
                    and (entry.st_dev, entry.st_ino) == directory_identity
                ):
                    failed_directory_fsync = True
                    raise OSError("fictional post-link directory fsync failure")
                return real_fsync(file_fd)

            with mock.patch.object(
                commit_learning_state.os,
                "fsync",
                side_effect=fail_first_fact_directory_fsync,
            ):
                with self.assertRaisesRegex(OSError, "post-link directory fsync"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertTrue(failed_directory_fsync)
            final_path = fact_directory / "record-session-001.json"
            self.assertEqual(
                commit_learning_state._canonical_json(fact),
                final_path.read_bytes(),
            )
            self.assertEqual(
                ["record-session-001.json"],
                sorted(path.name for path in fact_directory.iterdir()),
            )
            self.assertEqual(old_state, (workspace / "state.json").read_bytes())

            published = commit_fact(workspace, fact, now=LATER)
            snapshot = validate_workspace(workspace)

            self.assertFalse(published)
            self.assertEqual(1, snapshot.state["process"]["recorded_sessions"])
            self.assertEqual(LATER, snapshot.state["updated_at"])
            self.assertEqual(
                ["record-session-001.json"],
                sorted(path.name for path in fact_directory.iterdir()),
            )

    def test_final_fsync_failure_retry_fsyncs_existing_final(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            fact_directory = Path(tmp)
            directory_fd = os.open(
                fact_directory,
                os.O_RDONLY | os.O_DIRECTORY,
            )
            final_path = fact_directory / "record-session-001.json"
            real_fsync = os.fsync
            failed_final_fsync = False

            def fail_first_final_fsync(file_fd):
                nonlocal failed_final_fsync
                entry = os.fstat(file_fd)
                if final_path.exists():
                    final_entry = final_path.stat()
                    if (
                        not failed_final_fsync
                        and (entry.st_dev, entry.st_ino)
                        == (final_entry.st_dev, final_entry.st_ino)
                    ):
                        failed_final_fsync = True
                        raise OSError("fictional final inode fsync failure")
                return real_fsync(file_fd)

            try:
                with mock.patch.object(
                    commit_learning_state.os,
                    "fsync",
                    side_effect=fail_first_final_fsync,
                ):
                    with self.assertRaisesRegex(OSError, "final inode fsync"):
                        commit_learning_state._publish_fact_no_clobber(
                            directory_fd,
                            fact,
                        )

                retried_final_fsyncs = 0

                def track_retry_final_fsync(file_fd):
                    nonlocal retried_final_fsyncs
                    entry = os.fstat(file_fd)
                    final_entry = final_path.stat()
                    if (entry.st_dev, entry.st_ino) == (
                        final_entry.st_dev,
                        final_entry.st_ino,
                    ):
                        retried_final_fsyncs += 1
                    return real_fsync(file_fd)

                with mock.patch.object(
                    commit_learning_state.os,
                    "fsync",
                    side_effect=track_retry_final_fsync,
                ):
                    published = commit_learning_state._publish_fact_no_clobber(
                        directory_fd,
                        fact,
                    )
            finally:
                os.close(directory_fd)

            self.assertTrue(failed_final_fsync)
            self.assertFalse(published)
            self.assertEqual(1, retried_final_fsyncs)
            self.assertEqual(
                ["record-session-001.json"],
                sorted(path.name for path in fact_directory.iterdir()),
            )

    def test_replaced_temporary_name_is_neither_published_nor_removed(self):
        fact = session_fact(observations=[knowledge_observation()])
        replacement = b"fictional replacement inode\n"
        with tempfile.TemporaryDirectory() as tmp:
            fact_directory = Path(tmp)
            directory_fd = os.open(
                fact_directory,
                os.O_RDONLY | os.O_DIRECTORY,
            )
            real_write_all = commit_learning_state._write_all
            replaced_names = []

            def write_then_replace_temporary(file_fd, data):
                real_write_all(file_fd, data)
                names = [path.name for path in fact_directory.iterdir()]
                self.assertEqual(1, len(names))
                temporary_path = fact_directory / names[0]
                temporary_path.unlink()
                temporary_path.write_bytes(replacement)
                replaced_names.extend(names)

            try:
                with mock.patch.object(
                    commit_learning_state,
                    "_write_all",
                    side_effect=write_then_replace_temporary,
                ):
                    with self.assertRaisesRegex(ValidationError, "identity"):
                        commit_learning_state._publish_fact_no_clobber(
                            directory_fd,
                            fact,
                        )
            finally:
                os.close(directory_fd)

            self.assertEqual(1, len(replaced_names))
            self.assertFalse(
                (fact_directory / "record-session-001.json").exists()
            )
            replacement_path = fact_directory / replaced_names[0]
            self.assertTrue(replacement_path.exists())
            self.assertEqual(replacement, replacement_path.read_bytes())

    def test_publish_fails_closed_without_held_fd_primitive(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            fact_directory = Path(tmp)
            directory_fd = os.open(
                fact_directory,
                os.O_RDONLY | os.O_DIRECTORY,
            )
            try:
                with mock.patch.object(
                    commit_learning_state.sys,
                    "platform",
                    "fictional-os",
                ):
                    with self.assertRaisesRegex(
                        ValidationError,
                        "held-file|unavailable|platform",
                    ):
                        commit_learning_state._publish_fact_no_clobber(
                            directory_fd,
                            fact,
                        )
            finally:
                os.close(directory_fd)

            self.assertEqual([], list(fact_directory.iterdir()))

    def test_replaced_final_after_publish_is_never_unlinked(self):
        fact = session_fact(observations=[knowledge_observation()])
        replacement_fact = session_fact(
            student_attempt="fictional replacement evidence",
            observations=[knowledge_observation()],
        )
        replacement = commit_learning_state._canonical_json(replacement_fact)
        with tempfile.TemporaryDirectory() as tmp:
            fact_directory = Path(tmp)
            directory_fd = os.open(
                fact_directory,
                os.O_RDONLY | os.O_DIRECTORY,
            )
            final_name = "record-session-001.json"
            final_path = fact_directory / final_name
            directory_entry = fact_directory.stat()
            directory_identity = (
                directory_entry.st_dev,
                directory_entry.st_ino,
            )
            real_fsync = os.fsync
            replaced_final = False

            def replace_final_before_directory_fsync(file_fd):
                nonlocal replaced_final
                entry = os.fstat(file_fd)
                if (
                    not replaced_final
                    and (entry.st_dev, entry.st_ino) == directory_identity
                    and final_path.exists()
                ):
                    final_path.unlink()
                    final_path.write_bytes(replacement)
                    replaced_final = True
                return real_fsync(file_fd)

            try:
                with mock.patch.object(
                    commit_learning_state.os,
                    "fsync",
                    side_effect=replace_final_before_directory_fsync,
                ):
                    with self.assertRaisesRegex(
                        ValidationError,
                        "published|identity|content",
                    ):
                        commit_learning_state._publish_fact_no_clobber(
                            directory_fd,
                            fact,
                        )
            finally:
                os.close(directory_fd)

            self.assertTrue(replaced_final)
            self.assertTrue(final_path.exists())
            self.assertEqual(replacement, final_path.read_bytes())

    def test_replaced_source_name_never_publishes_replacement_content(self):
        fact = session_fact(observations=[knowledge_observation()])
        replacement = b"not canonical fact content\n"
        with tempfile.TemporaryDirectory() as tmp:
            fact_directory = Path(tmp)
            directory_fd = os.open(
                fact_directory,
                os.O_RDONLY | os.O_DIRECTORY,
            )
            final_name = "record-session-001.json"
            final_path = fact_directory / final_name
            real_stat = os.stat
            replaced_source_name = None
            observed_final_contents = []

            def replace_source_after_stat(path, *args, **kwargs):
                nonlocal replaced_source_name
                entry = real_stat(path, *args, **kwargs)
                if (
                    replaced_source_name is None
                    and kwargs.get("dir_fd") == directory_fd
                    and isinstance(path, str)
                    and path.startswith(".record-session-001-")
                    and path.endswith(".tmp")
                ):
                    temporary_path = fact_directory / path
                    temporary_path.unlink()
                    temporary_path.write_bytes(replacement)
                    replaced_source_name = path
                elif path == final_name:
                    observed_final_contents.append(final_path.read_bytes())
                return entry

            try:
                with mock.patch.object(
                    commit_learning_state.os,
                    "stat",
                    side_effect=replace_source_after_stat,
                ):
                    with self.assertRaisesRegex(ValidationError, "identity"):
                        commit_learning_state._publish_fact_no_clobber(
                            directory_fd,
                            fact,
                        )
            finally:
                os.close(directory_fd)

            self.assertIsNotNone(replaced_source_name)
            self.assertNotIn(replacement, observed_final_contents)
            self.assertFalse(final_path.exists())
            replacement_path = fact_directory / replaced_source_name
            self.assertTrue(replacement_path.exists())
            self.assertEqual(replacement, replacement_path.read_bytes())

    def test_cross_type_record_id_conflict_preserves_workspace(self):
        session = session_fact(observations=[knowledge_observation()])
        plan = plan_fact(record_id=session["record_id"])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, session, now=NOW)
            plan_directory = workspace / "plan-items"
            plan_before = {
                path.name: path.read_bytes() for path in plan_directory.iterdir()
            }
            state_before = (workspace / "state.json").read_bytes()

            with self.assertRaisesRegex(ValidationError, "duplicate record_id"):
                commit_fact(workspace, plan, now=LATER)

            self.assertEqual(
                plan_before,
                {path.name: path.read_bytes() for path in plan_directory.iterdir()},
            )
            self.assertEqual(
                state_before,
                (workspace / "state.json").read_bytes(),
            )
            validate_workspace(workspace)

    def test_history_conflict_is_rejected_before_fact_publication(self):
        original = session_fact(observations=[knowledge_observation()])
        conflicting = session_fact(
            record_id="record-session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-002")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, original, now=NOW)
            state_before = (workspace / "state.json").read_bytes()
            conflicting_path = workspace / "sessions/record-session-002.json"

            with self.assertRaisesRegex(ValidationError, "duplicate session_id"):
                commit_fact(workspace, conflicting, now=LATER)

            self.assertFalse(conflicting_path.exists())
            self.assertEqual(
                state_before,
                (workspace / "state.json").read_bytes(),
            )
            snapshot = validate_workspace(workspace)
            self.assertEqual(1, len(snapshot.sessions))
            self.assertEqual(1, snapshot.state["process"]["recorded_sessions"])

    def test_existing_cross_type_duplicate_is_rejected_before_publish(self):
        session = session_fact(observations=[knowledge_observation()])
        duplicate_plan = plan_fact(record_id=session["record_id"])
        incoming = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:10:00+00:00",
            observations=[knowledge_observation(evidence_id="evidence-002")],
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, session, now=NOW)
            duplicate_path = (
                workspace
                / "plan-items"
                / "record-session-001.json"
            )
            duplicate_path.write_bytes(
                commit_learning_state._canonical_json(duplicate_plan)
            )
            state_before = (workspace / "state.json").read_bytes()
            incoming_path = workspace / "sessions/record-session-002.json"

            with self.assertRaisesRegex(ValidationError, "duplicate record_id"):
                commit_fact(workspace, incoming, now=LATER)

            self.assertFalse(incoming_path.exists())
            self.assertEqual(
                state_before,
                (workspace / "state.json").read_bytes(),
            )

    def test_alias_fact_name_is_rejected_before_publish(self):
        existing = session_fact(observations=[knowledge_observation()])
        incoming = plan_fact(record_id="record-plan-002", item_id="item-002")
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            commit_fact(workspace, existing, now=NOW)
            original_path = workspace / "sessions/record-session-001.json"
            alias_path = workspace / "sessions/alias.json"
            original_path.rename(alias_path)
            state_before = (workspace / "state.json").read_bytes()
            incoming_path = workspace / "plan-items/record-plan-002.json"

            with self.assertRaisesRegex(ValidationError, "filename|record_id"):
                commit_fact(workspace, incoming, now=LATER)

            self.assertTrue(alias_path.exists())
            self.assertFalse(incoming_path.exists())
            self.assertEqual(
                state_before,
                (workspace / "state.json").read_bytes(),
            )

    def test_state_replace_failure_is_recoverable(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            old_state = (workspace / "state.json").read_bytes()

            with mock.patch.object(
                commit_learning_state.os,
                "replace",
                side_effect=OSError("fictional pre-replace failure"),
            ):
                with self.assertRaisesRegex(OSError, "pre-replace"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertTrue(
                (workspace / "sessions/record-session-001.json").is_file()
            )
            self.assertEqual(old_state, (workspace / "state.json").read_bytes())
            self.assertEqual(
                [],
                [path.name for path in workspace.iterdir() if path.name.endswith(".tmp")],
            )

            published = commit_fact(workspace, fact, now=LATER)
            snapshot = validate_workspace(workspace)

            self.assertFalse(published)
            self.assertEqual(1, snapshot.state["process"]["recorded_sessions"])
            self.assertEqual(LATER, snapshot.state["updated_at"])

    def test_state_write_failure_cleans_owned_temporary_file(self):
        fact = session_fact(observations=[knowledge_observation()])
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            old_state = (workspace / "state.json").read_bytes()
            real_write_all = commit_learning_state._write_all
            calls = 0

            def fail_state_write(file_fd, data):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("fictional state write failure")
                return real_write_all(file_fd, data)

            with mock.patch.object(
                commit_learning_state,
                "_write_all",
                side_effect=fail_state_write,
            ):
                with self.assertRaisesRegex(OSError, "state write"):
                    commit_fact(workspace, fact, now=NOW)

            self.assertEqual(old_state, (workspace / "state.json").read_bytes())
            self.assertEqual(
                [],
                [path.name for path in workspace.iterdir() if path.name.endswith(".tmp")],
            )

    def test_two_concurrent_session_commits_preserve_both_facts(self):
        first = session_fact(
            record_id="record-session-001",
            session_id="session-001",
            observations=[knowledge_observation(evidence_id="evidence-001")],
        )
        second = session_fact(
            record_id="record-session-002",
            session_id="session-002",
            completed_at="2026-08-06T10:01:00+00:00",
            observations=[
                knowledge_observation(
                    evidence_id="evidence-002",
                    target_id="mathematics.geometry.line-plane-perpendicular",
                    target_name="线面垂直",
                )
            ],
        )
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            inputs = []
            for fact in (first, second):
                path = Path(tmp) / (fact["record_id"] + "-input.json")
                path.write_text(json.dumps(fact, ensure_ascii=False), encoding="utf-8")
                inputs.append(path)

            processes = [
                subprocess.Popen(
                    [
                        sys.executable,
                        str(COMMIT),
                        str(workspace),
                        "--fact-file",
                        str(path),
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for path in inputs
            ]
            results = []
            for process in processes:
                stdout, stderr = process.communicate(timeout=10)
                results.append((process.returncode, stdout, stderr))

            self.assertEqual([0, 0], sorted(result[0] for result in results), results)
            snapshot = validate_workspace(workspace)
            self.assertEqual(2, snapshot.state["process"]["recorded_sessions"])
            self.assertEqual(
                {"record-session-001.json", "record-session-002.json"},
                {path.name for path in (workspace / "sessions").iterdir()},
            )

    def test_cli_rejects_invalid_fact_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            result = self.run_cli(workspace, {"record_type": "session"})

            self.assertEqual(1, result.returncode)
            self.assertTrue(result.stderr.startswith("ERROR:"), result.stderr)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
