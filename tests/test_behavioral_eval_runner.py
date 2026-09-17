import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tests/behavioral/run_behavioral_eval.py"


class BehavioralEvalRunnerTest(unittest.TestCase):
    def _write_cases(self, directory, *, failing=False):
        cases = [
            {
                "id": "sample-case",
                "prompt": "student prompt",
                "must": ["FAIL-GRADE" if failing else "answer the question"],
                "must_not": ["reveal private process"],
            }
        ]
        path = Path(directory) / "cases.json"
        path.write_text(json.dumps(cases), encoding="utf-8")
        return path

    def _write_fake_codex(self, directory):
        path = Path(directory) / "fake-codex.py"
        path.write_text(
            """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys
import time

prompt = sys.argv[-1]
is_grader = prompt.startswith("BEHAVIORAL_EVAL_GRADER_V1")
if "SLOW-EXECUTOR" in prompt:
    time.sleep(1)
with Path(os.environ["FAKE_CODEX_LOG"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"kind": "grader" if is_grader else "executor", "prompt": prompt}) + "\\n")

def emit(text):
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": text}}))

if not is_grader:
    emit("MODEL RESPONSE")
    raise SystemExit(0)

payload = json.loads(prompt.split("\\nINPUT_JSON\\n", 1)[1])
grades = []
for expectation in payload["expectations"]:
    grades.append({
        "id": expectation["id"],
        "passed": "FAIL-GRADE" not in expectation["criterion"],
        "evidence": "fake evidence",
    })
emit(json.dumps({"schema_version": 1, "expectations": grades}))
""",
            encoding="utf-8",
        )
        path.chmod(0o755)
        return path

    def _run(self, root, *, failing=False):
        cases = self._write_cases(root, failing=failing)
        fake_codex = self._write_fake_codex(root)
        output = Path(root) / "results"
        log = Path(root) / "codex-calls.jsonl"
        environment = os.environ.copy()
        environment["FAKE_CODEX_LOG"] = str(log)
        completed = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--cases",
                str(cases),
                "--output-dir",
                str(output),
                "--codex-bin",
                str(fake_codex),
                "--execute",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )
        return completed, output, log

    def test_archives_response_and_does_not_leak_criteria_to_executor(self):
        with tempfile.TemporaryDirectory() as root:
            completed, output, log = self._run(root)

            self.assertEqual(0, completed.returncode, completed.stderr)
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("passed", report["status"])
            self.assertEqual(2, report["summary"]["expectations_passed"])
            self.assertEqual(
                "MODEL RESPONSE",
                (output / "sample-case/response.md").read_text(encoding="utf-8"),
            )
            calls = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
            ]
            executor_prompt = next(
                call["prompt"] for call in calls if call["kind"] == "executor"
            )
            self.assertIn("student prompt", executor_prompt)
            self.assertIn("$shanghai-high-school-study-coach", executor_prompt)
            self.assertNotIn("./skill/SKILL.md", executor_prompt)
            self.assertNotIn("answer the question", executor_prompt)
            self.assertNotIn("reveal private process", executor_prompt)

    def test_unmet_criterion_fails_run_but_preserves_grading_evidence(self):
        with tempfile.TemporaryDirectory() as root:
            completed, output, _ = self._run(root, failing=True)

            self.assertEqual(1, completed.returncode)
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual("failed", report["status"])
            self.assertEqual(1, report["summary"]["expectations_failed"])
            result = json.loads(
                (output / "sample-case/result.json").read_text(encoding="utf-8")
            )
            self.assertEqual("failed", result["status"])
            self.assertFalse(result["expectations"][0]["passed"])
            self.assertTrue((output / "sample-case/grader.jsonl").is_file())

    def test_dry_run_counts_ungraded_cases_without_starting_codex(self):
        with tempfile.TemporaryDirectory() as root:
            cases = self._write_cases(root)
            output = Path(root) / "results"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--cases",
                    str(cases),
                    "--output-dir",
                    str(output),
                    "--codex-bin",
                    str(Path(root) / "does-not-exist"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            self.assertEqual(1, report["summary"]["cases_total"])
            self.assertEqual(1, report["summary"]["cases_ungraded"])
            self.assertEqual(2, report["summary"]["expectations_total"])
            self.assertEqual(2, report["summary"]["expectations_ungraded"])

    def test_executor_timeout_is_archived_as_a_failed_case(self):
        with tempfile.TemporaryDirectory() as root:
            cases = Path(root) / "cases.json"
            cases.write_text(
                json.dumps(
                    [
                        {
                            "id": "slow-case",
                            "prompt": "SLOW-EXECUTOR",
                            "must": ["answer"],
                            "must_not": ["leak"],
                        }
                    ]
                ),
                encoding="utf-8",
            )
            fake_codex = self._write_fake_codex(root)
            output = Path(root) / "results"
            environment = os.environ.copy()
            environment["FAKE_CODEX_LOG"] = str(Path(root) / "calls.jsonl")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(RUNNER),
                    "--cases",
                    str(cases),
                    "--output-dir",
                    str(output),
                    "--codex-bin",
                    str(fake_codex),
                    "--timeout-seconds",
                    "0.05",
                    "--execute",
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )

            self.assertEqual(1, completed.returncode)
            self.assertTrue((output / "report.json").is_file(), completed.stderr)
            result = json.loads(
                (output / "slow-case/result.json").read_text(encoding="utf-8")
            )
            self.assertEqual("failed", result["status"])
            self.assertIsNone(result["executor_exit_code"])
            self.assertIn(
                "timed out",
                (output / "slow-case/stderr.txt").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
