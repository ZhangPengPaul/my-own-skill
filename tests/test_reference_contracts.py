from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT
    / "skills/shanghai-high-school-study-coach/references"
    / "shanghai-curriculum-and-exams.md"
)


class ReferenceContractTest(unittest.TestCase):
    def read_reference(self):
        return REFERENCE.read_text(encoding="utf-8")

    def verified_source_rows(self, content):
        expected_header = [
            "发布机构",
            "完整标题",
            "发布日期或更新日期",
            "获取日期",
            "URL 或文档标识",
            "适用范围",
        ]
        lines = content.splitlines()
        header_index = None
        for index, line in enumerate(lines):
            if not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells == expected_header:
                header_index = index
                break
        self.assertIsNotNone(header_index, "missing six-column source table header")

        rows = []
        for line in lines[header_index + 1 :]:
            if not line.strip().startswith("|"):
                break
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
                continue
            self.assertEqual(6, len(cells), line)
            self.assertTrue(all(cells), line)
            rows.append(cells)
        return rows

    def test_source_governance_is_explicit(self):
        content = self.read_reference()
        for token in (
            "上海市教育委员会",
            "https://edu.sh.gov.cn/",
            "上海市教育考试院",
            "https://www.shmeea.edu.cn/",
            "发布日期",
            "获取日期",
            "适用范围",
            "来源冲突",
        ):
            self.assertIn(token, content)

    def test_verified_source_table_has_complete_official_rows(self):
        rows = self.verified_source_rows(self.read_reference())
        self.assertGreaterEqual(len(rows), 6)

        allowed_origins = (
            "https://edu.sh.gov.cn/",
            "https://www.shmeea.edu.cn/",
        )
        for row in rows:
            urls = re.findall(r"https://[^\s（）()]+", row[4])
            self.assertGreaterEqual(len(urls), 1, row[4])
            for url in urls:
                self.assertTrue(url.startswith(allowed_origins), url)

        rendered_rows = "\n".join(" | ".join(row) for row in rows)
        for marker in (
            "AA4304003-2021-004",
            "AA4322004-2021-004",
            "AA4304003-2025-003",
            "AA4304003-2025-004",
            "AA4304003-2026-002",
            "2026年上海市普通高中学业水平等级性考试即将举行",
        ):
            self.assertIn(marker, rendered_rows)

    def test_exam_goals_can_overlap_and_require_student_confirmation(self):
        compact = re.sub(r"\s+", "", self.read_reference())
        for phrase in (
            "同一学科可同时承担计分考试与合格考目标",
            "只能来自`profile.md`或用户确认",
            "不能从默认九科列表自动推断",
        ):
            self.assertIn(phrase, compact)

    def test_language_and_mathematics_references_have_operational_sections(self):
        contracts = {
            "chinese.md": {
                "headings": ("诊断", "阅读与材料题", "作文", "练习与状态证据"),
                "phrases": (
                    "文本证据",
                    "作文",
                    "开放题",
                    "迁移验证",
                    "所有模式都不得生成可直接冒充学生作业的整篇替代稿",
                    "复盘可以提供提纲、局部示范、逐段批注或明确标注的比较学习范文",
                    "不能替代学生本人修改",
                    "不得输出与学生水平不匹配的成品",
                    "涉及精确分数时必须有适用评分标准",
                    "只有在新文本中复用方法的独立迁移证据，才能提高掌握度",
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
                    "只有独立完成变式并解释方法的迁移证据，才允许提高掌握度",
                ),
            },
            "english.md": {
                "headings": ("诊断", "阅读与翻译", "写作", "练习与状态证据"),
                "phrases": (
                    "保留学生原意",
                    "任务完成",
                    "语言准确",
                    "针对性练习",
                    "所有模式都不得生成可直接冒充学生作业的整篇替代稿",
                    "复盘可以提供提纲、局部示范、逐段批注或明确标注的比较学习范文",
                    "不能替代学生本人修改",
                    "不得输出与学生水平不匹配的成品",
                    "没有适用评分标准时，不给精确分数",
                    "学生必须在新句子、新段落或新文本中独立使用目标能力，才允许提高掌握度",
                ),
            },
        }

        for filename, contract in contracts.items():
            reference = REFERENCE.parent / filename
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


if __name__ == "__main__":
    unittest.main()
