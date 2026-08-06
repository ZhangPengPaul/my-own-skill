from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "skills/shanghai-high-school-study-coach/scripts/init_student.py"
SUMMARY = ROOT / "skills/shanghai-high-school-study-coach/scripts/summarize_progress.py"


class SummarizeProgressTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
