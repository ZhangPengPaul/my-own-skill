from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPrivacyTest(unittest.TestCase):
    def test_student_workspaces_are_ignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/student-workspaces/", lines)
        self.assertIn("**/student-workspaces/", lines)
        self.assertIn("**/private-workspace-roots/", lines)
        for probe in (
            "student-workspaces/.privacy-probe",
            "skills/coach-workspace/run/student-workspaces/student-a/state.json",
            "skills/coach-workspace/run/private-workspace-roots/case-a/student-a/state.json",
        ):
            with self.subTest(probe=probe):
                result = subprocess.run(
                    ["git", "check-ignore", "--no-index", probe],
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
            ["git", "ls-files"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        private_names = {"student-workspaces", "private-workspace-roots"}
        tracked = [
            path
            for path in result.stdout.splitlines()
            if private_names.intersection(Path(path).parts)
        ]
        self.assertEqual([], tracked)


if __name__ == "__main__":
    unittest.main()
