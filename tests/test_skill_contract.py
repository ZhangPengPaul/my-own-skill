from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/shanghai-high-school-study-coach/SKILL.md"
OPENAI_YAML = ROOT / "skills/shanghai-high-school-study-coach/agents/openai.yaml"
SESSION_TEMPLATE = (
    ROOT / "skills/shanghai-high-school-study-coach/assets/session-record-template.md"
)
PLAN_TEMPLATE = (
    ROOT
    / "skills/shanghai-high-school-study-coach/assets/student-workspace-template/plans/current.md"
)


def extract_learning_loop_step(content, step_number):
    section = re.search(
        r"^## 执行学习闭环\s*$\n(?P<body>.*?)(?=^## |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if section is None:
        raise AssertionError("missing learning loop section")
    step = re.search(
        rf"^{step_number}\.\s+(?P<text>.*?)(?=^\d+\.\s+|^## |\Z)",
        section.group("body"),
        re.MULTILINE | re.DOTALL,
    )
    if step is None:
        raise AssertionError(f"missing learning loop step {step_number}")
    return "".join(line.strip() for line in step.group("text").splitlines())


class SkillContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = SKILL.read_text(encoding="utf-8")
        cls.learning_step_3 = extract_learning_loop_step(cls.content, 3)
        cls.learning_step_8 = extract_learning_loop_step(cls.content, 8)

    def test_frontmatter_has_only_name_and_description(self):
        match = re.match(r"^---\n(.*?)\n---", self.content, re.DOTALL)
        self.assertIsNotNone(match)
        keys = re.findall(r"^([a-z-]+):", match.group(1), re.MULTILINE)
        self.assertEqual(["name", "description"], keys)

    def test_has_all_task_modes_and_learning_steps(self):
        for token in (
            "assessment", "explanation", "practice", "grading", "review", "planning",
            "诊断", "讲解", "练习", "反馈", "错题", "掌握度", "学习计划",
        ):
            self.assertIn(token, self.content)

    def test_requires_evidence_and_uncertainty_handling(self):
        for phrase in (
            "学生表现证据", "不得提高掌握度", "图片或 PDF", "要求用户确认",
            "assets/session-record-template.md", "assets/mistake-record-template.md",
        ):
            self.assertIn(phrase, self.content)

    def test_maps_phase_one_subject_references(self):
        for name in ("chinese", "mathematics", "english", "politics", "history", "geography"):
            self.assertIn("references/%s.md" % name, self.content)

    def test_remains_compact_and_has_no_forbidden_markers(self):
        self.assertLessEqual(len(self.content.splitlines()), 500)
        for token in ("TO" + "DO", "T" + "BD", "place" + "holder"):
            self.assertNotIn(token, self.content)

    def test_default_prompt_mentions_skill(self):
        content = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn("$shanghai-high-school-study-coach", content)

    def test_uses_portable_python_commands_from_skill_root(self):
        self.assertIn(
            "`<skill-root>` 表示当前 `SKILL.md` 所在目录",
            self.content,
        )
        for command in (
            "python3 <skill-root>/scripts/init_student.py --root <private-root> <student-id>",
            "python3 <skill-root>/scripts/validate_student_data.py <workspace>",
            "python3 <skill-root>/scripts/summarize_progress.py <workspace>",
        ):
            self.assertIn(command, self.content)
        unsafe_paths = re.findall(
            r"(?<!<skill-root>/)scripts/(?:init_student|validate_student_data|summarize_progress)\.py",
            self.content,
        )
        self.assertEqual([], unsafe_paths)

    def test_validates_candidate_before_atomic_state_replacement(self):
        for phrase in (
            "不得先覆写 `state.json` 再校验",
            "`<skill-root>/scripts/validate_student_data.py` 中的 "
            "`validate_state(candidate, workspace)`",
            "任何校验、写入或替换失败",
            "删除己方临时文件",
            "保留原 `state.json`",
            "CLI 只检查已落盘工作区，不能直接验证候选对象",
        ):
            self.assertIn(phrase, self.content)
        ordered = (
            "构造候选 `state` 对象",
            "`validate_state(candidate, workspace)`",
            "`state.json` 同目录的唯一临时文件",
            "同文件系统原子替换",
            "替换后再运行 `python3 <skill-root>/scripts/validate_student_data.py <workspace>`",
        )
        positions = [self.content.index(phrase) for phrase in ordered]
        self.assertEqual(sorted(positions), positions)

    def test_temporary_session_never_touches_workspace_or_progress(self):
        for phrase in (
            "临时会话不要求学生 ID",
            "不创建目录或文件",
            "不复制材料",
            "不读取或写入工作区",
            "不更新掌握度、计划或计数",
            "仅已有工作区或用户明确同意创建后",
        ):
            self.assertIn(phrase, self.content)

    def test_uncertain_material_pauses_every_mode_before_any_conclusion(self):
        for phrase in (
            "不确定材料规则适用于所有任务模式",
            "用户确认前暂停答案、评分、错因诊断和所有持久化",
            "只能展示不确定片段，并请求更清晰的局部材料或确认文本",
        ):
            self.assertIn(phrase, self.learning_step_3)
        for condition in ("不确定", "歧义", "不可读", "可能影响结论"):
            self.assertIn(condition, self.learning_step_3)
        self.assertRegex(
            self.learning_step_3,
            r"只有关键内容.*不确定.*歧义.*不可读.*影响结论时，才要求用户确认",
        )

    def test_clear_reliable_material_continues_without_confirmation(self):
        for phrase in (
            "先判断可辨性",
            "清晰且可可靠转写",
            "不强制等待确认",
            "直接继续诊断或批改",
        ):
            self.assertIn(phrase, self.learning_step_3)
        self.assertRegex(
            self.learning_step_3,
            r"清晰且可可靠转写.*不强制等待确认，直接继续诊断或批改",
        )

    def test_review_with_actionable_issue_and_transfer_uses_correction_and_variant(self):
        for phrase in (
            "发现可行动错因或改进点时",
            "当前订正任务",
            "该能力适合迁移验证时",
            "同时说明后续变式验证",
            "变式可安排在学生订正后",
            "不立即给完整解答",
        ):
            self.assertIn(phrase, self.learning_step_8)
        self.assertRegex(
            self.learning_step_8,
            r"发现可行动错因或改进点时.*当前订正任务.*"
            r"该能力适合迁移验证时.*同时说明后续变式验证",
        )

    def test_review_without_issue_or_transfer_does_not_force_follow_up(self):
        for phrase in (
            "答案已完整正确",
            "任务本身不适合变式",
            "不得虚构订正点或强行添加变式",
            "简短核验结论或其他合适后续结束",
        ):
            self.assertIn(phrase, self.learning_step_8)
        self.assertRegex(
            self.learning_step_8,
            r"答案已完整正确或任务本身不适合变式时，"
            r"不得虚构订正点或强行添加变式",
        )

    def test_process_fields_are_reconciled_from_unique_completed_facts(self):
        for phrase in (
            "从已落盘事实对账重算",
            "唯一稳定 `session_id`",
            "`status: completed`",
            "incomplete",
            "重复 `session_id`",
            "唯一稳定 `item_id`",
            "完成证据存在",
            "缺少证据或重复 `item_id`",
        ):
            self.assertIn(phrase, self.content)
        self.assertNotIn("recorded_sessions += 1", self.content)
        self.assertNotRegex(self.content, r"completed_plan_items\s*\+=")

    def test_progress_reconciliation_and_retries_are_idempotent(self):
        for phrase in (
            "重试同一会话必须复用同一 `session_id`",
            "不能生成第二条记录",
            "同一组事实文件重复执行对账得到相同计数",
            "忽略 `updated_at`",
            "确有变化时才更新 `updated_at`",
            "no-op",
            "保留原时间戳",
            "中断后重试从事实文件恢复，不依赖内存增量",
        ):
            self.assertIn(phrase, self.content)
        facts = self.content.index("会话记录和计划记录先以同目录唯一临时文件原子替换")
        reconciliation = self.content.index("再从已落盘事实对账重算")
        self.assertLess(facts, reconciliation)

    def test_session_and_plan_templates_define_stable_completion_records(self):
        session = SESSION_TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("- session_id:", session)
        self.assertIn("- status: incomplete", session)
        for phrase in (
            "记录完整且成功落盘",
            "同目录唯一临时文件",
            "原子替换",
            "`status: completed`",
        ):
            self.assertIn(phrase, session)

        plan = PLAN_TEMPLATE.read_text(encoding="utf-8")
        for field in (
            "- item_id:",
            "- subject:",
            "- task:",
            "- estimated_effort:",
            "- status:",
            "- evidence:",
        ):
            self.assertIn(field, plan)
        for phrase in (
            "唯一稳定",
            "`status: completed`",
            "完成证据",
        ):
            self.assertIn(phrase, plan)

    def test_external_sharing_requires_scoped_current_authorization(self):
        for phrase in (
            "默认不向外部服务发送材料",
            "具体目的地、目的、最小发送范围和未成年人数据风险",
            "移除非必要身份信息并脱敏",
            "针对该目的地和范围的明确授权",
            "泛化授权或历史授权无效",
        ):
            self.assertIn(phrase, self.content)

    def test_planning_loads_subject_references_one_at_a_time_only_when_needed(self):
        for phrase in (
            "纯排期不加载学科参考",
            "涉及学科内容时逐科按需读取",
            "一次只加载一个学科参考",
            "不一次加载全部学科参考",
        ):
            self.assertIn(phrase, self.content)

    def test_phase_one_science_boundary_cannot_be_bypassed_by_files(self):
        for phrase in (
            "无论对应目录或参考文件是否存在",
            "合格考适配均未完成且未验收",
            "第二阶段验收后必须显式修改本节边界",
        ):
            self.assertIn(phrase, self.content)


if __name__ == "__main__":
    unittest.main()
