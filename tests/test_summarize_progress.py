from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
INIT = SCRIPTS / "init_student.py"
sys.path.insert(0, str(SCRIPTS))

from commit_learning_state import commit_fact  # noqa: E402
import summarize_progress  # noqa: E402
from tests.workspace_fixtures import (  # noqa: E402
    knowledge_observation,
    pattern_observation,
    plan_fact,
    session_fact,
)


NOW = "2026-08-06T12:00:00+00:00"


class SummarizeProgressTest(unittest.TestCase):
    def initialize_workspace(self, root):
        result = subprocess.run(
            [sys.executable, str(INIT), "--root", str(root), "student-a"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)
        return root / "student-a"

    def commit_session(self, workspace, number, observations):
        commit_fact(
            workspace,
            session_fact(
                record_id="record-session-%03d" % number,
                session_id="session-%03d" % number,
                completed_at="2026-08-06T10:%02d:00+00:00" % number,
                observations=observations,
            ),
            now=NOW,
        )

    def test_reports_evidence_based_priorities(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_session(
                workspace,
                1,
                [
                    knowledge_observation(
                        evidence_id="evidence-001",
                        target_id="mathematics.geometry.target-suspected",
                        target_name="待确认目标",
                        evidence_type="initial_attempt",
                        next_review_at="2026-08-06T11:00:00+00:00",
                    )
                ],
            )
            self.commit_session(
                workspace,
                2,
                [
                    knowledge_observation(
                        evidence_id="evidence-002",
                        target_id="mathematics.geometry.target-confirmed",
                        target_name="已确认目标",
                    ),
                    knowledge_observation(
                        evidence_id="evidence-006",
                        target_id="mathematics.geometry.target-confirmed",
                        target_name="已确认目标",
                    ),
                ],
            )
            self.commit_session(
                workspace,
                3,
                [
                    knowledge_observation(
                        evidence_id="evidence-003",
                        target_id="mathematics.geometry.target-strengthening",
                        target_name="强化目标",
                        evidence_type="variant",
                        outcome="correct",
                        hint_level="principle",
                        first_substantive_error=None,
                    )
                ],
            )
            self.commit_session(
                workspace,
                4,
                [pattern_observation(evidence_id="evidence-004")],
            )
            self.commit_session(
                workspace,
                5,
                [pattern_observation(evidence_id="evidence-005")],
            )
            commit_fact(
                workspace,
                plan_fact(
                    task="优先巩固待确认目标",
                    due_at="2026-08-07T12:00:00+00:00",
                    priority=1,
                ),
                now=NOW,
            )

            output = summarize_progress.render(workspace, now=NOW)

        self.assertIn("待确认薄弱: 1", output)
        self.assertIn("已确认薄弱: 1", output)
        self.assertIn("强化中: 1", output)
        self.assertIn("到期复测", output)
        self.assertIn("重复出现", output)
        self.assertIn(
            "待确认目标 [suspected_gap；到期复测; evidence: evidence-001]",
            output,
        )
        self.assertIn(
            "已确认目标 [confirmed_gap; evidence: evidence-002, evidence-006]",
            output,
        )
        self.assertIn(
            "模式：方法选择 [重复出现; evidence: evidence-004, evidence-005]",
            output,
        )
        self.assertIn("优先级 1", output)
        self.assertIn("已完成计划项目: 0", output)
        self.assertIn("记录会话: 5", output)
        self.assertNotIn("预计分数", output)
        self.assertNotIn("qualification", output)

    def test_active_plan_items_are_sorted_by_priority_due_date_and_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            for record_id, item_id, priority, due_at, task in (
                ("record-plan-003", "item-003", 2, None, "第三项"),
                ("record-plan-002", "item-002", 1, "2026-08-09T00:00:00+00:00", "第二项"),
                ("record-plan-001", "item-001", 1, "2026-08-08T00:00:00+00:00", "第一项"),
            ):
                commit_fact(
                    workspace,
                    plan_fact(
                        record_id=record_id,
                        item_id=item_id,
                        priority=priority,
                        due_at=due_at,
                        task=task,
                    ),
                    now=NOW,
                )

            output = summarize_progress.render(workspace, now=NOW)

        self.assertLess(output.index("第一项"), output.index("第二项"))
        self.assertLess(output.index("第二项"), output.index("第三项"))

    def test_plan_due_dates_are_sorted_by_absolute_aware_instant(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            for record_id, item_id, due_at, task in (
                (
                    "record-plan-001",
                    "item-001",
                    "2026-08-08T00:30:00+01:00",
                    "绝对时间较早",
                ),
                (
                    "record-plan-002",
                    "item-002",
                    "2026-08-07T23:45:00Z",
                    "绝对时间较晚",
                ),
                ("record-plan-003", "item-003", None, "未设日期"),
            ):
                commit_fact(
                    workspace,
                    plan_fact(
                        record_id=record_id,
                        item_id=item_id,
                        priority=1,
                        due_at=due_at,
                        task=task,
                    ),
                    now=NOW,
                )

            output = summarize_progress.render(workspace, now=NOW)

        self.assertLess(output.index("绝对时间较早"), output.index("绝对时间较晚"))
        self.assertLess(output.index("绝对时间较晚"), output.index("未设日期"))

    def test_uses_shared_timestamp_parser_for_now_reviews_and_plan_due_dates(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_session(
                workspace,
                1,
                [
                    knowledge_observation(
                        evidence_type="initial_attempt",
                        next_review_at="2026-08-06T12:00:00Z",
                    )
                ],
            )
            commit_fact(
                workspace,
                plan_fact(due_at="2026-08-08T00:30:00+01:00"),
                now=NOW,
            )
            shared_parser = summarize_progress._parse_timestamp

            with mock.patch.object(
                summarize_progress,
                "_parse_timestamp",
                wraps=shared_parser,
            ) as parser:
                summarize_progress.render(
                    workspace,
                    now="2026-08-06T13:00:00+01:00",
                )

        self.assertEqual(
            [
                mock.call("2026-08-06T13:00:00+01:00", "now"),
                mock.call("2026-08-06T12:00:00Z", "next_review_at"),
                mock.call("2026-08-08T00:30:00+01:00", "due_at"),
            ],
            parser.call_args_list,
        )

    def test_renders_the_snapshot_returned_by_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            state_path = workspace / "state.json"
            original_validate_workspace = summarize_progress.validate_workspace

            def validate_then_replace(workspace_to_validate):
                snapshot = original_validate_workspace(workspace_to_validate)
                state_path.write_bytes(b"\xff\xfe")
                return snapshot

            with mock.patch.object(
                summarize_progress,
                "validate_workspace",
                side_effect=validate_then_replace,
            ) as validator:
                output = summarize_progress.render(workspace, now=NOW)

            validator.assert_called_once_with(workspace)
            self.assertIn("- student_id: student-a", output)

    def test_escapes_control_characters_in_target_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_session(
                workspace,
                1,
                [
                    knowledge_observation(
                        target_name="安全名称\n# injected heading",
                        evidence_type="initial_attempt",
                    )
                ],
            )

            output = summarize_progress.render(workspace, now=NOW)

        self.assertNotIn("\n# injected heading", output)
        self.assertIn("安全名称\\u000A# injected heading", output)

    def test_escapes_control_characters_in_snapshot_evidence_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            self.commit_session(
                workspace,
                1,
                [knowledge_observation(evidence_type="initial_attempt")],
            )
            original_validate_workspace = summarize_progress.validate_workspace

            def validate_with_hostile_evidence(workspace_to_validate):
                snapshot = original_validate_workspace(workspace_to_validate)
                target = snapshot.state["subjects"]["mathematics"][
                    "knowledge_units"
                ]["mathematics.geometry.dihedral-angle"]
                target["evidence_ids"] = ["evidence-safe", "evidence-hostile\n# heading"]
                return snapshot

            with mock.patch.object(
                summarize_progress,
                "validate_workspace",
                side_effect=validate_with_hostile_evidence,
            ):
                output = summarize_progress.render(workspace, now=NOW)

        self.assertNotIn("\n# heading", output)
        self.assertIn(
            "evidence: evidence-safe, evidence-hostile\\u000A# heading",
            output,
        )

    def test_uses_six_subjects_in_canonical_order(self):
        expected = [
            "chinese",
            "mathematics",
            "english",
            "politics",
            "history",
            "geography",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            output = summarize_progress.render(workspace, now=NOW)

        section = output.split("## 学科状态\n", 1)[1].split("\n## ", 1)[0]
        actual = [
            line[4:]
            for line in section.splitlines()
            if line.startswith("### ")
        ]
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
