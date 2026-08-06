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


if __name__ == "__main__":
    unittest.main()
