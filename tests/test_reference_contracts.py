from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE = (
    ROOT
    / "skills/shanghai-high-school-study-coach/references"
    / "shanghai-curriculum-and-exams.md"
)


class ReferenceContractTest(unittest.TestCase):
    def test_source_governance_is_explicit(self):
        content = REFERENCE.read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
