import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import tests.behavioral.run_cross_session_eval as eval_runner
from tests.behavioral.run_cross_session_eval import (
    EvaluationFailed,
    _grader_prompt,
    _opening_sentence,
    _visible_memory_process_markers,
    run_evaluation,
)


class CrossSessionEvalRunnerTest(unittest.TestCase):
    def _expectation(self, expectation_id="answer", criterion="Answers correctly."):
        return {"id": expectation_id, "criterion": criterion}

    def _stage(
        self,
        stage_id,
        prompt,
        *,
        count=1,
        weak=1,
        repeated=0,
        pending=0,
        targets=None,
        expectations=None,
        forbidden_texts=None,
    ):
        if targets is None:
            targets = [] if count == 0 else [
                {
                    "subject": "mathematics",
                    "module_id": "geometry",
                    "target_kind": "knowledge_unit",
                    "observation_count": count,
                }
            ]
        return {
            "id": stage_id,
            "prompt": prompt,
            "expectations": expectations or [self._expectation()],
            "workspace_expectations": {
                "observation_count": count,
                "evidence_strength_counts": {
                    "weak": weak,
                    "repeated": repeated,
                },
                "pending_validation_count": pending,
                "observation_targets": targets,
                "forbidden_texts": forbidden_texts or [],
            },
        }

    def _write_manifest(self, directory, cases):
        manifest = Path(directory) / "manifest.json"
        manifest.write_text(
            json.dumps({"schema_version": 2, "student_id": "student-a", "cases": cases}),
            encoding="utf-8",
        )
        return manifest

    def _write_fake_codex(self, directory):
        fake = Path(directory) / "fake-codex.py"
        fake.write_text(
            """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

prompt = sys.argv[-1]
is_grader = prompt.startswith("CROSS_SESSION_EVAL_GRADER_V1")
prior_artifact_root = os.environ.get("FAKE_PRIOR_ARTIFACT_ROOT")
prior_artifact_exists = bool(
    prior_artifact_root
    and Path(prior_artifact_root).exists()
    and any(Path(prior_artifact_root).rglob("*last-message*"))
)
Path(os.environ["FAKE_CODEX_LOG"]).open("a", encoding="utf-8").write(
    json.dumps({
        "kind": "grader" if is_grader else "executor",
        "argv": sys.argv[1:],
        "cwd": os.getcwd(),
        "root": os.environ.get("SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT"),
        "prior_artifact_exists": prior_artifact_exists,
    }) + "\\n"
)

def emit(message):
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": message}}))

if is_grader:
    payload = json.loads(prompt.split("\\nINPUT_JSON\\n", 1)[1])
    if "MALFORMED-GRADER" in payload["final_response"]:
        emit('{"schema_version": 1, "expectations": []}')
        raise SystemExit(0)
    grades = []
    for expectation in payload["expectations"]:
        passed = "FAIL-GRADE" not in expectation["criterion"]
        if expectation["id"] == "observation-semantic-fit":
            new_observations = payload["artifact_summary"].get(
                "new_observations", []
            )
            passed = bool(new_observations) and all(
                observation.get("target_id")
                != "mathematics.geometry.wrong-target"
                for observation in new_observations
            )
        grades.append({
            "id": expectation["id"],
            "passed": passed,
            "evidence": "fake evidence for " + expectation["id"],
        })
    emit(json.dumps({"schema_version": 1, "expectations": grades}))
    raise SystemExit(0)

if "FAIL-THIS-PHASE" in prompt:
    print("fake failure", file=sys.stderr)
    raise SystemExit(17)

root = Path(os.environ["SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT"])
workspace = root / "student-a"
observations = workspace / "observations"
existing = sorted(observations.glob("*.json"))
number = len(existing) + 1
strength = "repeated" if "WRONG-STRENGTH" in prompt else "weak"
target_id = (
    "mathematics.geometry.wrong-target"
    if "WRONG-TARGET" in prompt
    else
    "mathematics.geometry.dihedral-plane-angle"
    if "ALIAS-TARGET" in prompt
    else
    "mathematics.geometry.line-plane-angle"
    if "UNRELATED-SECOND" in prompt
    else "mathematics.geometry.dihedral-angle"
)
observation = {
    "schema_version": 1,
    "record_type": "interaction_observation",
    "record_id": "observation-%03d" % number,
    "interaction_id": "interaction-%03d" % number,
    "occurred_at": "2026-09-%02dT10:00:00+00:00" % number,
    "subject": "mathematics",
    "module_id": "geometry",
    "target_kind": "knowledge_unit",
    "target_id": target_id,
    "target_name": "dihedral angle plane angle",
    "signal_kind": "content_gap",
    "signal": "cannot identify the relevant angle",
    "evidence_strength": strength,
    "interaction_kind": "knowledge_question",
    "student_action": "asked how to identify an angle",
    "uncertainty": "needs independent confirmation",
}
(observations / (observation["record_id"] + ".json")).write_text(
    json.dumps(observation), encoding="utf-8"
)

if "MUTATE-PRIOR-OBSERVATION" in prompt and existing:
    prior = json.loads(existing[0].read_text(encoding="utf-8"))
    prior["signal"] = "rewritten prior observation"
    existing[0].write_text(json.dumps(prior), encoding="utf-8")

if "PERSIST-RAW-SENTINEL" in prompt:
    (workspace / "materials" / "leak.txt").write_text(
        "PERSIST-RAW-SENTINEL", encoding="utf-8"
    )
if "PERSIST-MATERIAL" in prompt:
    (workspace / "materials" / "note.txt").write_text("saved material", encoding="utf-8")
if "PERSIST-IMAGE" in prompt:
    (workspace / "summaries" / "image.bin").write_bytes(b"\\x89PNG\\r\\n\\x1a\\nraw")
if "PERSIST-UTF16" in prompt:
    (workspace / "summaries" / "binary.bin").write_bytes(
        "PERSIST-UTF16".encode("utf-16")
    )
if "PERSIST-FILENAME" in prompt:
    (workspace / "summaries" / "PERSIST-FILENAME").touch()
if "LEAK-PRIOR" in prompt:
    (workspace / "summaries" / "prior.txt").write_text(
        "PAST-SECRET-CANARY", encoding="utf-8"
    )
if "MUTATE-STATE" in prompt:
    state_path = workspace / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["unauthorized"] = True
    state_path.write_text(json.dumps(state), encoding="utf-8")
if "REPLACE-STATE-WITH-FIFO" in prompt:
    state_path = workspace / "state.json"
    state_path.unlink()
    os.mkfifo(state_path)
if "EMPTY-SUCCESS" in prompt:
    raise SystemExit(0)

if "VISIBLE-INTERNAL-NARRATION" in prompt:
    emit("我先读取学习记录并写入观察。")
if "TWO-PREFINAL-MESSAGES" in prompt:
    emit("先抓住当前题的关键条件。")
    emit("我会再把判断过程说清楚。")
if "INTERMEDIATE-RESPONSE-CANARY" in prompt:
    emit("ANSWER-CANARY-INTERMEDIATE")

if "REMOVE-CODEX-BEFORE-GRADER" in prompt:
    Path(sys.argv[0]).unlink()

emit("reply: " + prompt)
""",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        return fake

    def _run_with_fake(self, manifest, output, fake, log, **kwargs):
        previous_log = os.environ.get("FAKE_CODEX_LOG")
        previous_artifact_root = os.environ.get("FAKE_PRIOR_ARTIFACT_ROOT")
        os.environ["FAKE_CODEX_LOG"] = str(log)
        os.environ["FAKE_PRIOR_ARTIFACT_ROOT"] = str(Path(output) / "with-history")
        try:
            return run_evaluation(
                manifest,
                output,
                codex_bin=str(fake),
                **kwargs,
            )
        finally:
            if previous_log is None:
                del os.environ["FAKE_CODEX_LOG"]
            else:
                os.environ["FAKE_CODEX_LOG"] = previous_log
            if previous_artifact_root is None:
                del os.environ["FAKE_PRIOR_ARTIFACT_ROOT"]
            else:
                os.environ["FAKE_PRIOR_ARTIFACT_ROOT"] = previous_artifact_root

    def test_dry_run_is_ungraded_and_never_invokes_codex(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [{"id": "case-a", "stages": [self._stage("first", "QUESTION")]}],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            report = self._run_with_fake(
                manifest, output, fake, log, execute=False
            )

            self.assertFalse(log.exists())
            self.assertFalse(report["executed"])
            self.assertEqual("ungraded", report["status"])
            self.assertEqual("ungraded", report["cases"][0]["status"])
            stage = report["cases"][0]["stages"][0]
            self.assertEqual("not-run", stage["execution_status"])
            self.assertEqual("ungraded", stage["status"])
            self.assertIsNone(stage["expectations"][0]["passed"])
            self.assertEqual("not executed", stage["expectations"][0]["evidence"])

    def test_report_fingerprints_the_runtime_manifest_skill_contract_and_runner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [{"id": "case-a", "stages": [self._stage("first", "QUESTION")]}],
            )
            output = root / "results"

            report = run_evaluation(manifest, output, execute=False)

            repository = Path(__file__).resolve().parents[1]
            skill_root = repository / "skills/shanghai-high-school-study-coach"
            expected = {
                "manifest": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "runner": hashlib.sha256(
                    (
                        repository / "tests/behavioral/run_cross_session_eval.py"
                    ).read_bytes()
                ).hexdigest(),
            }
            expected.update(
                {
                    "skill/" + path.relative_to(skill_root).as_posix(): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in sorted(skill_root.rglob("*"))
                    if path.is_file()
                    and not path.is_symlink()
                    and "__pycache__" not in path.parts
                    and path.suffix not in {".pyc", ".pyo"}
                }
            )
            self.assertEqual(expected, report["source_sha256"])
            persisted_report = json.loads(
                (output / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual(expected, persisted_report["source_sha256"])

    def test_manifest_hash_uses_the_same_bytes_that_were_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [{"id": "case-a", "stages": [self._stage("first", "QUESTION")]}],
            )
            parsed_bytes = manifest.read_bytes()
            replacement = json.dumps(
                {
                    "schema_version": 2,
                    "student_id": "student-b",
                    "cases": [
                        {
                            "id": "replacement",
                            "stages": [self._stage("other", "OTHER QUESTION")],
                        }
                    ],
                }
            )
            original_reader = eval_runner._read_manifest

            def read_then_replace(path):
                result = original_reader(path)
                manifest.write_text(replacement, encoding="utf-8")
                return result

            with mock.patch.object(
                eval_runner, "_read_manifest", side_effect=read_then_replace
            ):
                report = run_evaluation(manifest, root / "results", execute=False)

            self.assertEqual("student-a", report["student_id"])
            self.assertEqual(
                hashlib.sha256(parsed_bytes).hexdigest(),
                report["source_sha256"]["manifest"],
            )

    def test_executes_and_grades_every_stage_with_isolated_directories(self):
        first_prompt = "FIRST-ROUND-PRIVATE-CONTENT"
        second_prompt = "SECOND-ROUND-ONLY ANSWER-CANARY-SECOND"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "with-history",
                        "stages": [
                            self._stage(
                                "first",
                                first_prompt,
                                forbidden_texts=[
                                    {
                                        "id": "raw-question",
                                        "text": first_prompt,
                                        "source": "prompt",
                                    }
                                ],
                            ),
                            self._stage(
                                "second",
                                second_prompt,
                                count=2,
                                weak=2,
                                pending=1,
                                forbidden_texts=[
                                    {
                                        "id": "raw-question",
                                        "text": "SECOND-ROUND-ONLY",
                                        "source": "prompt",
                                    },
                                    {
                                        "id": "raw-answer",
                                        "text": "ANSWER-CANARY-SECOND",
                                        "source": "response",
                                    },
                                ],
                            ),
                        ],
                    },
                    {
                        "id": "without-history",
                        "stages": [self._stage("second", second_prompt)],
                    },
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            report = self._run_with_fake(
                manifest, output, fake, log, execute=True
            )

            calls = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            executor_calls = [call for call in calls if call["kind"] == "executor"]
            grader_calls = [call for call in calls if call["kind"] == "grader"]
            self.assertEqual(3, len(executor_calls))
            self.assertEqual(3, len(grader_calls))
            self.assertEqual(3, len({call["cwd"] for call in executor_calls}))
            artifact_paths = (
                output / "with-history" / "first" / "artifact-summary.json",
                output / "with-history" / "second" / "artifact-summary.json",
                output / "without-history" / "second" / "artifact-summary.json",
            )
            for executor_call, grader_call, artifact_path in zip(
                executor_calls, grader_calls, artifact_paths
            ):
                grader_payload = json.loads(
                    grader_call["argv"][-1].split("\nINPUT_JSON\n", 1)[1]
                )
                archived_text = artifact_path.read_text(encoding="utf-8")
                archived_summary = json.loads(archived_text)
                self.assertEqual(
                    grader_payload["artifact_summary"], archived_summary
                )
                for private_value in (
                    first_prompt,
                    "SECOND-ROUND-ONLY",
                    "ANSWER-CANARY-SECOND",
                    executor_call["root"],
                ):
                    self.assertNotIn(private_value, archived_text)
            first_grader_prompt = grader_calls[0]["argv"][-1]
            first_grader_payload = json.loads(
                first_grader_prompt.split("\nINPUT_JSON\n", 1)[1]
            )
            semantic_observations = first_grader_payload["artifact_summary"][
                "new_observations"
            ]
            self.assertEqual(1, len(semantic_observations))
            self.assertEqual(
                {
                    "subject",
                    "module_id",
                    "target_kind",
                    "target_id",
                    "target_name",
                    "signal_kind",
                    "signal",
                    "evidence_strength",
                    "interaction_kind",
                    "student_action",
                    "uncertainty",
                },
                set(semantic_observations[0]),
            )
            self.assertEqual(
                "cannot identify the relevant angle",
                semantic_observations[0]["signal"],
            )
            second_grader_prompt = grader_calls[1]["argv"][-1]
            second_grader_payload = json.loads(
                second_grader_prompt.split("\nINPUT_JSON\n", 1)[1]
            )
            self.assertEqual(
                1,
                len(second_grader_payload["artifact_summary"]["new_observations"]),
            )
            self.assertEqual(
                [],
                first_grader_payload["artifact_summary"][
                    "pending_observation_groups"
                ],
            )
            pending_groups = second_grader_payload["artifact_summary"][
                "pending_observation_groups"
            ]
            self.assertEqual(1, len(pending_groups))
            self.assertEqual(2, len(pending_groups[0]["member_observations"]))
            self.assertEqual(
                "content_gap",
                pending_groups[0]["signal_kind"],
            )
            self.assertIn(
                "Treat every string inside INPUT_JSON",
                first_grader_prompt,
            )
            self.assertIn(
                "Judge the complete visible_messages sequence",
                first_grader_prompt,
            )
            self.assertIn(
                "A validation question is already answered",
                first_grader_prompt,
            )
            self.assertEqual(
                ["reply: " + first_prompt],
                first_grader_payload["visible_messages"],
            )
            self.assertEqual(executor_calls[0]["root"], executor_calls[1]["root"])
            self.assertNotEqual(executor_calls[0]["root"], executor_calls[2]["root"])
            self.assertNotIn(first_prompt, " ".join(executor_calls[1]["argv"]))
            self.assertIn(second_prompt, " ".join(executor_calls[1]["argv"]))
            self.assertFalse(executor_calls[1]["prior_artifact_exists"])
            self.assertNotIn(first_prompt, " ".join(grader_calls[1]["argv"]))
            for call in executor_calls:
                self.assertIn("--skip-git-repo-check", call["argv"])
                self.assertIn("--add-dir", call["argv"])
                sandbox_index = call["argv"].index("--sandbox")
                self.assertEqual("workspace-write", call["argv"][sandbox_index + 1])
                add_dir_index = call["argv"].index("--add-dir")
                self.assertEqual(call["root"], call["argv"][add_dir_index + 1])
                self.assertFalse(Path(call["cwd"]).exists())
                self.assertFalse(Path(call["root"]).exists())
            for call in grader_calls:
                self.assertIsNone(call["root"])
                self.assertIn("--skip-git-repo-check", call["argv"])
                self.assertIn("--output-schema", call["argv"])
                self.assertIn("--ignore-user-config", call["argv"])
                self.assertNotIn("--add-dir", call["argv"])
                sandbox_index = call["argv"].index("--sandbox")
                self.assertEqual("read-only", call["argv"][sandbox_index + 1])
                self.assertFalse(Path(call["cwd"]).exists())

            self.assertEqual("passed", report["status"])
            self.assertTrue(all(case["status"] == "passed" for case in report["cases"]))
            self.assertFalse(report["workspace_archived"])
            self.assertNotIn("workspace_roots", report)
            self.assertFalse((output / "private-workspace-roots").exists())
            second = report["cases"][0]["stages"][1]
            self.assertEqual("completed", second["execution_status"])
            self.assertEqual("completed", second["grader_status"])
            self.assertEqual("passed", second["status"])
            self.assertTrue(second["expectations"][0]["passed"])
            self.assertTrue(all(check["passed"] for check in second["automated_checks"]))
            self.assertTrue(
                (output / "with-history" / "second" / "grader-schema.json").is_file()
            )
            self.assertEqual(
                "reply: " + second_prompt,
                (output / "with-history" / "second" / "last-message.txt").read_text(
                    encoding="utf-8"
                ),
            )
            stage_result = json.loads(
                (output / "with-history" / "second" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(64, len(stage_result["prompt_sha256"]))
            self.assertEqual(64, len(stage_result["last_message_sha256"]))
            self.assertEqual(1, stage_result["visible_message_count"])
            self.assertEqual(64, len(stage_result["visible_messages_sha256"]))
            self.assertEqual(
                ["reply: " + second_prompt],
                json.loads(
                    (
                        output
                        / "with-history"
                        / "second"
                        / "visible-messages.json"
                    ).read_text(encoding="utf-8")
                ),
            )

    def test_visible_internal_memory_narration_is_an_automated_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "visible-process",
                        "stages": [
                            self._stage("first", "VISIBLE-INTERNAL-NARRATION")
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(
                EvaluationFailed, "visible-memory-process"
            ):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            stage = report["cases"][0]["stages"][0]
            checks = {check["id"]: check for check in stage["automated_checks"]}
            self.assertFalse(checks["visible-memory-process"]["passed"])
            self.assertEqual(2, stage["visible_message_count"])
            self.assertEqual(
                [
                    "我先读取学习记录并写入观察。",
                    "reply: VISIBLE-INTERNAL-NARRATION",
                ],
                json.loads(
                    (
                        output
                        / "visible-process"
                        / "first"
                        / "visible-messages.json"
                    ).read_text(encoding="utf-8")
                ),
            )

    def test_visible_memory_process_detects_natural_language_variants(self):
        messages = (
            "我先结合此前记录再回答。",
            "我会先查看后台上下文。",
            "我先参考一下你前几次的情况。",
            "我会先查看你的学习档案。",
            "结合你之前的学习记录来看，这里要选交线夹角。",
            "我先根据你之前的学习记录来回答。",
            "你的学习记录我先看一下。",
            "我先看看你的学习档案。",
            "我先更新一下你的薄弱点。",
            "我先读一下你的学习记录。",
            "我先调出你的学习档案再回答。",
            "我先载入你以前的表现。",
            "我先查阅你的学习记录。",
            "我先看一下你以往的表现再说。",
        )

        for message in messages:
            with self.subTest(message=message):
                self.assertTrue(_visible_memory_process_markers([message]))

    def test_visible_memory_process_does_not_flag_vocabulary_explanations(self):
        messages = (
            "student ID 指学生编号。",
            "learning record 可以译为学习记录。",
            "workspace 可以译为工作区。",
            "temporary file 可以译为临时文件。",
            "temporary fact file 可以译为临时事实文件。",
            "weak signal 在这里可以译为弱线索。",
            "我会结合历史记录分析这项制度的演变。",
            "这次作业要求先查看历史记录，再比较两种解释。",
            "我先查阅这段历史记录，再判断制度为何变化。",
            "我先确认 student ID 在这个句子里是不是作主语。",
        )

        for message in messages:
            with self.subTest(message=message):
                self.assertEqual([], _visible_memory_process_markers([message]))

    def test_more_than_one_pre_final_message_is_an_automated_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "message-budget",
                        "stages": [self._stage("first", "TWO-PREFINAL-MESSAGES")],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(
                EvaluationFailed, "visible-message-budget"
            ):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            stage = report["cases"][0]["stages"][0]
            checks = {check["id"]: check for check in stage["automated_checks"]}
            self.assertFalse(checks["visible-message-budget"]["passed"])
            self.assertEqual(3, stage["visible_message_count"])

    def test_grader_isolates_wrong_opening_before_a_later_correction(self):
        response = (
            "先量两个垂足分别连向同一点形成的角。"
            "后面更正：应量垂直截面与两个半平面相交所得射线的夹角。"
        )

        opening = _opening_sentence(response)
        prompt = _grader_prompt(
            "QUESTION",
            [response],
            [
                self._expectation(
                    "current-answer",
                    "The opening sentence or clause itself must be correct.",
                )
            ],
            {},
        )
        payload = json.loads(prompt.split("\nINPUT_JSON\n", 1)[1])

        self.assertEqual("先量两个垂足分别连向同一点形成的角。", opening)
        self.assertEqual(opening, payload["opening_sentence"])
        self.assertNotIn("后面更正", payload["opening_sentence"])
        self.assertIn(
            "later sentence or\nmessage cannot repair it",
            prompt,
        )

    def test_grader_keeps_semicolon_clauses_in_the_opening_sentence(self):
        response = (
            "先找两条截面交线；再选位于题目所指二面角内部的夹角。"
            "后面才是补充说明。"
        )

        prompt = _grader_prompt(
            "QUESTION",
            [response],
            [
                self._expectation(
                    "current-answer",
                    "The complete first sentence itself must be correct.",
                )
            ],
            {},
        )
        payload = json.loads(prompt.split("\nINPUT_JSON\n", 1)[1])

        self.assertIn("opening_sentence", payload)
        self.assertEqual(
            "先找两条截面交线；再选位于题目所指二面角内部的夹角。",
            payload["opening_sentence"],
        )
        self.assertNotIn("opening_sentence_or_clause", payload)
        self.assertIn("semicolon-separated clauses", prompt)

    def test_grader_rejects_label_only_substitution_as_the_same_representation(self):
        prompt = _grader_prompt(
            "QUESTION",
            ["讲解用 OA、OB。小检查改成 RX、RY，问应量哪个角？"],
            [
                self._expectation(
                    "exactly-one-validation",
                    "The task must genuinely test angle selection.",
                )
            ],
            {},
        )

        self.assertIn(
            "mechanically substituting renamed point, ray, or letter labels into the exact symbolic relationship just taught",
            prompt,
        )
        self.assertIn(
            "For calculation or language tasks, changed values, conditions, or context can form a valid variation",
            prompt,
        )
        self.assertIn(
            "the student must carry out the task independently",
            prompt,
        )
        self.assertNotIn(
            "Renaming only points, rays, letters, or numbers does not change the representation",
            prompt,
        )
        self.assertIn(
            "exactly two already-identified rays and asking the student to write their angle name",
            prompt,
        )

    def test_response_canary_can_appear_in_an_intermediate_visible_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = "INTERMEDIATE-RESPONSE-CANARY ANSWER-CANARY-INTERMEDIATE"
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "visible-canary",
                        "stages": [
                            self._stage(
                                "first",
                                prompt,
                                forbidden_texts=[
                                    {
                                        "id": "visible-answer",
                                        "text": "ANSWER-CANARY-INTERMEDIATE",
                                        "source": "response",
                                    }
                                ],
                            )
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            report = self._run_with_fake(manifest, output, fake, log, execute=True)

            checks = {
                check["id"]: check
                for check in report["cases"][0]["stages"][0]["automated_checks"]
            }
            self.assertTrue(
                checks["response-canary:first:visible-answer"]["passed"]
            )

    def test_dynamic_target_id_is_accepted_within_expected_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stage = self._stage("first", "ALIAS-TARGET")
            stage["workspace_expectations"]["observation_targets"] = [
                {
                    "subject": "mathematics",
                    "module_id": "geometry",
                    "target_kind": "knowledge_unit",
                    "observation_count": 1,
                }
            ]
            manifest = self._write_manifest(
                root,
                [{"id": "semantic-alias", "stages": [stage]}],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            report = self._run_with_fake(
                manifest, output, fake, log, execute=True
            )

            self.assertEqual("passed", report["status"])
            target_check = next(
                check
                for check in report["cases"][0]["stages"][0]["automated_checks"]
                if check["id"] == "observation-targets"
            )
            self.assertTrue(target_check["passed"])

    def test_successful_process_with_empty_response_fails_behavioral_grade(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [{"id": "empty", "stages": [self._stage("first", "EMPTY-SUCCESS")]}],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "empty final response"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            stage = report["cases"][0]["stages"][0]
            self.assertEqual("completed", stage["execution_status"])
            self.assertEqual("not-run", stage["grader_status"])
            self.assertEqual("failed", stage["status"])
            self.assertFalse(stage["expectations"][0]["passed"])
            self.assertIn("empty final response", stage["expectations"][0]["evidence"])
            response_check = next(
                check for check in stage["automated_checks"]
                if check["id"] == "final-response-present"
            )
            self.assertFalse(response_check["passed"])

    def test_one_failed_expectation_fails_stage_case_and_overall(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expectations = [
                self._expectation("direct-answer", "Answers directly."),
                self._expectation("one-check", "FAIL-GRADE exactly one check."),
            ]
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "behavior-failure",
                        "stages": [
                            self._stage("first", "QUESTION", expectations=expectations)
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "behavioral expectations failed"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            stage = report["cases"][0]["stages"][0]
            self.assertEqual("completed", stage["execution_status"])
            self.assertEqual("completed", stage["grader_status"])
            self.assertEqual([True, False], [item["passed"] for item in stage["expectations"]])
            self.assertTrue(all(item["evidence"] for item in stage["expectations"]))
            self.assertEqual("failed", stage["status"])
            self.assertEqual("failed", report["cases"][0]["status"])
            self.assertEqual("failed", report["status"])

    def test_rejects_malformed_grader_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "bad-grader",
                        "stages": [self._stage("first", "MALFORMED-GRADER")],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "grader contract failure"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            stage = report["cases"][0]["stages"][0]
            self.assertEqual("failed", stage["grader_status"])
            self.assertFalse(stage["expectations"][0]["passed"])
            self.assertIn("grader contract failure", stage["expectations"][0]["evidence"])

    def test_workspace_privacy_strength_and_state_postconditions_are_gates(self):
        scenarios = (
            (
                "PERSIST-RAW-SENTINEL",
                [
                    {
                        "id": "raw-question",
                        "text": "PERSIST-RAW-SENTINEL",
                        "source": "prompt",
                    }
                ],
                "privacy:first:raw-question",
            ),
            ("WRONG-STRENGTH", [], "observation-strength-counts"),
            ("MUTATE-STATE", [], "state-unchanged"),
            ("PERSIST-MATERIAL", [], "materials-empty"),
            ("PERSIST-IMAGE", [], "no-media-files"),
            (
                "PERSIST-UTF16",
                [
                    {
                        "id": "raw-question",
                        "text": "PERSIST-UTF16",
                        "source": "prompt",
                    }
                ],
                "privacy:first:raw-question",
            ),
            (
                "PERSIST-FILENAME",
                [
                    {
                        "id": "raw-question",
                        "text": "PERSIST-FILENAME",
                        "source": "prompt",
                    }
                ],
                "privacy:first:raw-question",
            ),
        )
        for prompt, forbidden, failed_check_id in scenarios:
            with self.subTest(prompt=prompt), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = self._write_manifest(
                    root,
                    [
                        {
                            "id": "postcondition",
                            "stages": [
                                self._stage(
                                    "first",
                                    prompt,
                                    forbidden_texts=forbidden,
                                )
                            ],
                        }
                    ],
                )
                fake = self._write_fake_codex(root)
                output = root / "results"
                log = root / "fake-codex.jsonl"

                with self.assertRaisesRegex(EvaluationFailed, "automated checks failed"):
                    self._run_with_fake(manifest, output, fake, log, execute=True)

                report = json.loads((output / "report.json").read_text(encoding="utf-8"))
                checks = {
                    check["id"]: check
                    for check in report["cases"][0]["stages"][0]["automated_checks"]
                }
                self.assertIn(failed_check_id, checks)
                self.assertFalse(checks[failed_check_id]["passed"])

    def test_two_unrelated_observations_do_not_satisfy_pending_validation_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "unrelated-history",
                        "stages": [
                            self._stage("first", "FIRST-SIGNAL"),
                            self._stage(
                                "second",
                                "UNRELATED-SECOND",
                                count=2,
                                weak=2,
                                pending=1,
                            ),
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "pending-validation-count"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            checks = {
                check["id"]: check
                for check in report["cases"][0]["stages"][1]["automated_checks"]
            }
            self.assertFalse(checks["pending-validation-count"]["passed"])

    def test_repeated_observations_for_wrong_target_do_not_pass_semantic_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            semantic_expectations = [
                self._expectation(
                    "observation-semantic-fit",
                    "The new observation accurately summarizes the student's current difficulty.",
                )
            ]
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "wrong-target",
                        "stages": [
                            self._stage(
                                "first",
                                "WRONG-TARGET-FIRST",
                                expectations=semantic_expectations,
                            ),
                            self._stage(
                                "second",
                                "WRONG-TARGET-SECOND",
                                count=2,
                                weak=2,
                                pending=1,
                                expectations=semantic_expectations,
                            ),
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "behavioral expectations failed"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            first = report["cases"][0]["stages"][0]
            checks = {
                check["id"]: check
                for check in first["automated_checks"]
            }
            self.assertTrue(checks["observation-targets"]["passed"])
            self.assertFalse(first["expectations"][0]["passed"])

    def test_later_stage_cannot_persist_an_earlier_stage_canary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "privacy-history",
                        "stages": [
                            self._stage(
                                "first",
                                "PAST-SECRET-CANARY",
                                forbidden_texts=[
                                    {
                                        "id": "raw-question",
                                        "text": "PAST-SECRET-CANARY",
                                        "source": "prompt",
                                    }
                                ],
                            ),
                            self._stage(
                                "second",
                                "LEAK-PRIOR",
                                count=2,
                                weak=2,
                                pending=1,
                            ),
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "privacy:first:raw-question"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            second_checks = {
                check["id"]: check
                for check in report["cases"][0]["stages"][1]["automated_checks"]
            }
            self.assertFalse(second_checks["privacy:first:raw-question"]["passed"])

    def test_later_stage_cannot_rewrite_an_earlier_observation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "immutable-history",
                        "stages": [
                            self._stage("first", "FIRST-SIGNAL"),
                            self._stage(
                                "second",
                                "MUTATE-PRIOR-OBSERVATION",
                                count=2,
                                weak=2,
                                pending=1,
                            ),
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(
                EvaluationFailed, "observation-history-unchanged"
            ):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            report = json.loads((output / "report.json").read_text(encoding="utf-8"))
            second_checks = {
                check["id"]: check
                for check in report["cases"][0]["stages"][1]["automated_checks"]
            }
            self.assertFalse(second_checks["observation-history-unchanged"]["passed"])

    def test_records_and_propagates_executor_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "failure",
                        "stages": [self._stage("first", "FAIL-THIS-PHASE", count=0, weak=0)],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(EvaluationFailed, "exit code 17"):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            stage_result = json.loads(
                (output / "failure" / "first" / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(17, stage_result["exit_code"])
            self.assertEqual("failed", stage_result["execution_status"])
            self.assertEqual("failed", stage_result["status"])
            self.assertFalse(stage_result["expectations"][0]["passed"])
            self.assertEqual(
                "fake failure\n",
                (output / "failure" / "first" / "stderr.txt").read_text(encoding="utf-8"),
            )

    def test_executor_start_oserror_is_archived_as_a_stage_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "missing-executor",
                        "stages": [
                            self._stage("first", "QUESTION", count=0, weak=0)
                        ],
                    }
                ],
            )
            output = root / "results"
            missing_codex = root / "does-not-exist"

            with self.assertRaisesRegex(
                EvaluationFailed, "executor process could not start"
            ):
                run_evaluation(
                    manifest,
                    output,
                    codex_bin=str(missing_codex),
                    execute=True,
                )

            stage_dir = output / "missing-executor" / "first"
            stage_result = json.loads(
                (stage_dir / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual("failed", stage_result["execution_status"])
            self.assertIsNone(stage_result["exit_code"])
            self.assertEqual("failed", stage_result["status"])
            self.assertIn(
                "executor process could not start",
                (stage_dir / "stderr.txt").read_text(encoding="utf-8"),
            )

    def test_grader_start_oserror_is_archived_as_a_stage_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "missing-grader",
                        "stages": [
                            self._stage("first", "REMOVE-CODEX-BEFORE-GRADER")
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"

            with self.assertRaisesRegex(
                EvaluationFailed, "grader process could not start"
            ):
                self._run_with_fake(manifest, output, fake, log, execute=True)

            stage_dir = output / "missing-grader" / "first"
            stage_result = json.loads(
                (stage_dir / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual("completed", stage_result["execution_status"])
            self.assertEqual("failed", stage_result["grader_status"])
            self.assertIsNone(stage_result["grader_exit_code"])
            self.assertEqual("failed", stage_result["status"])
            self.assertIn(
                "grader process could not start",
                (stage_dir / "grader.stderr.txt").read_text(encoding="utf-8"),
            )

    def test_completed_stage_artifacts_survive_a_later_stage_exception(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "with-history",
                        "stages": [
                            self._stage("first", "FIRST-SIGNAL"),
                            self._stage(
                                "second",
                                "SECOND-SIGNAL",
                                count=2,
                                weak=2,
                                pending=1,
                            ),
                            self._stage(
                                "third",
                                "THIRD-MUST-NOT-RUN",
                                count=3,
                                weak=3,
                                pending=1,
                            ),
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"
            original_grader = eval_runner._run_grader

            def fail_later_grader(codex_bin, stage, visible_messages, artifact_summary):
                if stage["id"] == "second":
                    raise RuntimeError("later stage crashed")
                return original_grader(
                    codex_bin, stage, visible_messages, artifact_summary
                )

            with mock.patch.object(
                eval_runner, "_run_grader", side_effect=fail_later_grader
            ):
                with self.assertRaisesRegex(RuntimeError, "later stage crashed"):
                    self._run_with_fake(
                        manifest, output, fake, log, execute=True
                    )

            first_stage = output / "with-history" / "first"
            for artifact in (
                "events.jsonl",
                "stderr.txt",
                "last-message.txt",
                "visible-messages.json",
                "artifact-summary.json",
                "grader-schema.json",
                "grader.jsonl",
                "grader.stderr.txt",
                "grader.last-message.txt",
                "result.json",
            ):
                with self.subTest(artifact=artifact):
                    self.assertTrue((first_stage / artifact).is_file())
            first_result = json.loads(
                (first_stage / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual("passed", first_result["status"])
            persisted_report = json.loads(
                (output / "report.json").read_text(encoding="utf-8")
            )
            self.assertEqual("failed", persisted_report["status"])
            self.assertEqual(
                ["passed", "failed", "failed"],
                [
                    stage["status"]
                    for stage in persisted_report["cases"][0]["stages"]
                ],
            )
            calls = [
                json.loads(line)
                for line in log.read_text(encoding="utf-8").splitlines()
            ]
            executor_prompts = [
                call["argv"][-1] for call in calls if call["kind"] == "executor"
            ]
            self.assertNotIn("THIRD-MUST-NOT-RUN", executor_prompts)

    def test_state_fifo_fails_fast_without_calling_path_read_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [
                    {
                        "id": "state-fifo",
                        "stages": [
                            self._stage("first", "REPLACE-STATE-WITH-FIFO")
                        ],
                    }
                ],
            )
            fake = self._write_fake_codex(root)
            output = root / "results"
            log = root / "fake-codex.jsonl"
            original_read_bytes = Path.read_bytes

            def reject_nonregular_state(path):
                if (
                    path.name == "state.json"
                    and path.exists()
                    and not path.is_symlink()
                    and not path.is_file()
                ):
                    raise AssertionError("read_bytes called on non-regular state.json")
                return original_read_bytes(path)

            with mock.patch.object(
                Path, "read_bytes", autospec=True, side_effect=reject_nonregular_state
            ):
                with self.assertRaises(EvaluationFailed):
                    self._run_with_fake(
                        manifest, output, fake, log, execute=True
                    )

            stage_result = json.loads(
                (output / "state-fifo" / "first" / "result.json").read_text(
                    encoding="utf-8"
                )
            )
            checks = {
                check["id"]: check for check in stage_result["automated_checks"]
            }
            self.assertFalse(checks["workspace-valid"]["passed"])
            self.assertFalse(checks["state-unchanged"]["passed"])

    def test_rejects_nonempty_output_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = self._write_manifest(
                root,
                [{"id": "case-a", "stages": [self._stage("first", "QUESTION")]}],
            )
            output = root / "results"
            output.mkdir()
            (output / "stale.txt").write_text("old run", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "output directory must be empty"):
                run_evaluation(manifest, output, execute=False)

    def test_bundled_manifest_requires_cross_session_memory_and_privacy_gates(self):
        repository = Path(__file__).resolve().parents[1]
        manifest_path = (
            repository
            / "skills/shanghai-high-school-study-coach/evals/cross-session-memory.json"
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = run_evaluation(manifest_path, Path(tmp) / "dry-run", execute=False)

        self.assertEqual("ungraded", report["status"])
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_case = {case["id"]: case for case in manifest["cases"]}
        history_stages = {
            stage["id"]: stage for stage in by_case["with-history"]["stages"]
        }
        first = history_stages["first-observation"]
        second = history_stages["second-observation"]
        third = history_stages["third-existing-pending"]
        control = by_case["without-history-control"]["stages"][0]
        self.assertEqual(1, first["workspace_expectations"]["observation_count"])
        self.assertEqual(
            {"weak": 1, "repeated": 0},
            first["workspace_expectations"]["evidence_strength_counts"],
        )
        self.assertEqual(2, second["workspace_expectations"]["observation_count"])
        self.assertEqual(
            {"weak": 2, "repeated": 0},
            second["workspace_expectations"]["evidence_strength_counts"],
        )
        self.assertEqual(0, first["workspace_expectations"]["pending_validation_count"])
        self.assertEqual(1, second["workspace_expectations"]["pending_validation_count"])
        self.assertEqual(3, third["workspace_expectations"]["observation_count"])
        self.assertEqual(
            {"weak": 3, "repeated": 0},
            third["workspace_expectations"]["evidence_strength_counts"],
        )
        self.assertEqual(1, third["workspace_expectations"]["pending_validation_count"])
        self.assertEqual(1, control["workspace_expectations"]["observation_count"])
        self.assertEqual(0, control["workspace_expectations"]["pending_validation_count"])
        self.assertEqual(
            {
                "subject": "mathematics",
                "module_id": "geometry",
                "target_kind": "knowledge_unit",
                "observation_count": 2,
            },
            second["workspace_expectations"]["observation_targets"][0],
        )
        self.assertIn(
            "persist-weak-observation",
            {expectation["id"] for expectation in first["expectations"]},
        )
        self.assertIn(
            "no-unsolicited-practice",
            {expectation["id"] for expectation in first["expectations"]},
        )
        self.assertIn(
            "exactly-one-validation",
            {expectation["id"] for expectation in second["expectations"]},
        )
        self.assertIn(
            "no-unsolicited-practice",
            {expectation["id"] for expectation in third["expectations"]},
        )
        self.assertNotIn(
            "exactly-one-validation",
            {expectation["id"] for expectation in third["expectations"]},
        )
        self.assertEqual(
            3,
            third["workspace_expectations"]["observation_targets"][0][
                "observation_count"
            ],
        )
        second_expectations = {
            expectation["id"]: expectation["criterion"]
            for expectation in second["expectations"]
        }
        first_expectations = {
            expectation["id"]: expectation["criterion"]
            for expectation in first["expectations"]
        }
        control_expectations = {
            expectation["id"]: expectation["criterion"]
            for expectation in control["expectations"]
        }
        self.assertIn(
            "same point on the edge",
            first_expectations["current-answer"],
        )
        self.assertIn(
            "both perpendicular to the edge",
            first_expectations["current-answer"],
        )
        for current_answer in (
            first_expectations["current-answer"],
            second_expectations["current-answer"],
            control_expectations["current-answer"],
        ):
            self.assertIn("complete first sentence", current_answer)
            self.assertIn("taken as a whole", current_answer)
            self.assertIn("semicolon-separated clauses", current_answer)
            self.assertIn("later sentence cannot", current_answer)
            self.assertNotIn("opening sentence or clause", current_answer)
        for current_answer in (
            second_expectations["current-answer"],
            control_expectations["current-answer"],
        ):
            self.assertIn("perpendicular cross-section", current_answer)
            self.assertIn("not merely perpendicular feet", current_answer)
        self.assertIn("natural-validation-transition", second_expectations)
        self.assertIn(
            "without mentioning or implying",
            second_expectations["natural-validation-transition"],
        )
        self.assertIn(
            "prior interactions",
            second_expectations["natural-validation-transition"],
        )
        self.assertIn(
            "diagnostic process",
            second_expectations["natural-validation-transition"],
        )
        self.assertNotIn(
            "explicitly stating",
            second_expectations["natural-validation-transition"],
        )
        self.assertIn(
            "pending_observation_groups.member_observations",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "supported by every member",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "leaves it unanswered for the student",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "minimally changed context",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "answer has not appeared anywhere earlier in visible_messages",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "Changing only point or ray letters is still the same representation and must fail",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "at least two candidate angles or at least one distractor ray or angle",
            second_expectations["exactly-one-validation"],
        )
        self.assertIn(
            "no-unsolicited-practice",
            {expectation["id"] for expectation in control["expectations"]},
        )
        for case in manifest["cases"]:
            for stage in case["stages"]:
                stage_expectations = {
                    expectation["id"]: expectation["criterion"]
                    for expectation in stage["expectations"]
                }
                self.assertIn("natural-coaching-surface", stage_expectations)
                self.assertIn(
                    "complete visible_messages sequence",
                    stage_expectations["natural-coaching-surface"],
                )
                self.assertIn(
                    "observation-semantic-fit",
                    {expectation["id"] for expectation in stage["expectations"]},
                )
                sources = {
                    item["source"]
                    for item in stage["workspace_expectations"]["forbidden_texts"]
                }
                self.assertEqual({"prompt"}, sources)
                lowered_prompt = stage["prompt"].lower()
                for directive in (
                    "persist",
                    "workspace",
                    "repeated signal",
                    "validation task",
                    "structured weak",
                    "exactly one",
                ):
                    self.assertNotIn(directive, lowered_prompt)

    def test_manifest_rejects_invalid_expectations_and_duplicate_ids(self):
        valid_stage = self._stage("first", "QUESTION")
        invalid_cases = (
            [
                {"id": "same", "stages": [valid_stage]},
                {"id": "same", "stages": [self._stage("other", "QUESTION")]},
            ],
            [
                {
                    "id": "case-a",
                    "stages": [valid_stage, self._stage("first", "OTHER")],
                }
            ],
            [
                {
                    "id": "case-a",
                    "stages": [
                        self._stage(
                            "first",
                            "QUESTION",
                            expectations=[
                                self._expectation("same", "First."),
                                self._expectation("same", "Second."),
                            ],
                        )
                    ],
                }
            ],
            [
                {
                    "id": "case-a",
                    "stages": [
                        self._stage(
                            "first",
                            "DUPLICATE-CANARY",
                            forbidden_texts=[
                                {
                                    "id": "same",
                                    "text": "DUPLICATE-CANARY",
                                    "source": "prompt",
                                },
                                {
                                    "id": "same",
                                    "text": "DUPLICATE-CANARY",
                                    "source": "prompt",
                                },
                            ],
                        )
                    ],
                }
            ],
            [
                {
                    "id": "case-a",
                    "stages": [
                        {
                            **valid_stage,
                            "expectations": ["legacy string expectation"],
                        }
                    ],
                }
            ],
        )
        for index, cases in enumerate(invalid_cases):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = self._write_manifest(root, cases)
                with self.assertRaises(ValueError):
                    run_evaluation(manifest, root / "results", execute=False)

    def test_manifest_rejects_non_integer_version_and_invalid_student_ids(self):
        invalid_headers = (
            {"schema_version": 2.0, "student_id": "student-a"},
            {"schema_version": 2, "student_id": "Student_A"},
            {"schema_version": 2, "student_id": "a" * 65},
        )
        cases = [{"id": "case-a", "stages": [self._stage("first", "QUESTION")]}]
        for index, header in enumerate(invalid_headers):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                manifest = root / "manifest.json"
                manifest.write_text(
                    json.dumps({**header, "cases": cases}), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    run_evaluation(manifest, root / "results", execute=False)


if __name__ == "__main__":
    unittest.main()
