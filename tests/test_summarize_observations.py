import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPTS))

from commit_learning_state import commit_fact  # noqa: E402
import summarize_progress  # noqa: E402
from tests.workspace_fixtures import (  # noqa: E402
    interaction_observation,
    knowledge_observation,
    session_fact,
)


class SummarizeObservationsTest(unittest.TestCase):
    def initialize_workspace(self, root):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "init_student.py"),
                "--root",
                str(root),
                "student-a",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / "student-a"

    def commit_observation(self, workspace, number, **overrides):
        values = {
            "record_id": "observation-%03d" % number,
            "interaction_id": "interaction-%03d" % number,
            "occurred_at": "2026-08-%02dT10:00:00+00:00" % number,
        }
        values.update(overrides)
        commit_fact(
            workspace,
            interaction_observation(**values),
            now="2026-08-20T00:00:00+00:00",
        )

    def commit_session(self, workspace, number, completed_at, **observation_overrides):
        commit_fact(
            workspace,
            session_fact(
                record_id="record-session-%03d" % number,
                session_id="session-%03d" % number,
                completed_at=completed_at,
                observations=[
                    knowledge_observation(
                        evidence_id="evidence-%03d" % number,
                        **observation_overrides,
                    )
                ],
            ),
            now="2026-08-20T00:00:00+00:00",
        )

    def test_renders_one_interaction_as_unresolved_weak_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("## 未解决单次弱线索", output)
        self.assertIn("subject: mathematics", output)
        self.assertIn("module: geometry", output)
        self.assertIn("target_kind: knowledge_unit", output)
        self.assertIn("target_id: mathematics.geometry.dihedral-angle", output)
        self.assertIn("target_name: 二面角的平面角", output)
        self.assertIn("signal_kind: content_gap", output)
        self.assertIn("signal: cannot identify the relevant angle", output)
        self.assertIn("time: 2026-08-01T10:00:00+00:00", output)
        self.assertIn("uncertainty: single observation", output)
        self.assertIn("- 无待验证观察", output)

    def test_second_interaction_moves_history_to_pending_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_observation(workspace, 2)

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("- 无未解决单次弱线索", output)
        self.assertIn("## 待验证观察", output)
        self.assertIn("module: geometry", output)
        self.assertIn("target_kind: knowledge_unit", output)
        self.assertIn("signal_kind: content_gap", output)
        self.assertIn("出现 2 次", output)
        self.assertIn("latest: 2026-08-02T10:00:00+00:00", output)

    def test_pending_validation_renders_each_member_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(
                workspace,
                1,
                signal="在二面角图形中分不清哪个角是平面角",
                student_action="询问如何从图中识别平面角",
                uncertainty="尚未观察独立识别",
            )
            self.commit_observation(
                workspace,
                2,
                signal="作出垂直截面后不确定应选择哪个角",
                student_action="询问垂直截面中应该量哪个角",
                uncertainty="尚未观察新图形中的独立选角",
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        first = (
            "成员观察 1｜signal: 在二面角图形中分不清哪个角是平面角｜"
            "student_action: 询问如何从图中识别平面角｜"
            "uncertainty: 尚未观察独立识别"
        )
        second = (
            "成员观察 2｜signal: 作出垂直截面后不确定应选择哪个角｜"
            "student_action: 询问垂直截面中应该量哪个角｜"
            "uncertainty: 尚未观察新图形中的独立选角"
        )
        self.assertIn(first, output)
        self.assertIn(second, output)
        self.assertLess(output.index(first), output.index(second))

    def test_mismatched_formal_evidence_does_not_resolve_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_observation(workspace, 2)
            self.commit_session(
                workspace,
                1,
                "2026-08-03T10:00:00+00:00",
                target_id="mathematics.geometry.other-target",
                target_name="其他目标",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("出现 2 次", output)
        self.assertIn("cannot identify the relevant angle", output)

    def test_subject_mismatch_does_not_resolve_observations(self):
        observations = [
            interaction_observation(
                record_id="observation-001",
                interaction_id="interaction-001",
                occurred_at="2026-08-01T10:00:00+00:00",
            ),
            interaction_observation(
                record_id="observation-002",
                interaction_id="interaction-002",
                occurred_at="2026-08-02T10:00:00+00:00",
            ),
        ]
        evidence = knowledge_observation(
            evidence_type="diagnostic",
            resolves_observation_signal_kinds=["content_gap"],
        )
        # The persisted schema couples subject to module and target_id. Calling
        # the selector directly isolates subject as an exact-match coordinate.
        session = session_fact(
            subject="english",
            completed_at="2026-08-03T10:00:00+00:00",
            observations=[evidence],
        )

        singletons, pending = summarize_progress._observation_summaries(
            observations,
            [session],
        )

        self.assertEqual((), singletons)
        self.assertEqual(1, len(pending))
        self.assertEqual(2, pending[0]["observation_count"])

    def test_module_mismatch_does_not_resolve_observations(self):
        observations = [
            interaction_observation(
                record_id="observation-001",
                interaction_id="interaction-001",
                occurred_at="2026-08-01T10:00:00+00:00",
            ),
            interaction_observation(
                record_id="observation-002",
                interaction_id="interaction-002",
                occurred_at="2026-08-02T10:00:00+00:00",
            ),
        ]
        evidence = knowledge_observation(
            module_id="algebra-and-functions",
            evidence_type="diagnostic",
            resolves_observation_signal_kinds=["content_gap"],
        )
        session = session_fact(
            completed_at="2026-08-03T10:00:00+00:00",
            observations=[evidence],
        )

        singletons, pending = summarize_progress._observation_summaries(
            observations,
            [session],
        )

        self.assertEqual((), singletons)
        self.assertEqual(1, len(pending))
        self.assertEqual(2, pending[0]["observation_count"])

    def test_target_kind_mismatch_does_not_resolve_observations(self):
        observations = [
            interaction_observation(
                record_id="observation-001",
                interaction_id="interaction-001",
                occurred_at="2026-08-01T10:00:00+00:00",
            ),
            interaction_observation(
                record_id="observation-002",
                interaction_id="interaction-002",
                occurred_at="2026-08-02T10:00:00+00:00",
            ),
        ]
        evidence = knowledge_observation(
            target_kind="pattern",
            evidence_type="diagnostic",
            resolves_observation_signal_kinds=["content_gap"],
        )
        session = session_fact(
            completed_at="2026-08-03T10:00:00+00:00",
            observations=[evidence],
        )

        singletons, pending = summarize_progress._observation_summaries(
            observations,
            [session],
        )

        self.assertEqual((), singletons)
        self.assertEqual(1, len(pending))
        self.assertEqual(2, pending[0]["observation_count"])

    def test_incomplete_session_does_not_resolve_observations(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_observation(workspace, 2)
            commit_fact(
                workspace,
                session_fact(
                    status="incomplete",
                    completed_at=None,
                    observations=[
                        knowledge_observation(
                            evidence_type="diagnostic",
                            resolves_observation_signal_kinds=["content_gap"],
                        )
                    ],
                ),
                now="2026-08-20T00:00:00+00:00",
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("出现 2 次", output)
        self.assertIn("cannot identify the relevant angle", output)

    def test_incomplete_revision_supersedes_completed_closing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_observation(workspace, 2)
            self.commit_session(
                workspace,
                1,
                "2026-08-03T10:00:00+00:00",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )
            commit_fact(
                workspace,
                session_fact(
                    record_id="record-session-002",
                    session_id="session-001",
                    supersedes_record_id="record-session-001",
                    status="incomplete",
                    completed_at=None,
                    observations=[],
                ),
                now="2026-08-20T00:00:00+00:00",
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("出现 2 次", output)
        self.assertIn("cannot identify the relevant angle", output)

    def test_validation_at_same_time_does_not_resolve_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_session(
                workspace,
                1,
                "2026-08-01T10:00:00+00:00",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("time: 2026-08-01T10:00:00+00:00", output)
        self.assertIn("cannot identify the relevant angle", output)

    def test_two_new_interactions_after_validation_form_new_pending_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1, signal="old signal one")
            self.commit_observation(workspace, 2, signal="old signal two")
            self.commit_session(
                workspace,
                1,
                "2026-08-03T10:00:00+00:00",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )
            self.commit_observation(workspace, 4, signal="new signal one")
            self.commit_observation(workspace, 5, signal="new signal two")

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("出现 2 次", output)
        self.assertNotIn("出现 4 次", output)
        self.assertIn("latest: 2026-08-05T10:00:00+00:00", output)
        self.assertIn("new signal one", output)
        self.assertIn("new signal two", output)
        self.assertNotIn("old signal one", output)
        self.assertNotIn("old signal two", output)

    def test_older_matching_formal_evidence_does_not_resolve_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_observation(workspace, 2)
            self.commit_session(
                workspace,
                1,
                "2026-07-31T10:00:00+00:00",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("出现 2 次", output)
        self.assertIn("cannot identify the relevant angle", output)

    def test_legacy_validation_without_signal_kinds_keeps_observation_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            evidence = knowledge_observation(
                evidence_id="evidence-001",
                evidence_type="diagnostic",
            )
            evidence.pop("resolves_observation_signal_kinds")
            commit_fact(
                workspace,
                session_fact(
                    record_id="record-session-001",
                    session_id="session-001",
                    completed_at="2026-08-02T10:00:00+00:00",
                    observations=[evidence],
                ),
                now="2026-08-20T00:00:00+00:00",
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("signal_kind: content_gap", output)
        self.assertIn("cannot identify the relevant angle", output)

    def test_validation_resolves_only_listed_signal_kind_for_same_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            for number in (1, 2):
                self.commit_observation(
                    workspace,
                    number,
                    signal="content gap signal",
                    student_action="content gap action",
                )
            for number in (3, 4):
                self.commit_observation(
                    workspace,
                    number,
                    signal_kind="representation-selection",
                    signal="representation selection signal",
                    student_action="representation selection action",
                )
            self.commit_session(
                workspace,
                1,
                "2026-08-05T10:00:00+00:00",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertNotIn("content gap signal", output)
        self.assertIn("signal_kind: representation-selection", output)
        self.assertIn("representation selection signal", output)
        self.assertIn("出现 2 次", output)

    def test_new_observation_after_validation_starts_a_fresh_singleton(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_observation(workspace, 1)
            self.commit_session(
                workspace,
                1,
                "2026-08-02T10:00:00+00:00",
                evidence_type="diagnostic",
                resolves_observation_signal_kinds=["content_gap"],
            )
            self.commit_observation(workspace, 3)

            output = summarize_progress.render(
                workspace,
                now="2026-08-20T00:00:00+00:00",
            )

        self.assertIn("time: 2026-08-03T10:00:00+00:00", output)
        self.assertIn("- 无待验证观察", output)
        self.assertNotIn("出现 2 次", output)

    def test_matching_later_validation_resolves_without_deleting_facts(self):
        for evidence_type in (
            "diagnostic",
            "variant",
            "delayed_retest",
            "transfer",
        ):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as tmp:
                    workspace = self.initialize_workspace(Path(tmp))
                    self.commit_observation(workspace, 1)
                    self.commit_observation(workspace, 2)
                    self.commit_session(
                        workspace,
                        1,
                        "2026-08-03T10:00:00+00:00",
                        evidence_type=evidence_type,
                        resolves_observation_signal_kinds=["content_gap"],
                    )
                    observation_files_before = sorted(
                        path.read_bytes()
                        for path in (workspace / "observations").iterdir()
                    )

                    output = summarize_progress.render(
                        workspace,
                        now="2026-08-20T00:00:00+00:00",
                    )
                    observation_files_after = sorted(
                        path.read_bytes()
                        for path in (workspace / "observations").iterdir()
                    )

                self.assertEqual(observation_files_before, observation_files_after)
                self.assertIn("- 无未解决单次弱线索", output)
                self.assertIn("- 无待验证观察", output)
                self.assertNotIn("cannot identify the relevant angle", output)
                self.assertIn("二面角的平面角 [suspected_gap", output)

    def test_initial_attempt_and_correction_do_not_close_weak_history(self):
        for evidence_type in ("initial_attempt", "correction"):
            with self.subTest(evidence_type=evidence_type):
                with tempfile.TemporaryDirectory() as tmp:
                    workspace = self.initialize_workspace(Path(tmp))
                    self.commit_observation(workspace, 1)
                    overrides = {
                        "evidence_type": evidence_type,
                        "resolves_observation_signal_kinds": ["content_gap"],
                    }
                    if evidence_type == "correction":
                        overrides["outcome"] = "correct"
                        overrides["first_substantive_error"] = None
                    self.commit_session(
                        workspace,
                        1,
                        "2026-08-03T10:00:00+00:00",
                        **overrides,
                    )

                    output = summarize_progress.render(
                        workspace,
                        now="2026-08-20T00:00:00+00:00",
                    )

                self.assertIn("cannot identify the relevant angle", output)

    def test_renders_repeated_observations_deterministically(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            for number in (2, 1):
                commit_fact(workspace, interaction_observation(
                    record_id="observation-%03d" % number,
                    interaction_id="interaction-%03d" % number,
                    occurred_at="2026-08-0%dT00:00:00+00:00" % number,
                    uncertainty=("需要换一种表示验证" if number == 1 else "可能是一次性疏漏|待复测"),
                ), now="2026-08-04T00:00:00+00:00")
            output = summarize_progress.render(workspace, now="2026-08-04T00:00:00+00:00")
        self.assertIn("## 待验证观察", output)
        self.assertIn("出现 2 次", output)
        self.assertIn("latest: 2026-08-02T00:00:00+00:00", output)
        self.assertIn("不确定性: 可能是一次性疏漏|待复测; 需要换一种表示验证", output)


if __name__ == "__main__":
    unittest.main()
