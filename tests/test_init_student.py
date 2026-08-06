from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/shanghai-high-school-study-coach/scripts/init_student.py"


class InitStudentTest(unittest.TestCase):
    def run_init(self, root, student_id):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), student_id],
            capture_output=True,
            text=True,
        )

    def test_creates_valid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "student-a")
            self.assertEqual(0, result.returncode, result.stderr)
            workspace = root / "student-a"
            for relative in (
                "profile.md",
                "state.json",
                "plans/current.md",
                "mistakes",
                "sessions",
                "materials",
            ):
                self.assertTrue((workspace / relative).exists(), relative)
            state = json.loads(
                (workspace / "state.json").read_text(encoding="utf-8")
            )
            self.assertEqual("student-a", state["student_id"])
            self.assertNotIn(
                "__STUDENT_ID__",
                (workspace / "profile.md").read_text(encoding="utf-8"),
            )

    def test_refuses_to_overwrite_existing_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(0, self.run_init(root, "student-a").returncode)
            marker = root / "student-a" / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            result = self.run_init(root, "student-a")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_invalid_id_leaves_no_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Student Name")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual([], list(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
