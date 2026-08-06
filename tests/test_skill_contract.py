from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/shanghai-high-school-study-coach/SKILL.md"
OPENAI_YAML = ROOT / "skills/shanghai-high-school-study-coach/agents/openai.yaml"


class SkillContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = SKILL.read_text(encoding="utf-8")

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

    def test_remains_compact_and_has_no_placeholders(self):
        self.assertLessEqual(len(self.content.splitlines()), 500)
        for token in ("TODO", "TBD", "placeholder"):
            self.assertNotIn(token, self.content)

    def test_default_prompt_mentions_skill(self):
        content = OPENAI_YAML.read_text(encoding="utf-8")
        self.assertIn("$shanghai-high-school-study-coach", content)


if __name__ == "__main__":
    unittest.main()
