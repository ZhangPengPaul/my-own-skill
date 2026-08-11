from pathlib import Path
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
BEHAVIORAL = ROOT / "tests/behavioral"
FIXTURES = BEHAVIORAL / "fixtures"
GENERATOR_PATH = BEHAVIORAL / "generate_fixtures.py"
FIXTURE_NAMES = ("math-exam.pdf", "english-essay.svg")
EXPECTED_IDS = {
    "math-guided-diagnosis",
    "math-direct-explanation",
    "english-writing",
    "chinese-text-evidence",
    "politics-material-link",
    "history-source-limits",
    "geography-fact-versus-inference",
    "single-error-needs-confirmation",
    "reinforcement-and-delayed-retest",
    "multi-weakness-priority",
    "unreadable-input",
    "no-evidence-no-mastery",
}
SUBJECT_LOOP_CASES = {
    "语文": "chinese-text-evidence",
    "数学": "reinforcement-and-delayed-retest",
    "英语": "english-writing",
    "政治": "politics-material-link",
    "历史": "history-source-limits",
    "地理": "geography-fact-versus-inference",
}
LOOP_OUTPUT_MARKERS = (
    "内容问题",
    "执行模式",
    "suspected_gap",
    "confirmed_gap",
    "strengthening",
    "provisionally_mastered",
    "stable",
    "讲解不作为掌握证据",
)
MATH_LINES = (
    "Fictional mathematics review",
    "1. Solve x^2 - 5x + 6 = 0.",
    "Student answer: x = 2. The second root was omitted.",
    "2. For y = (x - 1)^2 + 3, state the vertex.",
    "Student answer: (1, -3).",
)
ESSAY_LINES = (
    "My weekend volunteer work",
    "Last Saturday I go to the community library.",
    "I helped children find books and read stories.",
    "Although I was tired, but I felt useful.",
    "I hope to join the activity again next month.",
)
SVG_NAMESPACE = "http://www.w3.org/2000/svg"


