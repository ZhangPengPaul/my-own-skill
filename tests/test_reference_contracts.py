from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / "skills/shanghai-high-school-study-coach/references"
REQUIRED_HEADINGS = {
    "固定模块",
    "动态知识单元归一化",
    "诊断",
    "详细解析",
    "强化与迁移",
}
MODULES = {
    "chinese.md": {
        "language-and-accumulation", "classical-texts", "modern-reading",
        "writing", "integrated-expression",
    },
    "mathematics.md": {
        "sets-and-logic", "algebra-and-functions", "geometry",
        "probability-and-statistics", "modeling-and-applications",
    },
    "english.md": {
        "vocabulary-and-grammar", "reading", "translation", "writing",
        "integrated-language-use",
    },
    "politics.md": {
        "concepts-and-principles", "material-analysis",
        "reasoning-and-argument", "answer-organization",
    },
    "history.md": {
        "chronology-and-facts", "source-analysis", "causation-and-change",
        "comparison-and-evaluation", "historical-expression",
    },
    "geography.md": {
        "maps-and-space", "data-and-charts", "processes-and-mechanisms",
        "regional-analysis", "human-environment",
    },
}
SUBJECT_RULES = {
    "chinese.md": (
        "文本证据", "学生本人修改", "新文本", "独立组织有依据的回答",
    ),
    "mathematics.md": (
        "第一个实质错误", "条件检查", "改变条件或表示方式",
        "独立解释方法和适用条件",
    ),
    "english.md": (
        "保留学生原意", "意义不变", "新句子、段落或文本",
        "独立完成意义准确的表达",
    ),
    "politics.md": (
        "概念与材料", "材料依据", "新材料",
        "独立选择概念并解释概念与材料的联系",
    ),
    "history.md": (
        "史料局限", "证据支持边界", "不同时期或来源的史料",
        "独立引用证据形成受史料限制的解释",
    ),
    "geography.md": (
        "观察与推断", "不得把推断写成图表直接事实",
        "不同区域、尺度或图表", "独立引用数据并解释机制",
    ),
}


class ReferenceContractTest(unittest.TestCase):
    def test_only_six_subject_references_exist(self):
        self.assertEqual(
            set(MODULES),
            {path.name for path in REFERENCE_DIR.glob("*.md")},
        )

    def test_each_adapter_has_exact_operational_headings(self):
        for filename in MODULES:
            content = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
            headings = set(re.findall(r"^## (.+)$", content, re.MULTILINE))
            with self.subTest(filename=filename):
                self.assertEqual(REQUIRED_HEADINGS, headings)

    def test_each_adapter_lists_exact_fixed_modules(self):
        for filename, expected in MODULES.items():
            content = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
            module_section = re.search(
                r"^## 固定模块\s*$\n(?P<body>.*?)(?=^## |\Z)",
                content,
                re.MULTILINE | re.DOTALL,
            )
            self.assertIsNotNone(module_section, filename)
            actual = set(
                re.findall(
                    r"^\| `([a-z0-9-]+)` \|",
                    module_section.group("body"),
                    re.MULTILINE,
                )
            )
            with self.subTest(filename=filename):
                self.assertEqual(expected, actual)

    def test_each_adapter_defines_conservative_normalization(self):
        phrases = (
            "相同学习目标和前置边界",
            "当前材料中可以证明两个名称等价",
            "适用条件、证据类型或前置要求不同",
            "pending-normalization",
            "不能可靠映射时不猜测",
        )
        for filename in MODULES:
            content = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
            section = re.search(
                r"^## 动态知识单元归一化\s*$\n(?P<body>.*?)(?=^## |\Z)",
                content,
                re.MULTILINE | re.DOTALL,
            ).group("body")
            for phrase in phrases:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, section)

    def test_each_adapter_distinguishes_content_and_execution(self):
        for filename in MODULES:
            content = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
            for phrase in (
                "内容薄弱", "执行模式", "追问或最小诊断",
                "一次失误不自动建立内容薄弱点",
            ):
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, content)

    def test_each_adapter_defines_detailed_explanation_and_two_stage_practice(self):
        for filename in MODULES:
            content = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
            for phrase in (
                "条件和目标", "方法选择理由", "关键知识及适用条件",
                "完整过程", "容易出错", "结果或结论验证",
                "一道同类订正", "一道改变情境的变式", "独立迁移",
            ):
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, content)

    def test_subject_specific_behavior_is_preserved(self):
        for filename, phrases in SUBJECT_RULES.items():
            content = (REFERENCE_DIR / filename).read_text(encoding="utf-8")
            for phrase in phrases:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, content)

    def test_policy_verification_surface_is_absent(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(REFERENCE_DIR.glob("*.md"))
        )
        for forbidden in (
            "上海市教育考试院", "上海市教育委员会", "考试政策",
            "官方原文 URL", "外部政策", "qualification",
        ):
            self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
