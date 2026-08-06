from pathlib import Path
import json
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BEHAVIORAL = ROOT / "tests/behavioral"


class BehavioralFixtureTest(unittest.TestCase):
    def test_generator_creates_pdf_and_image(self):
        subprocess.run(
            [sys.executable, str(BEHAVIORAL / "generate_fixtures.py")], check=True
        )
        pdf = (BEHAVIORAL / "fixtures/math-exam.pdf").read_bytes()
        svg = (BEHAVIORAL / "fixtures/english-essay.svg").read_text(
            encoding="utf-8"
        )
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn("<svg", svg)
        self.assertIn("My weekend volunteer work", svg)

    def test_case_catalog_has_required_phase_one_coverage(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        ids = {case["id"] for case in cases}
        self.assertEqual(
            {
                "onboarding-plan",
                "math-review",
                "english-writing",
                "humanities-evidence",
                "unreadable-input",
                "source-conflict",
                "no-evidence-no-mastery",
            },
            ids,
        )
        for case in cases:
            self.assertTrue(case["prompt"])
            self.assertTrue(case["must"])
            self.assertTrue(case["must_not"])


if __name__ == "__main__":
    unittest.main()