def load_generator():
    spec = importlib.util.spec_from_file_location("fixture_generator", GENERATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATOR = load_generator()


class BehavioralFixtureTest(unittest.TestCase):
    def assert_svg(self, path):
        root = ET.parse(path).getroot()
        self.assertEqual(f"{{{SVG_NAMESPACE}}}svg", root.tag)
        self.assertEqual("900", root.attrib.get("width"))
        self.assertEqual("280", root.attrib.get("height"))
        texts = [
            element.text
            for element in root.findall(f"{{{SVG_NAMESPACE}}}text")
        ]
        self.assertEqual(list(ESSAY_LINES), texts)

    def test_generator_is_isolated_and_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_output = Path(first)
            second_output = Path(second)
            GENERATOR.generate_fixtures(first_output)
            subprocess.run(
                [
                    sys.executable,
                    str(GENERATOR_PATH),
                    "--output-dir",
                    str(second_output),
                ],
                check=True,
            )

            for name in FIXTURE_NAMES:
                with self.subTest(name=name):
                    first_bytes = (first_output / name).read_bytes()
                    second_bytes = (second_output / name).read_bytes()
                    committed_bytes = (FIXTURES / name).read_bytes()
                    self.assertEqual(first_bytes, second_bytes)
                    self.assertEqual(first_bytes, committed_bytes)

    def test_pdf_has_consistent_classic_xref_and_content_length(self):
        pdf = (FIXTURES / "math-exam.pdf").read_bytes()
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertNotIn(b"\r", pdf)
        self.assertNotIn(b"\x00", pdf)

        startxref_match = re.search(br"startxref\n(\d+)\n%%EOF\n$", pdf)
        self.assertIsNotNone(startxref_match)
        xref_offset = int(startxref_match.group(1))
        self.assertTrue(pdf[xref_offset:].startswith(b"xref\n"))

        trailer_offset = pdf.index(b"trailer\n", xref_offset)
        xref_lines = pdf[xref_offset:trailer_offset].splitlines(keepends=True)
        self.assertEqual(b"xref\n", xref_lines[0])
        self.assertEqual(b"0 6\n", xref_lines[1])
        entries = xref_lines[2:]
        self.assertEqual(6, len(entries))
        for entry in entries:
            self.assertEqual(20, len(entry))
            self.assertRegex(entry, br"^\d{10} \d{5} [fn] \n$")

        for object_number, entry in enumerate(entries[1:], start=1):
            offset = int(entry[:10])
            marker = f"{object_number} 0 obj\n".encode("ascii")
            self.assertTrue(pdf[offset:].startswith(marker), marker)

        contents_offset = int(entries[4][:10])
        contents_end = pdf.index(b"\nendobj\n", contents_offset)
        contents_object = pdf[contents_offset:contents_end]
        stream_match = re.match(
            br"4 0 obj\n<< /Length (\d+) >>\nstream\n", contents_object
        )
        self.assertIsNotNone(stream_match)
        stream_start = stream_match.end()
        stream_end = contents_object.index(b"endstream", stream_start)
        stream = contents_object[stream_start:stream_end]
        self.assertEqual(int(stream_match.group(1)), len(stream))
        for line in MATH_LINES:
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            self.assertIn((f"({escaped}) Tj").encode("ascii"), stream)

    def test_svg_is_well_formed_and_has_expected_text(self):
        self.assert_svg(FIXTURES / "english-essay.svg")

    def test_svg_writer_escapes_xml_text(self):
        with tempfile.TemporaryDirectory() as output_dir:
            path = Path(output_dir) / "escaped.svg"
            GENERATOR.write_svg(path, ["A & B", "x < y"])
            texts = [
                element.text
                for element in ET.parse(path)
                .getroot()
                .findall(f"{{{SVG_NAMESPACE}}}text")
            ]
            self.assertEqual(["A & B", "x < y"], texts)

    def test_case_catalog_has_strict_phase_one_schema(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        self.assertIs(type(cases), list)
        self.assertEqual(12, len(cases))

        ids = set()
        for index, case in enumerate(cases):
            with self.subTest(index=index, case=case):
                self.assertIs(type(case), dict)
                self.assertEqual({"id", "prompt", "must", "must_not"}, set(case))

                case_id = case["id"]
                self.assertIs(type(case_id), str)
                self.assertTrue(case_id.strip())
                self.assertNotIn(case_id, ids)
                ids.add(case_id)

                prompt = case["prompt"]
                self.assertIs(type(prompt), str)
                self.assertTrue(prompt.strip())

                for field in ("must", "must_not"):
                    values = case[field]
                    self.assertIs(type(values), list)
                    self.assertTrue(values)
                    for value in values:
                        self.assertIs(type(value), str)
                        self.assertTrue(value.strip())
                self.assertTrue(set(case["must"]).isdisjoint(case["must_not"]))

        self.assertEqual(EXPECTED_IDS, ids)

    def test_every_phase_one_subject_appears_in_a_prompt(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        prompts = "\n".join(case["prompt"] for case in cases)
        for subject in ("语文", "数学", "英语", "政治", "历史", "地理"):
            with self.subTest(subject=subject):
                self.assertIn(subject, prompts)

    def test_each_subject_has_complete_evidence_loop_case(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        by_id = {case["id"]: case for case in cases}
        for subject, case_id in SUBJECT_LOOP_CASES.items():
            with self.subTest(subject=subject, case_id=case_id):
                case = by_id[case_id]
                self.assertIn(subject, case["prompt"])
                self.assertIn("学生表现链", case["prompt"])
                output_contract = "\n".join(case["must"])
                for marker in LOOP_OUTPUT_MARKERS:
                    self.assertIn(marker, output_contract)

    def test_single_error_case_preserves_existing_stable_state(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        case = next(
            case for case in cases if case["id"] == "single-error-needs-confirmation"
        )
        contract = "\n".join([case["prompt"], *case["must"]])
        self.assertIn("此前为 stable", contract)
        self.assertIn("保留已有 stable", contract)

    def test_direct_answer_case_requires_complete_explanation(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        direct = next(
            case for case in cases if case["id"] == "math-direct-explanation"
        )
        for outcome in (
            "方法选择理由",
            "完整推导",
            "易错点",
            "结果验证",
            "理解检查",
        ):
            with self.subTest(outcome=outcome):
                self.assertIn(outcome, direct["must"])
        self.assertIn("因为提供了解析而更新掌握状态", direct["must_not"])


if __name__ == "__main__":
    unittest.main()
