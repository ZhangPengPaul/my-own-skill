from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPrivacyTest(unittest.TestCase):
    def test_student_workspaces_are_ignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/student-workspaces/", lines)
        result = subprocess.run(
            [
                "git",
                "check-ignore",
                "--no-index",
                "student-workspaces/.privacy-probe",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            0,
            result.returncode,
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}",
        )

    def test_no_student_workspace_is_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "student-workspaces"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual("", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
