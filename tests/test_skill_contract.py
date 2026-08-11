from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills/shanghai-high-school-study-coach"
SKILL = PACKAGE / "SKILL.md"
OPENAI_YAML = PACKAGE / "agents/openai.yaml"


def extract_section(content, heading):
    match = re.search(
        r"^(?P<level>#{2,3}) " + re.escape(heading)
        + r"\s*$\n(?P<body>.*?)(?=^(?P=level) |\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        raise AssertionError("missing section: %s" % heading)
    return match.group("body")


class SkillContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_scope_and_triggers(self):
        match = re.match(r"^---\n(.*?)\n---", self.content, re.DOTALL)
        self.assertIsNotNone(match)
        keys = re.findall(r"^([a-z-]+):", match.group(1), re.MULTILINE)
        self.assertEqual(["name", "description"], keys)
        description = re.search(
            r"^description:\s*(.+)$", match.group(1), re.MULTILINE
        ).group(1)
        for phrase in (
            "上海高中", "真实作答", "练习", "批改", "复盘", "薄弱点",
            "针对性强化", "图片", "PDF", "跨会话",
            "语文", "数学", "英语", "政治", "历史", "地理",
        ):
            self.assertIn(phrase, description)
        for forbidden in ("物理", "化学", "生物", "考试政策", "官方网站"):
            self.assertNotIn(forbidden, description)

    def test_uses_required_section_order(self):
        self.assertEqual(
            [
                "支持边界", "定位学生工作区", "识别任务模式",
                "加载当前学科参考", "选择学习路径", "识别薄弱点",
                "当场强化与延迟复测", "记录学生表现证据",
                "更新持久化状态", "优先级和学习计划", "图片与 PDF",
                "隐私与失败",
            ],
            re.findall(r"^## (.+)$", self.content, re.MULTILINE),
        )

    def test_direct_answer_requires_detailed_explanation_and_check(self):
        section = extract_section(self.content, "直接解析路径")
        for phrase in (
            "明确要求答案时立即提供完整解析", "条件和目标", "方法选择理由",
            "关键知识及适用条件", "完整过程", "容易出错",
            "结果或结论验证", "理解检查或最小变式",
            "解析本身不改变掌握状态",
        ):
            self.assertIn(phrase, section)

    def test_guided_path_preserves_attempt_and_first_error(self):
        section = extract_section(self.content, "学习引导路径")
        for phrase in (
            "保留学生已经完成的步骤", "第一个实质错误", "定位卡点",
            "回忆知识", "提示关键中间量", "建议下一步",
        ):
            self.assertIn(phrase, section)

    def test_single_error_is_suspected_before_diagnostic_confirmation(self):
        section = extract_section(self.content, "识别薄弱点")
        self.assert_single_error_protocol(section)

    def test_single_error_protocol_rejects_opposite_mutations(self):
        section = re.sub(r"\s+", "", extract_section(self.content, "识别薄弱点"))
        mutations = (
            ("内容薄弱与执行模式分开记录。", "内容薄弱与执行模式合并记录。"),
            (
                "普通初次作答中的一次计算、审题或表达失误只记录执行模式，"
                "不降低内容状态。",
                "普通初次作答中的一次计算、审题或表达失误把`stable`降为"
                "`suspected_gap`。",
            ),
        )
        for affirmative, opposite in mutations:
            with self.subTest(opposite=opposite):
                mutated = section.replace(affirmative, opposite)
                self.assertNotEqual(section, mutated)
                with self.assertRaises(AssertionError):
                    self.assert_single_error_protocol(mutated)

        for contradiction in (
            "内容薄弱与执行模式合并记录。",
            "无需诊断证据即可降低内容状态。",
        ):
            with self.subTest(contradiction=contradiction):
                with self.assertRaises(AssertionError):
                    self.assert_single_error_protocol(section + contradiction)

        for source, destinations in self.single_error_forbidden_downgrades().items():
            for destination in destinations:
                contradiction = (
                    f"一次计算失误可以把`{source}`降为`{destination}`。"
                )
                with self.subTest(source=source, destination=destination):
                    with self.assertRaises(AssertionError):
                        self.assert_single_error_protocol(section + contradiction)

        self.assert_single_error_protocol(
            section + "一次审题失误不能把`transferable`降为`confirmed_gap`。"
        )
        self.assert_single_error_protocol(
            section + "一次审题失误可以不把`transferable`降为`confirmed_gap`。"
        )
        with self.assertRaises(AssertionError):
            self.assert_single_error_protocol(
                section
                + "一次计算失误不代表内容缺口，但可以把`stable`降为"
                "`provisionally_mastered`。"
            )
        with self.assertRaises(AssertionError):
            self.assert_single_error_protocol(
                section
                + "一次计算失误后，`stable`可以降为`provisionally_mastered`。"
            )
        with self.assertRaises(AssertionError):
            self.assert_single_error_protocol(
                section
                + "一次计算失误不能把`stable`降为`confirmed_gap`，但可以把"
                "`stable`降为`provisionally_mastered`。"
            )
        with self.assertRaises(AssertionError):
            self.assert_single_error_protocol(
                section
                + "一次计算失误不能把`stable`降为`confirmed_gap`；但可以把"
                "`stable`降为`provisionally_mastered`。"
            )
        self.assert_single_error_protocol(
            section
            + "一次表达失误可以把`stable`保持为原状态，不降为"
            "`provisionally_mastered`。"
        )

    def assert_single_error_protocol(self, section):
        normalized = re.sub(r"\s+", "", section)
        self.assertLess(normalized.index("suspected_gap"), normalized.index("confirmed_gap"))
        for clause in (
            "内容薄弱与执行模式分开记录。",
            "没有更高既有状态时",
            "单次错误涉及的内容状态只标记为`suspected_gap`（待确认线索）",
            "可以同时记录`observed_once`",
            "不得升级为`confirmed_gap`",
            "已有`provisionally_mastered`、`stable`或`transferable`时",
            "普通初次作答中的一次计算、审题或表达失误只记录执行模式，"
            "不降低内容状态",
            "无提示变式、延迟复测或迁移任务是掌握检查",
            "其失败属于诊断证据，可以把内容状态降为`confirmed_gap`",
            "只有诊断证据表明不理解相关内容时，才允许内容状态降级",
            "符合上述内容诊断门槛的新失败才可以导致降级",
        ):
            self.assertIn(clause, normalized)
        for opposite in (
            "内容薄弱与执行模式合并记录",
            "无需诊断证据即可降低内容状态",
            "内容状态按证据更新，允许新失败导致降级",
        ):
            self.assertNotIn(opposite, normalized)
        for sentence in normalized.split("。"):
            if not re.search(r"一次(?:计算|审题|表达)(?:、审题或表达)?失误", sentence):
                continue
            for clause in re.split(r"[，,；;]", sentence):
                for source, destinations in self.single_error_forbidden_downgrades().items():
                    destination_pattern = "|".join(
                        re.escape(f"`{destination}`") for destination in destinations
                    )
                    source_pattern = re.escape(f"`{source}`")
                    downgrade_target = (
                        r"[^。；，,]*降[^。；，,]*(?:"
                        + destination_pattern
                        + r")"
                    )
                    affirmative = re.search(
                        r"(?:可以把|会把|应当把|将|把)[^。；，,]*"
                        + source_pattern
                        + downgrade_target,
                        clause,
                    ) or re.search(
                        source_pattern
                        + r"[^。；，,]*(?:可以|会|将|应当)"
                        + downgrade_target,
                        clause,
                    )
                    protected = re.search(
                        r"(?:不可以把|不能把|不会把|不得把|不应当把|可以不把|"
                        r"不将|不能将|不会将|不得将|不应当将|可以不将)"
                        r"[^。；，,]*"
                        + source_pattern
                        + downgrade_target,
                        clause,
                    ) or re.search(
                        source_pattern
                        + r"[^。；，,]*(?:不会|不应当|不得|不能|不)"
                        + downgrade_target,
                        clause,
                    )
                    self.assertFalse(affirmative and not protected)

    @staticmethod
    def single_error_forbidden_downgrades():
        return {
            "provisionally_mastered": (
                "unassessed", "suspected_gap", "confirmed_gap", "strengthening",
            ),
            "stable": (
                "unassessed", "suspected_gap", "confirmed_gap", "strengthening",
                "provisionally_mastered",
            ),
            "transferable": (
                "unassessed", "suspected_gap", "confirmed_gap", "strengthening",
                "provisionally_mastered", "stable",
            ),
        }

    def test_defines_content_and_pattern_states(self):
        section = extract_section(self.content, "识别薄弱点")
        for state in (
            "unassessed", "suspected_gap", "confirmed_gap", "strengthening",
            "provisionally_mastered", "stable", "transferable",
            "observed_once", "recurring", "improving", "controlled",
        ):
            self.assertIn(state, section)

    def test_reinforcement_and_delayed_retest_are_evidence_gated(self):
        section = extract_section(self.content, "当场强化与延迟复测")
        for phrase in (
            "最小前置内容", "同类订正", "改变数字、条件、材料或表示方式",
            "延迟复测", "无提示", "没有学生表现证据", "不改变掌握状态",
        ):
            self.assertIn(phrase, section)

    def test_temporary_session_has_zero_writes(self):
        section = extract_section(self.content, "定位学生工作区")
        for phrase in (
            "临时会话不要求学生 ID", "不创建目录或文件", "不复制材料",
            "不读取或写入工作区", "不更新掌握状态、计划或计数",
        ):
            self.assertIn(phrase, section)

    def test_loads_one_subject_reference_at_a_time(self):
        section = extract_section(self.content, "加载当前学科参考")
        for name in (
            "chinese", "mathematics", "english", "politics", "history", "geography",
        ):
            self.assertIn("references/%s.md" % name, section)
        for phrase in (
            "一次只加载一个学科参考", "纯排期不加载学科参考",
            "不一次加载全部学科参考",
        ):
            self.assertIn(phrase, section)

    def test_images_and_pdfs_pause_only_for_uncertainty(self):
        section = extract_section(self.content, "图片与 PDF")
        for phrase in (
            "清晰且可可靠转写", "不强制等待确认",
            "关键内容不确定、歧义或不可读",
            "暂停答案、评分、错因诊断和持久化",
            "更清晰的局部材料或确认文本",
        ):
            self.assertIn(phrase, section)

    def test_persistent_updates_use_only_transactional_writer(self):
        section = extract_section(self.content, "更新持久化状态")
        command = (
            "python3 <skill-root>/scripts/commit_learning_state.py "
            "<workspace> --fact-file <json-file>"
        )
        self.assertIn(command, section)
        for phrase in (
            "工作区之外创建结构化事实临时文件", "只记录学生真实表现",
            "python3 <skill-root>/scripts/validate_student_data.py <workspace>",
            "删除结构化事实临时文件",
            "不得直接编辑 `state.json`、会话事实或计划事实",
        ):
            self.assertIn(phrase, section)
        self.assertNotIn("os.replace", self.content)
        self.assertNotIn("直接写入 `state.json`", self.content)

    def test_evidence_record_excludes_generated_explanations(self):
        section = extract_section(self.content, "记录学生表现证据")
        for phrase in (
            "唯一 `evidence_id`", "稳定 `session_id`",
            "学生实际回答", "提示级别", "第一个实质错误",
            "Codex 生成的答案或讲解不是掌握证据",
            "学生只说“懂了”不是掌握证据",
        ):
            self.assertIn(phrase, section)

    def test_priority_protocol_matches_confirmed_spec(self):
        section = extract_section(self.content, "优先级和学习计划")
        self.assert_priority_protocol(section)

    def test_priority_protocol_rejects_opposite_mutations(self):
        section = re.sub(
            r"\s+",
            "",
            extract_section(self.content, "优先级和学习计划"),
        )
        mutations = (
            (
                "教师明确要求或学生当前目标中的任一项，都优先于并覆盖自动排序。",
                "教师明确要求或学生当前目标中的任一项，都不覆盖自动排序。",
            ),
            (
                "自动排序必须综合比较以下六项：",
                "自动排序不考虑以下六项：",
            ),
            (
                "每个计划最多包含：",
                "每个计划不限量包含：",
            ),
            (
                "完成计划必须引用匹配学科、目标类型和目标ID的真实证据。",
                "完成计划不必引用匹配学科、目标类型和目标ID的真实证据。",
            ),
        )
        for affirmative, opposite in mutations:
            with self.subTest(opposite=opposite):
                mutated = section.replace(affirmative, opposite)
                self.assertNotEqual(section, mutated)
                with self.assertRaises(AssertionError):
                    self.assert_priority_protocol(mutated)

    def assert_priority_protocol(self, section):
        normalized = re.sub(r"\s+", "", section)
        for sentence in (
            "教师明确要求或学生当前目标中的任一项，都优先于并覆盖自动排序。",
            "自动排序必须综合比较以下六项：前置依赖影响、证据强度、重复出现频率、"
            "当前教材与教师进度、到期复测和可用时间。",
            "每个计划最多包含：1个主要内容薄弱、1个必要前置内容、"
            "1个重复出现的执行模式，以及到期复测。",
            "完成计划必须引用匹配学科、目标类型和目标ID的真实证据。",
        ):
            self.assertIn(sentence, normalized)
        for opposite in (
            "不覆盖自动排序",
            "不考虑以下六项",
            "不限量包含",
            "不必引用匹配学科、目标类型和目标ID的真实证据",
        ):
            self.assertNotIn(opposite, normalized)

    def test_portable_commands_are_documented(self):
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

    def test_policy_and_removed_template_surface_is_absent(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (SKILL, OPENAI_YAML, *sorted((PACKAGE / "references").glob("*.md")))
        )
        for forbidden in (
            "session-record-template.md", "mistake-record-template.md",
            "plans/current.md", "shanghai-curriculum-and-exams.md",
            "上海市教育考试院", "上海市教育委员会", "考试政策",
            "官方原文 URL", "qualification",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, combined)

    def test_privacy_requires_scoped_current_authorization(self):
        section = extract_section(self.content, "隐私与失败")
        for phrase in (
            "默认不向外部服务发送材料",
            "具体目的地、目的、最小发送范围和未成年人数据风险",
            "移除非必要身份信息并脱敏",
            "针对该目的地和范围的明确授权",
            "泛化授权或历史授权无效",
        ):
            self.assertIn(phrase, section)

    def test_ui_metadata_matches_confirmed_workflow(self):
        self.assertEqual(
            '''interface:
  display_name: "上海高中学习教练"
  short_description: "根据学生真实作答识别六科薄弱点，并通过针对性练习持续强化"
  default_prompt: "Use $shanghai-high-school-study-coach to diagnose my current weak points from my actual work, teach the missing part, and guide one targeted verification step."
''',
            OPENAI_YAML.read_text(encoding="utf-8"),
        )

    def test_remains_compact(self):
        self.assertLessEqual(len(self.content.splitlines()), 500)


if __name__ == "__main__":
    unittest.main()
