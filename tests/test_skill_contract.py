from pathlib import Path
import json
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "skills/shanghai-high-school-study-coach"
SKILL = PACKAGE / "SKILL.md"
OPENAI_YAML = PACKAGE / "agents/openai.yaml"
OBSERVATION_REFERENCE = PACKAGE / "references/observation-memory.md"


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
            "随手拍题", "知识点", "英文单词",
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

    def test_direct_answer_scales_detail_to_the_current_question(self):
        section = extract_section(self.content, "直接解析路径")
        for phrase in (
            "解释深度与当前问题相称", "问单词或单步理由时", "不强制凑齐",
            "不自动追加练习", "明确要求完整解题时立即提供完整解析",
            "条件和目标", "方法选择理由",
            "关键知识及适用条件", "完整过程", "容易出错",
            "结果或结论验证",
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
        positive_transfer = (
            "还要在新的表示或情境中独立完成并解释方法，才支持 `transferable`"
        )
        for phrase in (
            "最小前置内容", "同类订正", "改变数字、条件、材料或表示方式",
            "延迟复测", "无提示", "没有学生表现证据", "不改变掌握状态",
            "先达到 `stable` 后",
            positive_transfer,
            "不能把达到 `stable` 之前的当场变式追溯为迁移证据",
        ):
            self.assertIn(phrase, section)
        opposite = "即使之后在新情境中独立完成并解释方法，也不支持 `transferable`"
        self.assertNotIn(opposite, section)
        mutated = section + opposite
        with self.assertRaises(AssertionError):
            self.assertNotIn(opposite, mutated)

    def test_temporary_session_has_zero_writes(self):
        section = extract_section(self.content, "定位学生工作区")
        for phrase in (
            "没有持久化学生 ID 时使用零写入临时会话",
            "临时会话不要求学生 ID", "不创建目录或文件", "不复制材料",
            "不读取或写入工作区", "不更新掌握状态、计划或计数",
        ):
            self.assertIn(phrase, section)
        self.assertNotIn("给出已有工作区绝对路径且没有提供持久化学生 ID", section)

    def test_persistent_identity_enables_default_local_observation_memory(self):
        section = extract_section(self.content, "定位学生工作区")
        for phrase in (
            "使用持久化学生 ID", "已有工作区", "默认启用本地学习记忆",
            "不要求另行确认是否创建或保存",
            "--report-status", "`created`、`migrated` 或 `existing`",
            "`existing` 不重复这段告知",
            "没有持久化学生 ID 时使用零写入临时会话",
            "使用零写入临时会话",
            "delete_observations.py", "按学生、目标或时间删除观察",
            "缺少 ID、ID 不匹配或只有工作区路径时拒绝读取、写入或删除",
        ):
            self.assertIn(phrase, section)
        self.assertNotIn("用户明确要求跨会话保存且同意创建后", section)

    def test_existing_workspace_routes_to_validation_not_initialization(self):
        section = extract_section(self.content, "定位学生工作区")
        normalized = re.sub(r"\s+", "", section)
        self.assertIn(
            "python3<skill-root>/scripts/init_student.py--ensure--report-status<student-id>",
            normalized,
        )
        self.assertIn("`workspace`的绝对路径", normalized)
        self.assertIn("SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT", section)
        self.assertIn("--root <root>", section)
        self.assertIn("`--root` 的优先级高于环境变量", section)
        self.assertIn("`--root` 可使用绝对路径或相对路径", section)
        self.assertIn("相对路径按命令调用时的工作目录解析", section)
        self.assertIn("已有工作区", normalized)
        self.assertIn("自动迁移", normalized)
        self.assertNotIn("仅当工作区不存在时", normalized)

    def test_daily_interaction_observation_contract(self):
        section = extract_section(self.content, "定位学生工作区")
        daily = extract_section(self.content, "日常互动中的教练方式")
        canonical_fields = {
            "schema_version", "record_type", "record_id", "interaction_id",
            "occurred_at", "subject", "module_id", "target_kind", "target_id",
            "target_name", "signal_kind", "signal", "evidence_strength",
            "interaction_kind", "student_action", "uncertainty",
        }
        for field in canonical_fields:
            self.assertIn("`%s`" % field, section)
        for legacy_field in ("confidence", "observed_at"):
            self.assertNotIn("`%s`" % legacy_field, section)
        for phrase in (
            "按首次启用本地观察记忆处理并告知学生",
            "日常答疑只保存结构化观察摘要",
            "若学生明确进入批改、复盘或正式掌握验证",
            "才可能保存完成该任务所必需的作答证据",
            "不保存完整题目、原始回答、图片或 PDF",
        ):
            self.assertIn(phrase, section + daily)
        for phrase in (
            "两次不同的 interaction_id",
            "相似线索",
            "出现清晰且可复用的学习行为线索",
            "明确暴露不知道、不会判断或发生混淆",
            "即使没有提交解题尝试",
            "写入一条 `weak` 观察",
            "没有形成有效线索时不为凑记录而写入",
            "写入本轮观察前先运行进度汇总",
            "立即再次运行进度汇总",
            "写入前的历史基线",
            "观察记忆的定位、读取、写入和校验属于后台动作",
            "不得向学生播报",
            "最多一句",
            "只围绕当前学习问题",
            "同一 `subject`、`module_id`、`target_kind`、`target_id` 和 `signal_kind`",
            "不得依据单条历史或同一互动的重复写入声称重复",
            "日常观察永不直接改变正式掌握状态",
            "学生实际回答低打扰验证后",
            "满足正式证据字段",
            "低打扰验证",
            "当前问题优先",
            "不打断当前回答",
            "单次互动不升级为诊断",
            "重复事实",
            "原因和是否构成薄弱点仍待验证",
            "重复的具体表现",
            "每条成员观察都支持的最小共同表现",
            "不得把本轮更具体的细节追溯成此前也发生过",
            "正常情况下恰好加入一个",
            "至多一个",
            "直接执行重复信号中尚未完成的同一类动作",
            "不能只问前置条件、定义片段或相关但更简单的问题",
            "留给学生回答",
            "改变足以阻止照抄答案的信息",
            "答案没有在此前任何可见消息中出现",
            "不能让学生照抄或复述刚给出的答案",
            "关联空格",
            "多个彼此独立的题目或练习组",
            "延期验证",
        ):
            self.assertIn(phrase, daily)
        for phrase in (
            "未解决单次弱线索", "待验证观察", "尚未解决的观察历史",
            "`diagnostic`、`variant`、`delayed_retest` 或 `transfer`",
            "才关闭更早的对应观察",
            "字段缺失或空列表不关闭观察",
            "同一目标下其他行为线索继续保留",
            "`initial_attempt`", "`correction`", "不自动关闭观察",
            "观察事实保持不可变",
        ):
            self.assertIn(phrase, daily)

    def test_low_disruption_validation_is_a_same_round_edge_trigger(self):
        daily = extract_section(self.content, "日常互动中的教练方式")
        for phrase in (
            "只在本轮新写入的 observation",
            "`subject`、`module_id`、`target_kind`、`target_id`、`signal_kind`",
            "五个字段完全一致",
            "写入前恰好只有一个历史 `interaction_id`",
            "写入后首次达到两个不同 `interaction_id`",
            "本轮首次形成待验证组",
            "既有待验证观察不触发",
            "本轮没有新增匹配 observation 时不触发",
            "任一字段不一致时不触发",
        ):
            self.assertIn(phrase, daily)

    def test_low_disruption_validation_keeps_observation_reasoning_private(self):
        daily = extract_section(self.content, "日常互动中的教练方式")
        for phrase in (
            "最小共同表现只用于后台选题",
            "不得出现在学生可见回复中",
            "不主动告诉学生此前或不同互动出现过同类表现",
            "不提历史观察",
            "不解释造成表现的原因仍未知",
            "不使用“薄弱点”或“是否薄弱”",
            "当前答案后自然顺手加入",
        ):
            self.assertIn(phrase, daily)
        for obsolete in (
            "验证题前必须用一句自然的话交代待确认边界",
            "造成这种表现的原因尚不明确",
            "是否构成薄弱点也尚未确定",
        ):
            self.assertNotIn(obsolete, daily)

    def test_low_disruption_validation_requires_real_discrimination(self):
        daily = extract_section(self.content, "日常互动中的教练方式")
        for phrase in (
            "改变足以阻止照抄答案的信息",
            "只是重命名点、射线或字母",
            "把刚讲过的符号关系机械替换后得到答案",
            "改变数值、条件或语境可以构成最小变式",
            "独立执行待验证动作",
            "至少提供一个干扰角、干扰线或多个候选",
            "不能只给出唯一两条射线让学生照着写角名",
        ):
            self.assertIn(phrase, daily)
        self.assertNotIn("字母或数值，不算改变表示", daily)

    def test_low_disruption_validation_is_suppressed_and_not_reprompted(self):
        daily = extract_section(self.content, "日常互动中的教练方式")
        for phrase in (
            "当前互动与该观察组不相关",
            "学生表示没空",
            "只要答案",
            "希望先做当前题",
            "要求切题",
            "均不加入小检查",
            "一次触发后",
            "不得在后续普通互动再次主动提示",
            "未回答时等待学生主动回应",
            "明确进入评估或复盘",
        ):
            self.assertIn(phrase, daily)

    def test_student_visible_transition_hides_all_memory_process(self):
        daily = extract_section(self.content, "日常互动中的教练方式")
        for phrase in (
            "关键答案必须准确且自足",
            "不能把“两个垂足分别连向同一点”当作关键答案",
            "一般定义场景",
            "棱上同一点",
            "分别位于两个面内且都垂直于棱",
            "只有题目已给出垂直于棱的截面时",
            "朝向题目所指二面角内部",
            "不得提及学习记录或此前记录",
            "不得说明会查看、确认或结合任何后台上下文",
            "需要多个后台步骤时连续完成",
            "不得另发“我会把……说清楚”一类计划句",
            "发出后不得再发送计划或过渡消息",
            "下一条可见消息必须是完整答案",
            "当前输入已经足以作答",
            "尚未读取图片或 PDF",
            "只说明正在辨认题面和学生标注",
            "不得猜测题意或结论",
        ):
            self.assertIn(phrase, daily)

        self.assertIn(
            "可以说“已知截面垂直于棱时，关键是量截面与两个面的交线"
            "所成、且位于所指二面角内部的角”",
            daily,
        )
        self.assertIn(
            "不能说“我先结合你之前的学习记录确认一下”",
            daily,
        )

    def test_repeated_signal_contract_includes_minimum_common_example(self):
        daily = extract_section(self.content, "日常互动中的教练方式")
        for phrase in (
            "在图中分不清哪个角是二面角的平面角",
            "作出截面后不知道选哪个角",
            "两次都在判断哪个角是二面角的平面角时卡住",
            "两次都在作出截面后不知道选哪个角",
            "逐条比较汇总中的成员观察",
            "不能只采用顶层代表性 `signal`",
        ):
            self.assertIn(phrase, daily)

    def test_observation_reference_makes_persistence_operational(self):
        self.assertTrue(OBSERVATION_REFERENCE.is_file())
        reference = OBSERVATION_REFERENCE.read_text(encoding="utf-8")
        daily = extract_section(self.content, "日常互动中的教练方式")
        self.assertIn("references/observation-memory.md", daily)
        for phrase in (
            "`target_kind`", "`interaction_kind`", "`evidence_strength`",
            "`pending-normalization`", "同一次学生互动", "幂等重试",
            "每次日常互动的新观察一律写 `weak`",
            "复用同一组", "写入后重新运行", "summarize_progress.py",
            "`^[a-z0-9][a-z0-9-]{0,95}$`",
            "不要使用大写 `T`",
            "提问本身是唯一可观察行为",
            "尚未观察到独立表现",
            "不得写成学生已经尝试或答错",
            "`resolves_observation_signal_kinds`",
            "字段缺失或列表为空时不关闭任何观察",
            "同一目标下未列出的其他 `signal_kind` 保持未解决",
        ):
            self.assertIn(phrase, reference)

    def test_daily_behavioral_cases_cover_observation_lifecycle(self):
        cases = json.loads((ROOT / "tests/behavioral/cases.json").read_text(encoding="utf-8"))
        by_id = {case["id"]: case for case in cases}
        for case_id in ("ordinary-question-first", "repeated-observation-validation"):
            self.assertIn(case_id, by_id)
        ordinary = by_id["ordinary-question-first"]
        self.assertIn("直接解释零乘积性质", ordinary["must"])
        self.assertIn("不要求先确认任务模式", ordinary["must"])
        self.assertNotIn("可保留低强度结构化观察", ordinary["must"])
        self.assertIn("向学生公开后台观察或记录动作", ordinary["must_not"])
        repeated = by_id["repeated-observation-validation"]
        self.assertIn("interaction-001", repeated["prompt"])
        self.assertIn("interaction-002", repeated["prompt"])
        self.assertNotIn("请说明如何处理", repeated["prompt"])

        required = "\n".join(repeated["must"])
        for phrase in (
            "不公开提及历史观察、跨互动重复或薄弱点判断",
            "当前答案后自然顺手加入",
            "恰好一个最小、低打扰验证任务",
            "关联空格",
        ):
            self.assertIn(phrase, required)
        self.assertNotIn("首次启用时告知本地观察记忆", required)
        self.assertNotIn("继续先回答当前问题", required)

        forbidden = "\n".join(repeated["must_not"])
        self.assertIn("向学生播报历史观察、跨互动重复或诊断过程", forbidden)
        self.assertIn("把重复表现直接断言为内容薄弱或具体原因", forbidden)
        self.assertIn("安排两个彼此独立的句子或编号题", forbidden)
        self.assertIn("为验证打断当前答疑", forbidden)

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
            "<workspace> --fact-file <json-file> --student-id <student-id>"
        )
        self.assertIn(command, section)
        for phrase in (
            "工作区之外创建结构化事实临时文件", "只记录学生真实表现",
            "python3 <skill-root>/scripts/validate_student_data.py <workspace> --student-id <student-id>",
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
            "`resolves_observation_signal_kinds`",
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
            "python3 <skill-root>/scripts/init_student.py --ensure --report-status <student-id>",
            "python3 <skill-root>/scripts/init_student.py --ensure --report-status --root <root> <student-id>",
            "python3 <skill-root>/scripts/validate_student_data.py <workspace> --student-id <student-id>",
            "python3 <skill-root>/scripts/summarize_progress.py <workspace> --student-id <student-id>",
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
  short_description: "自然回答上海高中六科问题，并跨会话识别和验证薄弱点"
  default_prompt: "Use $shanghai-high-school-study-coach to answer an ordinary question naturally, prioritize the current question, and use gradual observation of recurring signals to guide teaching or targeted practice without forcing a diagnosis first."
''',
            OPENAI_YAML.read_text(encoding="utf-8"),
        )
        prompt = OPENAI_YAML.read_text(encoding="utf-8")
        for phrase in ("ordinary question", "current question", "gradual observation"):
            self.assertIn(phrase, prompt)
        self.assertIn("without forcing a diagnosis first", prompt)
        self.assertNotIn("diagnose my current weak points", prompt)

    def test_remains_compact(self):
        self.assertLessEqual(len(self.content.splitlines()), 500)


if __name__ == "__main__":
    unittest.main()
