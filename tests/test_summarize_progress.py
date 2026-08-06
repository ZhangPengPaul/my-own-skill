from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills/shanghai-high-school-study-coach/scripts"
INIT = SCRIPTS / "init_student.py"
SUMMARY = SCRIPTS / "summarize_progress.py"
sys.path.insert(0, str(SCRIPTS))

import summarize_progress


class SummarizeProgressTest(unittest.TestCase):
    def initialize_workspace(self, root):
        subprocess.run(
            [sys.executable, str(INIT), "--root", str(root), "student-a"],
            check=True,
            capture_output=True,
            text=True,
        )
        return root / "student-a"

    def test_reports_recorded_facts_and_mastery_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(
                [sys.executable, str(INIT), "--root", str(root), "student-a"],
                check=True,
            )
            workspace = root / "student-a"
            session = workspace / "sessions/2026-08-06-mathematics-s1.md"
            session.write_text("fictional independent answer", encoding="utf-8")
            state_path = workspace / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
                "status": "developing",
                "evidence": ["sessions/2026-08-06-mathematics-s1.md"],
                "last_reviewed_at": "2026-08-06",
                "next_review_at": "2026-08-13",
            }
            state["process"] = {"completed_plan_items": 2, "recorded_sessions": 1}
            state_path.write_text(
                json.dumps(state, ensure_ascii=False), encoding="utf-8"
            )

            result = subprocess.run(
                [sys.executable, str(SUMMARY), str(workspace)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("student-a", result.stdout)
            self.assertIn("mathematics: developing=1", result.stdout)
            self.assertIn("已完成计划项目: 2", result.stdout)
            self.assertIn("记录会话: 1", result.stdout)
            self.assertNotIn("预计分数", result.stdout)

    def test_renders_the_state_snapshot_returned_by_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            state_path = workspace / "state.json"
            original_validate_workspace = summarize_progress.validate_workspace

            def validate_then_replace(workspace_to_validate):
                state = original_validate_workspace(workspace_to_validate)
                state_path.write_bytes(b"\xff\xfe")
                return state

            with mock.patch.object(
                summarize_progress,
                "validate_workspace",
                side_effect=validate_then_replace,
            ) as validator:
                try:
                    output = summarize_progress.render(workspace)
                except UnicodeError as error:
                    self.fail("render reread state.json after validation: %s" % error)

            validator.assert_called_once_with(workspace)
            self.assertIn("- student_id: student-a", output)

    def test_uses_canonical_subject_order(self):
        expected_subjects = [
            "chinese",
            "mathematics",
            "english",
            "politics",
            "history",
            "geography",
            "physics",
            "chemistry",
            "biology",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            state_path = workspace / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["subjects"] = dict(reversed(list(state["subjects"].items())))
            state_path.write_text(json.dumps(state), encoding="utf-8")

            output = summarize_progress.render(workspace)

        subject_section = output.split("## 学科状态\n\n", 1)[1]
        rendered_subjects = [
            line[2:].split(":", 1)[0] for line in subject_section.splitlines()
        ]
        self.assertEqual(expected_subjects, rendered_subjects)

    def test_escapes_updated_at_newline_in_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = self.initialize_workspace(Path(tmp))
            state_path = workspace / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["updated_at"] = "2026-08-06T00:00:00Z\n# injected heading"
            state_path.write_text(json.dumps(state), encoding="utf-8")

            output = summarize_progress.render(workspace)

        self.assertNotIn("\n# injected heading", output)
        self.assertIn(
            "- updated_at: 2026-08-06T00:00:00Z\\u000A# injected heading\n",
            output,
        )


if __name__ == "__main__":
    unittest.main()
