from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = (
    ROOT / "skills/shanghai-high-school-study-coach/references"
)


class ReferenceContractTest(unittest.TestCase):
    def test_only_six_subject_references_exist(self):
        references = REFERENCE_DIR.glob("*.md")
        self.assertEqual(
            {
                "chinese.md",
                "mathematics.md",
                "english.md",
                "politics.md",
                "history.md",
                "geography.md",
            },
            {path.name for path in references},
        )

    def test_language_and_mathematics_references_have_operational_sections(self):
        contracts = {
            "chinese.md": {
                "headings": ("诊断", "阅读与材料题", "作文", "练习与状态证据"),
                "phrases": (
                    "文本证据",
                    "作文",
                    "开放题",
                    "迁移验证",
                    "不能替代学生本人修改",
                    "学生水平不匹配的成品",
                ),
                "patterns": (
                    r"所有模式[^。]*不得生成[^。]*冒充学生作业[^。]*整篇替代稿",
                    r"精确分数[^。]*适用评分标准",
                    r"只有[^。]*独立迁移证据[^。]*才能提高掌握度",
                ),
            },
            "mathematics.md": {
                "headings": ("诊断", "讲解与提示", "批改", "练习与状态证据"),
                "phrases": (
                    "第一个实质错误",
                    "条件检查",
                    "推导",
                    "变式",
                    "不得虚构评分点或分数",
                ),
                "patterns": (
                    r"有限提示下完成订正[^。；]*developing",
                    r"独立完成延迟复测[^。；]*stable",
                    r"独立完成变式并解释方法[^。；]*迁移证据[^。；]*才支持\s+transferable",
                ),
                "forbidden_phrases": ("才允许提高掌握度",),
            },
            "english.md": {
                "headings": ("诊断", "阅读与翻译", "写作", "练习与状态证据"),
                "phrases": (
                    "保留学生原意",
                    "任务完成",
                    "语言准确",
                    "针对性练习",
                    "不能替代学生本人修改",
                    "学生水平不匹配的成品",
                ),
                "patterns": (
                    r"所有模式[^。]*不得生成[^。]*冒充学生作业[^。]*整篇替代稿",
                    r"适用评分标准[^。]*精确分数",
                    r"新(?:句子|段落|文本)[^。]*独立使用目标能力[^。]*才允许[^。]*提高掌握度",
                ),
            },
        }

        for filename, contract in contracts.items():
            reference = REFERENCE_DIR / filename
            content = reference.read_text(encoding="utf-8")
            headings = set(
                re.findall(r"^##[ \t]+(.+?)[ \t]*$", content, flags=re.MULTILINE)
            )

            for heading in contract["headings"]:
                phrase = f"## {heading}"
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(heading, headings)
            for phrase in contract["phrases"]:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, content)
            for phrase in contract.get("patterns", ()):
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertRegex(content, phrase)
            for phrase in contract.get("forbidden_phrases", ()):
                with self.subTest(filename=filename, phrase=f"not: {phrase}"):
                    self.assertNotIn(phrase, content)

    def test_humanities_references_have_operational_sections(self):
        contracts = {
            "politics.md": {
                "title": "政治学习与反馈",
                "headings": ("诊断", "材料边界", "答题组织", "练习与状态证据"),
                "phrases": (
                    "材料依据",
                    "概念",
                    "分点",
                    "材料不能支持的推断",
                ),
                "patterns": (
                    r"有限提示下完成针对性订正[^。；]*developing",
                    r"独立完成延迟复测[^。；]*stable",
                    r"新材料[^。；]*独立选择概念[^。；]*引用材料证据[^。；]*解释[^。；]*transferable",
                ),
                "forbidden_phrases": ("支持提高掌握度",),
            },
            "history.md": {
                "title": "历史学习与反馈",
                "headings": ("诊断", "史料题", "因果与评价", "练习与状态证据"),
                "phrases": (
                    "时间",
                    "因果",
                    "史料",
                    "证据",
                    "史料直接信息",
                    "基于背景的推断",
                    "无法由证据支持的结论",
                    "后见之明",
                    "单次证据不得越级",
                ),
                "patterns": (
                    r"区分[^。]*史料作者或材料声称的内容[^。]*已证实史实",
                    r"检查[^。]*作者[^。]*形成时间[^。]*目的[^。]*受众或情境[^。]*代表性[^。]*局限",
                    r"重要结论[^。]*其他独立史料[^。]*互证",
                    r"单一史料[^。]*不得超出[^。]*支持的边界",
                    r"有限提示下完成针对性订正[^。；]*developing",
                    r"独立完成延迟复测[^。；]*stable",
                    r"不同时期史料[^。；]*独立选择与引用证据[^。；]*因果解释[^。；]*transferable",
                ),
                "forbidden_phrases": ("支持提高掌握度",),
            },
            "geography.md": {
                "title": "地理学习与反馈",
                "headings": ("诊断", "图表与材料", "过程与因果", "练习与状态证据"),
                "phrases": (
                    "空间",
                    "图表",
                    "尺度",
                    "因果链",
                    "相关性不能直接证明因果",
                    "单次证据不得越级",
                ),
                "patterns": (
                    r"先(?:描述|识别)[^。；]*(?:可观察模式|可观察事实|图表或材料[^。；]*事实)[^。；]*再[^。；]*解释",
                    r"不得把推断[^。；]*(?:写成|冒充)[^。；]*图表直接事实",
                    r"因果解释[^。]*机制[^。]*材料依据",
                    r"不得无依据外推[^。]*时间、空间、样本或尺度之外",
                    r"有限提示下完成针对性订正[^。；]*developing",
                    r"独立完成延迟复测[^。；]*stable",
                    r"不同区域、尺度或图表[^。；]*独立选择并引用证据[^。；]*解释因果[^。；]*transferable",
                ),
                "forbidden_phrases": ("支持提高掌握度",),
            },
        }

        for filename, contract in contracts.items():
            reference = REFERENCE_DIR / filename
            content = reference.read_text(encoding="utf-8")
            titles = set(
                re.findall(r"^#[ \t]+(.+?)[ \t]*$", content, flags=re.MULTILINE)
            )
            headings = set(
                re.findall(r"^##[ \t]+(.+?)[ \t]*$", content, flags=re.MULTILINE)
            )

            with self.subTest(filename=filename, phrase=f"# {contract['title']}"):
                self.assertIn(contract["title"], titles)
            for heading in contract["headings"]:
                phrase = f"## {heading}"
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(heading, headings)
            for phrase in contract["phrases"]:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertIn(phrase, content)
            for phrase in contract["patterns"]:
                with self.subTest(filename=filename, phrase=phrase):
                    self.assertRegex(content, phrase)
            for phrase in contract["forbidden_phrases"]:
                with self.subTest(filename=filename, phrase=f"not: {phrase}"):
                    self.assertNotIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
