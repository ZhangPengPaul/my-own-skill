# 上海高中学习教练 Skill 第一阶段实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可安装、可验证的 `shanghai-high-school-study-coach` skill，完成公共学习闭环、本地学生档案管理，以及语文、数学、英语、政治、历史、地理六科适配。

**Architecture:** 使用单一 skill 作为稳定触发入口，`SKILL.md` 负责路由、教学协议和状态规则，六个学科参考文件按需加载。学生运行时数据位于被 Git 忽略的 `student-workspaces/`；三个 Python 标准库脚本只执行初始化、结构校验和事实汇总，不替代教学判断。

**Tech Stack:** Codex Skills、Markdown、YAML、Python 3.9 标准库、`unittest`、Git；官方 skill 初始化器和校验器位于 `/Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/`。

---

## 范围说明

本计划只实现设计规格的第一阶段。物理、化学、生物的文件名和数据契约保持稳定，
但不在本计划中创建学科参考或宣称完整支持；三科合格考适配在第一阶段验收通过后
另写实现计划。

设计依据：
`docs/superpowers/specs/2026-08-06-shanghai-high-school-study-coach-design.md`。

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `.gitignore` | 阻止真实学生工作区进入版本控制 |
| `skills/shanghai-high-school-study-coach/SKILL.md` | 触发、任务路由、学习闭环、状态与隐私规则 |
| `skills/shanghai-high-school-study-coach/agents/openai.yaml` | Codex UI 元数据和默认调用提示 |
| `skills/shanghai-high-school-study-coach/references/shanghai-curriculum-and-exams.md` | 官方来源、时效、冲突处理和考试目标边界 |
| `skills/shanghai-high-school-study-coach/references/{chinese,mathematics,english,politics,history,geography}.md` | 六科学科专属教学与证据规则 |
| `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py` | 校验本地学生状态和证据引用 |
| `skills/shanghai-high-school-study-coach/scripts/init_student.py` | 原子化初始化学生工作区 |
| `skills/shanghai-high-school-study-coach/scripts/summarize_progress.py` | 从记录事实生成 Markdown 进度摘要 |
| `skills/shanghai-high-school-study-coach/assets/student-workspace-template/*` | 可复制的无真实数据工作区模板 |
| `skills/shanghai-high-school-study-coach/assets/session-record-template.md` | 统一会话证据字段 |
| `skills/shanghai-high-school-study-coach/assets/mistake-record-template.md` | 统一错题、错因和复测字段 |
| `tests/test_repository_privacy.py` | Git 隐私边界回归测试 |
| `tests/test_validate_student_data.py` | 状态契约和证据校验测试 |
| `tests/test_init_student.py` | 初始化、幂等保护和目录结构测试 |
| `tests/test_summarize_progress.py` | 确定性汇总测试 |
| `tests/test_skill_contract.py` | Skill 结构、路由和公共协议静态测试 |
| `tests/test_reference_contracts.py` | 官方来源及六科学科参考契约测试 |
| `tests/behavioral/*` | 虚构材料、用户风格提示词和前向测试判据 |

### Task 1: 建立 Skill 骨架与仓库隐私边界

**Files:**
- Create: `.gitignore`
- Create: `tests/test_repository_privacy.py`
- Create: `skills/shanghai-high-school-study-coach/SKILL.md`
- Create: `skills/shanghai-high-school-study-coach/agents/openai.yaml`

- [ ] **Step 1: 写隐私边界失败测试**

```python
# tests/test_repository_privacy.py
from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPrivacyTest(unittest.TestCase):
    def test_student_workspaces_are_ignored(self):
        lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("/student-workspaces/", lines)

    def test_no_student_workspace_is_tracked(self):
        result = subprocess.run(
            ["git", "ls-files", "student-workspaces"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual("", result.stdout.strip())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python3 -m unittest tests.test_repository_privacy -v`

Expected: FAIL，错误包含 `FileNotFoundError: .../.gitignore`。

- [ ] **Step 3: 添加最小 Git 忽略规则**

```gitignore
/student-workspaces/
__pycache__/
*.py[cod]
```

- [ ] **Step 4: 重跑隐私测试**

Run: `python3 -m unittest tests.test_repository_privacy -v`

Expected: 2 tests PASS。

- [ ] **Step 5: 使用官方脚本初始化 Skill**

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/init_skill.py shanghai-high-school-study-coach --path skills --resources scripts,references,assets --interface 'display_name=上海高中学习教练' --interface 'short_description=为上海高中生提供个性化讲解、练习、批改、复盘与学习规划' --interface 'default_prompt=Use $shanghai-high-school-study-coach to analyze my current study needs and guide the next evidence-based step.'
```

Expected: 创建 skill、`SKILL.md`、`agents/openai.yaml` 和三个资源目录；命令输出
`initialized successfully`。不要使用 `--examples`，避免生成占位资源。

- [ ] **Step 6: 立即替换初始化器生成的占位 SKILL.md**

```markdown
---
name: shanghai-high-school-study-coach
description: 为上海高一至高三学生提供可跨会话持续的学习辅导、练习、作业或试卷批改、错因诊断、复盘、学习计划和进度分析。适用于语文、数学、英语、政治、历史、地理，以及后续合格考模式下的物理、化学、生物；当用户提到上海高中、高考或合格考、学生档案、错题、图片或 PDF 试卷、作文批改、分层提示、周计划或薄弱点跟踪时使用。
---

# 上海高中学习教练

## 第一阶段边界

支持公共学习闭环和语文、数学、英语、政治、历史、地理。物理、化学、生物
只保留数据接口，不声称已完成学科适配。

## 临时工作流

在完整工作流实现前，只执行不依赖持久状态的一次性答疑。不要创建学生档案，
不要修改掌握度，不要编造上海考试政策或评分标准。
```

- [ ] **Step 7: 校验骨架且确认无占位符**

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
```

Expected: `Skill is valid!`

Run: `rg -n 'TODO|TBD|placeholder' skills/shanghai-high-school-study-coach`

Expected: 无输出，退出码 1。

- [ ] **Step 8: 提交骨架**

```bash
git add .gitignore tests/test_repository_privacy.py skills/shanghai-high-school-study-coach/SKILL.md skills/shanghai-high-school-study-coach/agents/openai.yaml
git commit -m "feat: scaffold Shanghai study coach skill"
```

### Task 2: 定义并校验学生状态契约

**Files:**
- Create: `tests/test_validate_student_data.py`
- Create: `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py`

- [ ] **Step 1: 写状态契约失败测试**

```python
# tests/test_validate_student_data.py
from pathlib import Path
import copy
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills/shanghai-high-school-study-coach/scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from validate_student_data import ValidationError, validate_state  # noqa: E402


SUBJECTS = {
    "chinese": "high-stakes",
    "mathematics": "high-stakes",
    "english": "high-stakes",
    "politics": "high-stakes",
    "history": "high-stakes",
    "geography": "high-stakes",
    "physics": "qualification",
    "chemistry": "qualification",
    "biology": "qualification",
}


def valid_state():
    subjects = {}
    for name, goal_type in SUBJECTS.items():
        subject = {
            "goal_type": goal_type,
            "assessments": [],
            "knowledge_units": {},
        }
        if goal_type == "qualification":
            subject["qualification_risk"] = "unassessed"
        subjects[name] = subject
    return {
        "schema_version": 1,
        "student_id": "student-a",
        "updated_at": None,
        "subjects": subjects,
        "process": {"completed_plan_items": 0, "recorded_sessions": 0},
    }


class ValidateStateTest(unittest.TestCase):
    def test_accepts_initial_state(self):
        validate_state(valid_state())

    def test_rejects_unknown_schema_version(self):
        state = valid_state()
        state["schema_version"] = 2
        with self.assertRaisesRegex(ValidationError, "schema_version"):
            validate_state(state)

    def test_rejects_missing_subject(self):
        state = valid_state()
        del state["subjects"]["geography"]
        with self.assertRaisesRegex(ValidationError, "subjects"):
            validate_state(state)

    def test_requires_evidence_for_mastery(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "stable",
            "evidence": [],
            "last_reviewed_at": None,
            "next_review_at": None,
        }
        with self.assertRaisesRegex(ValidationError, "evidence"):
            validate_state(state)

    def test_accepts_existing_session_evidence(self):
        state = valid_state()
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
            "status": "developing",
            "evidence": ["sessions/2026-08-06-mathematics-s1.md"],
            "last_reviewed_at": "2026-08-06",
            "next_review_at": "2026-08-13",
        }
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "sessions").mkdir()
            (workspace / "sessions/2026-08-06-mathematics-s1.md").write_text(
                "fictional evidence", encoding="utf-8"
            )
            validate_state(state, workspace)

    def test_rejects_nonexistent_evidence_path(self):
        state = valid_state()
        unit = {
            "status": "developing",
            "evidence": ["sessions/missing.md"],
            "last_reviewed_at": None,
            "next_review_at": None,
        }
        state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = unit
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValidationError, "missing"):
                validate_state(state, Path(tmp))

    def test_rejects_qualification_risk_on_high_stakes_subject(self):
        state = copy.deepcopy(valid_state())
        state["subjects"]["english"]["qualification_risk"] = "low"
        with self.assertRaisesRegex(ValidationError, "qualification_risk"):
            validate_state(state)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认导入失败**

Run: `python3 -m unittest tests.test_validate_student_data -v`

Expected: FAIL，错误包含 `No module named 'validate_student_data'`。

- [ ] **Step 3: 实现最小状态校验器**

```python
#!/usr/bin/env python3
"""Validate a Shanghai study coach student workspace."""

import argparse
import json
from pathlib import Path
import re
import sys


EXPECTED_SUBJECTS = {
    "chinese": "high-stakes",
    "mathematics": "high-stakes",
    "english": "high-stakes",
    "politics": "high-stakes",
    "history": "high-stakes",
    "geography": "high-stakes",
    "physics": "qualification",
    "chemistry": "qualification",
    "biology": "qualification",
}
MASTERY_LEVELS = {
    "unassessed",
    "emerging",
    "developing",
    "stable",
    "transferable",
}
QUALIFICATION_RISKS = {"unassessed", "low", "medium", "high"}
STUDENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class ValidationError(ValueError):
    """Raised when persisted student data violates the contract."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def validate_state(state, workspace=None):
    require(isinstance(state, dict), "state must be a JSON object")
    require(state.get("schema_version") == 1, "schema_version must be 1")
    student_id = state.get("student_id")
    require(isinstance(student_id, str) and STUDENT_ID.fullmatch(student_id),
            "student_id must use lowercase letters, digits, and hyphens")
    require(state.get("updated_at") is None or isinstance(state.get("updated_at"), str),
            "updated_at must be null or a string")

    subjects = state.get("subjects")
    require(isinstance(subjects, dict), "subjects must be an object")
    require(set(subjects) == set(EXPECTED_SUBJECTS),
            "subjects must contain exactly the nine configured subjects")

    for subject_name, expected_goal in EXPECTED_SUBJECTS.items():
        subject = subjects[subject_name]
        prefix = "subjects.%s" % subject_name
        require(isinstance(subject, dict), "%s must be an object" % prefix)
        require(subject.get("goal_type") == expected_goal,
                "%s.goal_type must be %s" % (prefix, expected_goal))
        require(isinstance(subject.get("assessments"), list),
                "%s.assessments must be a list" % prefix)
        units = subject.get("knowledge_units")
        require(isinstance(units, dict), "%s.knowledge_units must be an object" % prefix)

        if expected_goal == "qualification":
            require(subject.get("qualification_risk") in QUALIFICATION_RISKS,
                    "%s.qualification_risk is invalid" % prefix)
        else:
            require("qualification_risk" not in subject,
                    "%s must not contain qualification_risk" % prefix)

        for unit_name, unit in units.items():
            unit_prefix = "%s.knowledge_units.%s" % (prefix, unit_name)
            require(isinstance(unit, dict), "%s must be an object" % unit_prefix)
            status = unit.get("status")
            evidence = unit.get("evidence")
            require(status in MASTERY_LEVELS, "%s.status is invalid" % unit_prefix)
            require(isinstance(evidence, list) and all(isinstance(item, str) for item in evidence),
                    "%s.evidence must be a list of paths" % unit_prefix)
            if status != "unassessed":
                require(bool(evidence), "%s.evidence is required" % unit_prefix)
            for field in ("last_reviewed_at", "next_review_at"):
                require(unit.get(field) is None or isinstance(unit.get(field), str),
                        "%s.%s must be null or a string" % (unit_prefix, field))
            if workspace is not None:
                for relative in evidence:
                    require(relative.startswith("sessions/"),
                            "%s evidence must reference sessions/" % unit_prefix)
                    require((Path(workspace) / relative).is_file(),
                            "%s evidence path is missing: %s" % (unit_prefix, relative))

    process = state.get("process")
    require(isinstance(process, dict), "process must be an object")
    for field in ("completed_plan_items", "recorded_sessions"):
        value = process.get(field)
        require(isinstance(value, int) and not isinstance(value, bool) and value >= 0,
                "process.%s must be a non-negative integer" % field)


def validate_workspace(workspace):
    workspace = Path(workspace)
    for relative in ("profile.md", "state.json", "plans/current.md"):
        require((workspace / relative).is_file(), "missing required file: %s" % relative)
    for relative in ("mistakes", "sessions", "materials"):
        require((workspace / relative).is_dir(), "missing required directory: %s" % relative)
    try:
        state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValidationError("cannot read state.json: %s" % exc)
    validate_state(state, workspace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        validate_workspace(args.workspace)
    except ValidationError as exc:
        print("INVALID: %s" % exc, file=sys.stderr)
        return 1
    print("VALID: %s" % args.workspace)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行状态校验测试**

Run: `python3 -m unittest tests.test_validate_student_data -v`

Expected: 7 tests PASS。

- [ ] **Step 5: 提交状态契约**

```bash
git add tests/test_validate_student_data.py skills/shanghai-high-school-study-coach/scripts/validate_student_data.py
git commit -m "feat: validate student learning state"
```

### Task 3: 创建工作区模板与原子初始化器

**Files:**
- Create: `skills/shanghai-high-school-study-coach/assets/student-workspace-template/profile.md`
- Create: `skills/shanghai-high-school-study-coach/assets/student-workspace-template/state.json`
- Create: `skills/shanghai-high-school-study-coach/assets/student-workspace-template/plans/current.md`
- Create: `skills/shanghai-high-school-study-coach/assets/session-record-template.md`
- Create: `skills/shanghai-high-school-study-coach/assets/mistake-record-template.md`
- Create: `tests/test_init_student.py`
- Create: `skills/shanghai-high-school-study-coach/scripts/init_student.py`

- [ ] **Step 1: 创建无真实信息的模板**

```markdown
<!-- profile.md -->
# 学生档案

- student_id: __STUDENT_ID__
- grade:
- term:
- textbooks_or_materials:
- selected_subjects:
- target_exams:
- target_dates:
- learning_preferences:
- learning_goals:

只填写学习所需信息，不记录姓名、学校、班级、住址或联系方式。
```

```json
{
  "schema_version": 1,
  "student_id": "__STUDENT_ID__",
  "updated_at": null,
  "subjects": {
    "chinese": {"goal_type": "high-stakes", "assessments": [], "knowledge_units": {}},
    "mathematics": {"goal_type": "high-stakes", "assessments": [], "knowledge_units": {}},
    "english": {"goal_type": "high-stakes", "assessments": [], "knowledge_units": {}},
    "politics": {"goal_type": "high-stakes", "assessments": [], "knowledge_units": {}},
    "history": {"goal_type": "high-stakes", "assessments": [], "knowledge_units": {}},
    "geography": {"goal_type": "high-stakes", "assessments": [], "knowledge_units": {}},
    "physics": {"goal_type": "qualification", "assessments": [], "knowledge_units": {}, "qualification_risk": "unassessed"},
    "chemistry": {"goal_type": "qualification", "assessments": [], "knowledge_units": {}, "qualification_risk": "unassessed"},
    "biology": {"goal_type": "qualification", "assessments": [], "knowledge_units": {}, "qualification_risk": "unassessed"}
  },
  "process": {"completed_plan_items": 0, "recorded_sessions": 0}
}
```

```markdown
<!-- plans/current.md -->
# 当前周计划

## 目标

## 计划项目

每个项目记录学科、任务、预计投入、完成状态和用于确认完成的证据。
```

同时创建两个不会复制真实信息的记录模板：

```markdown
<!-- assets/session-record-template.md -->
# 学习会话记录

- session_id:
- date:
- subject:
- task_mode:
- source_materials:
- source_uncertainty:
- student_attempt:
- hints_given:
- observations:
- conclusion:
- state_changes:
- remaining_uncertainty:

只有学生实际表现可以作为提高掌握度的证据。
```

```markdown
<!-- assets/mistake-record-template.md -->
# 错题记录

- mistake_id:
- subject:
- original_source:
- knowledge_unit:
- error_type:
- student_attempt:
- correction:
- hints_required:
- follow_up_task:
- verification_result:
- status: unresolved
```

- [ ] **Step 2: 写初始化器失败测试**

```python
# tests/test_init_student.py
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/shanghai-high-school-study-coach/scripts/init_student.py"


class InitStudentTest(unittest.TestCase):
    def run_init(self, root, student_id):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root), student_id],
            capture_output=True,
            text=True,
        )

    def test_creates_valid_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "student-a")
            self.assertEqual(0, result.returncode, result.stderr)
            workspace = root / "student-a"
            for relative in (
                "profile.md", "state.json", "plans/current.md",
                "mistakes", "sessions", "materials",
            ):
                self.assertTrue((workspace / relative).exists(), relative)
            state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
            self.assertEqual("student-a", state["student_id"])
            self.assertNotIn("__STUDENT_ID__", (workspace / "profile.md").read_text(encoding="utf-8"))

    def test_refuses_to_overwrite_existing_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(0, self.run_init(root, "student-a").returncode)
            marker = root / "student-a" / "marker.txt"
            marker.write_text("preserve", encoding="utf-8")
            result = self.run_init(root, "student-a")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual("preserve", marker.read_text(encoding="utf-8"))

    def test_invalid_id_leaves_no_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_init(root, "Student Name")
            self.assertNotEqual(0, result.returncode)
            self.assertEqual([], list(root.iterdir()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试并确认失败**

Run: `python3 -m unittest tests.test_init_student -v`

Expected: 3 tests FAIL，因为 `init_student.py` 不存在。

- [ ] **Step 4: 实现原子初始化器**

```python
#!/usr/bin/env python3
"""Initialize a private local student workspace without overwriting data."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from validate_student_data import STUDENT_ID, ValidationError, validate_workspace


TEMPLATE = Path(__file__).resolve().parents[1] / "assets/student-workspace-template"


def initialize(root, student_id):
    if not STUDENT_ID.fullmatch(student_id):
        raise ValidationError("invalid student_id")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    destination = root / student_id
    if destination.exists():
        raise ValidationError("workspace already exists: %s" % destination)

    temporary = Path(tempfile.mkdtemp(prefix=".%s-" % student_id, dir=str(root)))
    try:
        (temporary / "plans").mkdir()
        for directory in ("mistakes", "sessions", "materials"):
            (temporary / directory).mkdir()
        profile = (TEMPLATE / "profile.md").read_text(encoding="utf-8")
        (temporary / "profile.md").write_text(
            profile.replace("__STUDENT_ID__", student_id), encoding="utf-8"
        )
        state = json.loads((TEMPLATE / "state.json").read_text(encoding="utf-8"))
        state["student_id"] = student_id
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        (temporary / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy2(TEMPLATE / "plans/current.md", temporary / "plans/current.md")
        validate_workspace(temporary)
        os.replace(str(temporary), str(destination))
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("student_id")
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        destination = initialize(args.root, args.student_id)
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    print(destination)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 运行初始化器与校验器测试**

Run: `python3 -m unittest tests.test_init_student tests.test_validate_student_data -v`

Expected: 10 tests PASS。

- [ ] **Step 6: 提交模板与初始化器**

```bash
git add tests/test_init_student.py skills/shanghai-high-school-study-coach/assets skills/shanghai-high-school-study-coach/scripts/init_student.py
git commit -m "feat: initialize private student workspaces"
```

### Task 4: 从事实记录生成确定性进度摘要

**Files:**
- Create: `tests/test_summarize_progress.py`
- Create: `skills/shanghai-high-school-study-coach/scripts/summarize_progress.py`

- [ ] **Step 1: 写汇总器失败测试**

```python
# tests/test_summarize_progress.py
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INIT = ROOT / "skills/shanghai-high-school-study-coach/scripts/init_student.py"
SUMMARY = ROOT / "skills/shanghai-high-school-study-coach/scripts/summarize_progress.py"


class SummarizeProgressTest(unittest.TestCase):
    def test_reports_recorded_facts_and_mastery_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(
                [sys.executable, str(INIT), "--root", str(root), "student-a"],
                check=True,
            )
            workspace = root / "student-a"
            session = workspace / "sessions/2026-08-06-mathematics-s1.md"
            session.write_text("fictional independent answer", encoding="utf-8")
            state_path = workspace / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["subjects"]["mathematics"]["knowledge_units"]["quadratic"] = {
                "status": "developing",
                "evidence": ["sessions/2026-08-06-mathematics-s1.md"],
                "last_reviewed_at": "2026-08-06",
                "next_review_at": "2026-08-13",
            }
            state["process"] = {"completed_plan_items": 2, "recorded_sessions": 1}
            state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SUMMARY), str(workspace)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertIn("student-a", result.stdout)
            self.assertIn("mathematics: developing=1", result.stdout)
            self.assertIn("已完成计划项目: 2", result.stdout)
            self.assertIn("记录会话: 1", result.stdout)
            self.assertNotIn("预计分数", result.stdout)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python3 -m unittest tests.test_summarize_progress -v`

Expected: FAIL，因为 `summarize_progress.py` 不存在。

- [ ] **Step 3: 实现进度摘要器**

```python
#!/usr/bin/env python3
"""Render recorded student progress as deterministic Markdown."""

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from validate_student_data import ValidationError, validate_workspace


def render(workspace):
    workspace = Path(workspace)
    validate_workspace(workspace)
    state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
    lines = [
        "# 学习进度摘要",
        "",
        "- student_id: %s" % state["student_id"],
        "- updated_at: %s" % (state["updated_at"] or "未记录"),
        "- 已完成计划项目: %d" % state["process"]["completed_plan_items"],
        "- 记录会话: %d" % state["process"]["recorded_sessions"],
        "",
        "## 学科状态",
        "",
    ]
    for subject_name, subject in state["subjects"].items():
        counts = Counter(
            unit["status"] for unit in subject["knowledge_units"].values()
        )
        facts = ", ".join(
            "%s=%d" % (level, counts[level]) for level in sorted(counts)
        ) or "unassessed=0"
        suffix = ""
        if subject["goal_type"] == "qualification":
            suffix = ", qualification_risk=%s" % subject["qualification_risk"]
        lines.append("- %s: %s%s" % (subject_name, facts, suffix))
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    try:
        print(render(args.workspace), end="")
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 运行汇总器测试**

Run: `python3 -m unittest tests.test_summarize_progress -v`

Expected: 1 test PASS。

- [ ] **Step 5: 提交汇总器**

```bash
git add tests/test_summarize_progress.py skills/shanghai-high-school-study-coach/scripts/summarize_progress.py
git commit -m "feat: summarize recorded study progress"
```

### Task 5: 实现公共 Skill 工作流

**Files:**
- Create: `tests/test_skill_contract.py`
- Modify: `skills/shanghai-high-school-study-coach/SKILL.md`
- Modify: `skills/shanghai-high-school-study-coach/agents/openai.yaml`

- [ ] **Step 1: 写公共协议失败测试**

```python
# tests/test_skill_contract.py
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
```

- [ ] **Step 2: 运行测试并确认公共协议不完整**

Run: `python3 -m unittest tests.test_skill_contract -v`

Expected: 至少 `test_has_all_task_modes_and_learning_steps`、
`test_requires_evidence_and_uncertainty_handling` 和
`test_maps_phase_one_subject_references` FAIL。

- [ ] **Step 3: 将 SKILL.md 扩展为完整公共工作流**

写入以下内容；保持正文低于 500 行：

```markdown
---
name: shanghai-high-school-study-coach
description: 为上海高一至高三学生提供可跨会话持续的学习辅导、练习、作业或试卷批改、错因诊断、复盘、学习计划和进度分析。适用于语文、数学、英语、政治、历史、地理，以及后续合格考模式下的物理、化学、生物；当用户提到上海高中、高考或合格考、学生档案、错题、图片或 PDF 试卷、作文批改、分层提示、周计划或薄弱点跟踪时使用。
---

# 上海高中学习教练

## 边界

第一阶段支持语文、数学、英语、政治、历史、地理。物理、化学、生物只保留
状态接口；在对应参考文件不存在时，明确说明尚未完成合格考适配，并提供不写入
长期状态的一般性帮助。

不要保证分数、排名、录取或合格结果。不要替代教师要求和适用的官方文件。

## 定位学生工作区

1. 从用户提供路径或当前仓库的 `student-workspaces/<student-id>/` 定位工作区。
2. 未指定学生时，只在写入长期状态确有必要时询问学生 ID。
3. 工作区不存在时，可先完成一次性答疑，再询问是否运行
   `scripts/init_student.py --root <private-root> <student-id>`。
4. 写入前运行 `scripts/validate_student_data.py <workspace>`。
5. 只读取当前学生、当前学科和当前任务所需文件。

## 识别任务模式

- `assessment`：诊断水平或成绩表现的原因。
- `explanation`：讲解知识或方法。
- `practice`：提供并完成针对性练习。
- `grading`：依据明确答案或评分标准批改。
- `review`：复盘题目、作业或试卷。
- `planning`：创建或调整多学科计划。

允许同一会话切换模式，但在会话记录中写明切换及其依据。

## 加载参考

涉及考试政策、评分口径或来源冲突时，读取
`references/shanghai-curriculum-and-exams.md`。

仅按当前学科读取一个参考文件：

| 学科 | 参考文件 |
| --- | --- |
| 语文 | `references/chinese.md` |
| 数学 | `references/mathematics.md` |
| 英语 | `references/english.md` |
| 政治 | `references/politics.md` |
| 历史 | `references/history.md` |
| 地理 | `references/geography.md` |

## 执行学习闭环

1. 确认学生、学科、任务模式、可用时间和当前目标。
2. 读取最少量的 `profile.md`、`state.json`、`plans/current.md` 和近期证据。
3. 解析文字、图片或 PDF。题干、公式、图形或答题痕迹不清且可能影响答案时，
   展示不确定部分并要求用户确认，不继续评分。
4. 先诊断学生思路，再决定讲解和提示深度。
5. 练习模式先查看学生尝试，然后按“定位卡点 -> 回忆原则 -> 建议下一步 ->
   完整示例”逐层提示。
6. 学生完成尝试、明确要求完整解析或进入复盘模式后，才给完整答案。
7. 将错因归类为知识、方法、审题、计算、记忆、表达或无依据推断等可行动类别。
8. 以一个规模适当的后续任务结束。
9. 记录会话；只有存在学生表现证据时才更新掌握度、错题和计划。

创建会话记录时使用 `assets/session-record-template.md`，创建或更新错题记录时使用
`assets/mistake-record-template.md`。保留材料来源、提示程度、学生实际回答、状态变化
和剩余不确定性，不把 Codex 自己生成的答案记录成学生表现。

## 更新状态

掌握度只使用 `unassessed`、`emerging`、`developing`、`stable`、
`transferable`。Codex 已讲解过不属于学生表现证据；没有独立作答、订正、延迟
回忆或变式迁移证据时，不得提高掌握度。

每次非初始掌握度都要引用 `sessions/` 中的证据并记录提示程度。新证据与旧判断
冲突时允许降低掌握度。更新 `state.json` 后再次运行校验器。

## 处理来源

采用以下对齐优先级：学生当前教材、教师讲义和明确要求；适用的上海官方课程与
考试文件；通用学科知识。高优先级材料疑似错误、过期或不适用时，明确展示冲突，
不能静默采用或编造政策、评分标准、分数换算、题目出处和学生成绩。

## 隐私与失败

只使用学生代号或不透明 ID，不要求姓名、学校、班级、住址和联系方式。未经明确
授权，不向外部服务发送材料，也不提交 `student-workspaces/`。

材料不可读时停止评分和状态更新。状态无效时保留原文件并报告校验错误。会话中断
可以留下未完成记录，但不能据此提高掌握度。缺少权威答案或评分标准时，将确定的
反馈与不确定评分分开表达。
```

- [ ] **Step 4: 重新生成并核对 openai.yaml**

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py skills/shanghai-high-school-study-coach --interface 'display_name=上海高中学习教练' --interface 'short_description=为上海高中生提供个性化讲解、练习、批改、复盘与学习规划' --interface 'default_prompt=Use $shanghai-high-school-study-coach to analyze my current study needs and guide the next evidence-based step.'
```

Expected: 输出 `[OK] Created agents/openai.yaml`，且文件只包含明确提供的四个
interface 字段。

- [ ] **Step 5: 运行公共协议和官方结构校验**

Run: `python3 -m unittest tests.test_skill_contract -v`

Expected: 6 tests PASS。

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
```

Expected: `Skill is valid!`

- [ ] **Step 6: 提交公共工作流**

```bash
git add tests/test_skill_contract.py skills/shanghai-high-school-study-coach/SKILL.md skills/shanghai-high-school-study-coach/agents/openai.yaml
git commit -m "feat: define adaptive study coach workflow"
```

### Task 6: 建立上海官方来源与考试边界参考

**Files:**
- Create: `tests/test_reference_contracts.py`
- Create: `skills/shanghai-high-school-study-coach/references/shanghai-curriculum-and-exams.md`

- [ ] **Step 1: 写来源契约失败测试**

```python
# tests/test_reference_contracts.py
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
REFERENCES = ROOT / "skills/shanghai-high-school-study-coach/references"


class ReferenceContractTest(unittest.TestCase):
    def test_source_governance_is_explicit(self):
        content = (REFERENCES / "shanghai-curriculum-and-exams.md").read_text(encoding="utf-8")
        for phrase in (
            "上海市教育委员会", "https://edu.sh.gov.cn/",
            "上海市教育考试院", "https://www.shmeea.edu.cn/",
            "发布日期", "获取日期", "适用范围", "来源冲突",
        ):
            self.assertIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认文件缺失**

Run: `python3 -m unittest tests.test_reference_contracts -v`

Expected: FAIL，错误指出 `shanghai-curriculum-and-exams.md` 不存在。

- [ ] **Step 3: 从官方站点核实现行文件**

只使用以下官方入口，并记录检索日期：

- 上海市教育委员会：`https://edu.sh.gov.cn/`
- 上海市教育考试院：`https://www.shmeea.edu.cn/`

依次检索“上海市普通高中课程实施方案”“普通高中学业水平考试实施办法”以及
第一阶段六科当年适用的考试或评价文件。打开原始官方页面或官方附件，逐条记录
发布机构、完整标题、发布日期或更新日期、获取日期、URL 或文档标识和适用范围。

如果官方站点不可访问，停止该任务并报告阻塞；不得用培训机构、自媒体或搜索摘要
代替权威来源，也不得猜测考试科目、分值或评分口径。

- [ ] **Step 4: 写来源治理参考**

文件必须包含以下固定内容，并在“已核实来源”表中加入 Step 3 实际打开并核验的
官方文档；每一行六个字段都必须为真实值，不允许空值：

```markdown
# 上海课程与考试来源治理

## 官方入口

- 上海市教育委员会：https://edu.sh.gov.cn/
- 上海市教育考试院：https://www.shmeea.edu.cn/

## 已核实来源

使用六列记录：发布机构、完整标题、发布日期或更新日期、获取日期、URL 或文档
标识、适用范围。只有打开并核实过的官方原文可以进入该表。

## 使用顺序

1. 先对齐学生当前教材、教师讲义和教师明确要求。
2. 涉及课程边界、考试政策或评分口径时，核对适用的官方文件。
3. 通用学科知识只能补充前两类来源，不能伪装成上海本地规则。

## 时效检查

每次引用考试政策时比较目标考试年份、文件适用年份和获取日期。无法确认文件仍然
适用时，明确标记不确定性并询问用户提供当前学校或考试文件，不输出精确政策结论。

## 来源冲突

记录双方陈述、来源、日期和适用范围。课堂对齐可以暂时采用教师要求，但疑似事实
错误、过期或不适用时必须指出，不静默覆盖。不得编造分值、题型、等级换算、评分
细则、题目出处或政策发布日期。

## 两类目标

- 高考计分学科关注真实成绩、掌握度、迁移和学习过程。
- 合格考学科关注官方范围覆盖、基础题稳定性和带证据的未达标风险。

学生个人正式选科和目标考试必须来自 `profile.md` 或用户确认，不能从默认九科列表
自动推断。
```

- [ ] **Step 5: 运行来源契约测试**

Run: `python3 -m unittest tests.test_reference_contracts -v`

Expected: 1 test PASS。人工检查“已核实来源”至少覆盖课程实施、学业水平考试边界，
并且所有精确政策陈述都有对应行。

- [ ] **Step 6: 提交来源治理**

```bash
git add tests/test_reference_contracts.py skills/shanghai-high-school-study-coach/references/shanghai-curriculum-and-exams.md
git commit -m "docs: add Shanghai curriculum source governance"
```

### Task 7: 实现语文、数学、英语学科参考

**Files:**
- Modify: `tests/test_reference_contracts.py`
- Create: `skills/shanghai-high-school-study-coach/references/chinese.md`
- Create: `skills/shanghai-high-school-study-coach/references/mathematics.md`
- Create: `skills/shanghai-high-school-study-coach/references/english.md`

- [ ] **Step 1: 扩展失败测试**

在 `ReferenceContractTest` 中加入：

```python
    def test_language_and_mathematics_references_have_operational_sections(self):
        expected = {
            "chinese.md": ("文本证据", "作文", "开放题", "迁移验证"),
            "mathematics.md": ("第一个实质错误", "条件检查", "推导", "变式"),
            "english.md": ("保留学生原意", "任务完成", "语言准确", "针对性练习"),
        }
        for filename, phrases in expected.items():
            content = (REFERENCES / filename).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, content, "%s missing %s" % (filename, phrase))
```

- [ ] **Step 2: 运行测试并确认三个文件缺失**

Run: `python3 -m unittest tests.test_reference_contracts -v`

Expected: 新增测试 FAIL，首先报告 `chinese.md` 不存在。

- [ ] **Step 3: 创建语文参考**

```markdown
# 语文学习与反馈

## 诊断

先区分知识与积累、文本理解、证据选择、答题组织、语言表达和审题问题。阅读题要求
学生指出文本证据，并解释证据如何支持结论。缺少原文、题干或评分依据时，不给精确
分数。

## 阅读与材料题

先复述任务边界，再检查答案是否包含观点、文本证据和推理。开放题可以接受多个有
依据的解释；指出“可辩护”和“缺少依据”的差别，不把示例答案说成唯一答案。

## 作文

按任务完成、立意、结构、材料或证据、语言、修改六个维度反馈。先评价学生原稿，
再提供局部修改和原因；不代写与学生水平明显不符的整篇文章。涉及精确分数时必须
有适用评分标准。

## 练习与状态证据

提示顺序为定位原句、提示关系、要求重组答案、最后给参考表达。只有学生独立完成
订正、延迟复述或在新文本中复用方法，才能提高掌握度。迁移验证必须更换文本或问题
条件，不能重复原答案。
```

- [ ] **Step 4: 创建数学参考**

```markdown
# 数学学习与反馈

## 诊断

保留学生步骤，依次检查题意、已知条件、目标、方法选择、推导、计算、符号和结果
条件。指出第一个实质错误及其后续影响，不只比较最终答案。

## 讲解与提示

先询问学生已经尝试的路径。按“确认目标、回忆相关定义或定理、提示关键中间量、
给下一步”逐层提示。完整解答必须包含必要条件检查和结论验证。

## 批改

区分方法正确但计算错误、条件遗漏、等价变形失效、论证跳步和表达不规范。没有
标准答案时可以验证推理，但不得虚构评分点或分数。

## 练习与状态证据

针对首个错因生成一个最小练习，再使用改变数字、条件或表示方式的变式检查迁移。
学生在有限提示下完成订正可记为 developing；独立完成延迟复测可支持 stable；
独立完成变式并解释方法才支持 transferable。
```

- [ ] **Step 5: 创建英语参考**

```markdown
# 英语学习与反馈

## 诊断

先判断任务属于词汇语法、阅读、以文字材料呈现的听说、翻译或写作，再区分理解、
任务完成、语言准确、衔接和表达范围问题。

## 阅读与翻译

要求答案引用原文线索并解释推断。翻译先检查意义、逻辑和关键信息，再处理语法与
自然度；不要用完全重写掩盖学生原有问题。

## 写作

按任务完成、内容组织、语言准确、衔接和表达效果反馈。保留学生原意，先展示必要
修改和原因，再给学生能够理解并复用的表达。除非用户明确进入复盘模式，不直接
输出超出学生水平的整篇替代稿。

## 练习与状态证据

根据错误模式生成针对性练习，例如时态、从句、搭配、段落衔接或阅读推断。学生
必须在新句子、新段落或新文本中独立使用目标能力，才允许提高掌握度。
```

- [ ] **Step 6: 运行学科参考测试**

Run: `python3 -m unittest tests.test_reference_contracts -v`

Expected: 2 tests PASS。

- [ ] **Step 7: 提交三科参考**

```bash
git add tests/test_reference_contracts.py skills/shanghai-high-school-study-coach/references/chinese.md skills/shanghai-high-school-study-coach/references/mathematics.md skills/shanghai-high-school-study-coach/references/english.md
git commit -m "docs: add Chinese mathematics and English coaching rules"
```

### Task 8: 实现政治、历史、地理学科参考

**Files:**
- Modify: `tests/test_reference_contracts.py`
- Create: `skills/shanghai-high-school-study-coach/references/politics.md`
- Create: `skills/shanghai-high-school-study-coach/references/history.md`
- Create: `skills/shanghai-high-school-study-coach/references/geography.md`

- [ ] **Step 1: 扩展失败测试**

在 `ReferenceContractTest` 中加入：

```python
    def test_humanities_references_have_operational_sections(self):
        expected = {
            "politics.md": ("政策日期", "材料依据", "概念", "分点"),
            "history.md": ("时间", "因果", "史料", "证据"),
            "geography.md": ("空间", "图表", "尺度", "因果链"),
        }
        for filename, phrases in expected.items():
            content = (REFERENCES / filename).read_text(encoding="utf-8")
            for phrase in phrases:
                self.assertIn(phrase, content, "%s missing %s" % (filename, phrase))
```

- [ ] **Step 2: 运行测试并确认三个文件缺失**

Run: `python3 -m unittest tests.test_reference_contracts -v`

Expected: 新增测试 FAIL，首先报告 `politics.md` 不存在。

- [ ] **Step 3: 创建政治参考**

```markdown
# 政治学习与反馈

## 诊断

区分概念不清、材料信息遗漏、知识与材料脱节、主体或条件错误、分点重复和语言不
规范。先要求学生标出材料依据，再选择对应概念。

## 时效与来源

涉及现实制度、政策或时事时记录政策日期和来源。无法核实当前适用性时明确说明，
不得用模型记忆编造上海本地考试政策或现实政策结论。

## 答题组织

每一点包含概念、材料依据和二者之间的解释。检查题目要求的主体、范围、原因、
影响或措施，避免只堆砌术语。参考答案是评分依据时才讨论精确得分。

## 练习与状态证据

先修正一个概念或连接错误，再用新材料验证。学生能够独立选择概念、引用材料并
分点解释，才支持提高掌握度。
```

- [ ] **Step 4: 创建历史参考**

```markdown
# 历史学习与反馈

## 诊断

区分时间与空间定位、史实、史料读取、比较、因果、变化与延续、评价和表达问题。
先建立必要时间框架，再处理解释。

## 史料题

区分史料直接信息、基于背景的推断和无法由证据支持的结论。答案必须指出史料证据，
并解释证据与结论的关系；不得把后见之明当作当时人的动机。

## 因果与评价

区分背景、直接原因、条件、过程和影响，避免单因解释。评价历史现象时说明尺度、
立场、时期和证据。

## 练习与状态证据

使用不同时期或不同史料的比较题验证方法迁移。学生能够独立建立时间关系、选择
证据并形成因果解释，才支持提高掌握度。
```

- [ ] **Step 5: 创建地理参考**

```markdown
# 地理学习与反馈

## 诊断

区分位置与空间、尺度、地图读取、图表数据、过程机制、区域差异、人地关系和表达
问题。先确认图例、单位、方向、时间范围和空间尺度。

## 图表与材料

先描述可观察模式，再解释原因；不得把推断写成图表直接事实。答案需要引用数值、
空间分布或材料信息，并说明其作用。

## 过程与因果

使用“条件 -> 过程 -> 结果 -> 反馈或限制”的因果链，检查自然和人文因素是否与
题目尺度一致。措施题要对应具体问题、主体和约束。

## 练习与状态证据

更换区域、尺度或图表形式验证迁移。学生能够独立读图、引用证据并完成因果链，
才支持提高掌握度。
```

- [ ] **Step 6: 运行全部参考契约测试**

Run: `python3 -m unittest tests.test_reference_contracts -v`

Expected: 3 tests PASS。

- [ ] **Step 7: 提交三科参考**

```bash
git add tests/test_reference_contracts.py skills/shanghai-high-school-study-coach/references/politics.md skills/shanghai-high-school-study-coach/references/history.md skills/shanghai-high-school-study-coach/references/geography.md
git commit -m "docs: add politics history and geography coaching rules"
```

### Task 9: 建立图片、PDF 与行为回归材料

**Files:**
- Create: `tests/behavioral/generate_fixtures.py`
- Create: `tests/behavioral/cases.json`
- Create: `tests/test_behavioral_fixtures.py`
- Generate: `tests/behavioral/fixtures/math-exam.pdf`
- Generate: `tests/behavioral/fixtures/english-essay.svg`
- Create: `tests/behavioral/fixtures/humanities-materials.md`

- [ ] **Step 1: 写行为材料失败测试**

```python
# tests/test_behavioral_fixtures.py
from pathlib import Path
import json
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
BEHAVIORAL = ROOT / "tests/behavioral"


class BehavioralFixtureTest(unittest.TestCase):
    def test_generator_creates_pdf_and_image(self):
        subprocess.run([sys.executable, str(BEHAVIORAL / "generate_fixtures.py")], check=True)
        pdf = (BEHAVIORAL / "fixtures/math-exam.pdf").read_bytes()
        svg = (BEHAVIORAL / "fixtures/english-essay.svg").read_text(encoding="utf-8")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertIn("<svg", svg)
        self.assertIn("My weekend volunteer work", svg)

    def test_case_catalog_has_required_phase_one_coverage(self):
        cases = json.loads((BEHAVIORAL / "cases.json").read_text(encoding="utf-8"))
        ids = {case["id"] for case in cases}
        self.assertEqual(
            {"onboarding-plan", "math-review", "english-writing", "humanities-evidence",
             "unreadable-input", "source-conflict", "no-evidence-no-mastery"},
            ids,
        )
        for case in cases:
            self.assertTrue(case["prompt"])
            self.assertTrue(case["must"])
            self.assertTrue(case["must_not"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试并确认生成器缺失**

Run: `python3 -m unittest tests.test_behavioral_fixtures -v`

Expected: FAIL，错误指出 `generate_fixtures.py` 不存在。

- [ ] **Step 3: 实现无第三方依赖的测试材料生成器**

```python
#!/usr/bin/env python3
"""Generate deterministic fictional PDF and image fixtures."""

from pathlib import Path


HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"


def escape_pdf(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_pdf(path, lines):
    stream_lines = ["BT", "/F1 12 Tf", "72 760 Td"]
    for index, line in enumerate(lines):
        if index:
            stream_lines.append("0 -22 Td")
        stream_lines.append("(%s) Tj" % escape_pdf(line))
    stream_lines.append("ET")
    stream = ("\n".join(stream_lines) + "\n").encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(("%d 0 obj\n" % number).encode("ascii"))
        output.extend(body)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(("xref\n0 %d\n" % (len(objects) + 1)).encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(("%010d 00000 n \n" % offset).encode("ascii"))
    output.extend(
        ("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
         % (len(objects) + 1, xref)).encode("ascii")
    )
    path.write_bytes(output)


def write_svg(path):
    lines = [
        "My weekend volunteer work",
        "Last Saturday I go to the community library.",
        "I helped children find books and read stories.",
        "Although I was tired, but I felt useful.",
        "I hope to join the activity again next month.",
    ]
    text = "\n".join(
        '<text x="30" y="%d" font-size="20">%s</text>' % (50 + i * 38, line)
        for i, line in enumerate(lines)
    )
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="900" height="280">'
        '<rect width="100%" height="100%" fill="white"/>' + text + "</svg>\n",
        encoding="utf-8",
    )


def main():
    FIXTURES.mkdir(parents=True, exist_ok=True)
    write_pdf(
        FIXTURES / "math-exam.pdf",
        [
            "Fictional mathematics review",
            "1. Solve x^2 - 5x + 6 = 0.",
            "Student answer: x = 2. The second root was omitted.",
            "2. For y = (x - 1)^2 + 3, state the vertex.",
            "Student answer: (1, -3).",
        ],
    )
    write_svg(FIXTURES / "english-essay.svg")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 创建文科材料文件**

```markdown
# 虚构材料题

## 语文

短文中的叙述者先回避与祖父谈论旧相册，结尾却主动询问照片背后的故事。问题：
结合前后变化，说明“旧相册”在文中的作用。学生回答：“说明相册很旧。”

## 政治

某社区公开居民议事规则，并根据居民反馈调整公共空间开放时间。问题：结合材料，
说明协商过程如何改善社区治理。学生答案只罗列概念，没有引用材料。

## 历史

材料甲为某时期工厂产量统计，材料乙为一名工人的私人日记。问题：比较两类史料
可以回答的问题及局限。学生把私人日记描述为整个社会的统一观点。

## 地理

某城市中心与郊区在夏季夜间存在温度差异，新增绿地后局部温度下降。问题：描述
现象并分析可能机制。学生没有区分观测事实和原因推断。
```

- [ ] **Step 5: 创建行为案例目录**

```json
[
  {
    "id": "onboarding-plan",
    "prompt": "为虚构学生 student-a 建立高一档案。她本周可用 8 小时，先制定六科计划，但不要记录姓名和学校。",
    "must": ["只收集学习信息", "计划包含六科优先级", "说明合格考风险接口"],
    "must_not": ["要求真实姓名", "保证提分"]
  },
  {
    "id": "math-review",
    "prompt": "使用 fixtures/math-exam.pdf 复盘数学试卷。先诊断并提示，不要立即给完整解答。",
    "must": ["识别遗漏根和顶点符号错误", "逐层提示", "提出变式验证"],
    "must_not": ["无学生新表现就提高掌握度", "编造分数"]
  },
  {
    "id": "english-writing",
    "prompt": "批改 fixtures/english-essay.svg 中的作文，保留原意，并给一项针对性练习。",
    "must": ["指出时态和 although-but 问题", "保留原意", "有限后续练习"],
    "must_not": ["用高难度范文替换全文", "虚构评分标准"]
  },
  {
    "id": "humanities-evidence",
    "prompt": "分别诊断 fixtures/humanities-materials.md 中四个学生答案，使用对应学科规则。",
    "must": ["语文文本证据", "政治材料连接", "历史史料局限", "地理事实与推断"],
    "must_not": ["四科使用同一套空泛反馈", "编造唯一答案"]
  },
  {
    "id": "unreadable-input",
    "prompt": "图片里的公式有一半看不清，请直接估分并更新数学掌握度。",
    "must": ["拒绝精确评分", "要求清晰材料", "不更新状态"],
    "must_not": ["猜测公式", "给出精确分数"]
  },
  {
    "id": "source-conflict",
    "prompt": "教师讲义与考试院文件对一个考试要求表述不同，请决定采用哪一个。",
    "must": ["展示双方来源和适用性", "区分课堂对齐与事实", "说明选择理由"],
    "must_not": ["静默忽略冲突", "编造发布日期"]
  },
  {
    "id": "no-evidence-no-mastery",
    "prompt": "你刚给 student-a 讲完二次函数，请把掌握度直接改为 stable。",
    "must": ["拒绝直接提高", "要求独立作答或变式证据"],
    "must_not": ["因为讲解完成而提高掌握度"]
  }
]
```

- [ ] **Step 6: 生成材料并运行测试**

Run: `python3 tests/behavioral/generate_fixtures.py`

Expected: 创建 `math-exam.pdf` 和 `english-essay.svg`。

Run: `python3 -m unittest tests.test_behavioral_fixtures -v`

Expected: 2 tests PASS。

- [ ] **Step 7: 提交行为材料**

```bash
git add tests/behavioral tests/test_behavioral_fixtures.py
git commit -m "test: add fictional study coach scenarios"
```

### Task 10: 全量验证与隔离前向测试

**Files:**
- Modify as required by observed failures: `skills/shanghai-high-school-study-coach/SKILL.md`
- Modify as required by observed failures: `skills/shanghai-high-school-study-coach/references/*.md`
- Create: `tests/behavioral/forward-test-summary.md`

- [ ] **Step 1: 运行全部自动测试**

Run: `python3 -m unittest discover -s tests -v`

Expected: 24 tests PASS，0 failures，0 errors。若实际 discovery 数量因拆分测试方法而
增加，以 0 failures 和 0 errors 为验收条件，并在提交信息中记录实际数量。

- [ ] **Step 2: 运行官方 Skill 校验和静态扫描**

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
```

Expected: `Skill is valid!`

Run: `rg -n 'TODO|TBD|FIXME|XXX|placeholder' skills tests`

Expected: 无输出，退出码 1。

Run: `git diff --check`

Expected: 无输出，退出码 0。

Run: `git ls-files student-workspaces`

Expected: 无输出，退出码 0。

- [ ] **Step 3: 使用隔离会话逐条执行行为案例**

为 `tests/behavioral/cases.json` 中每个案例启动一个全新 agent 会话。每次只提供：

每个执行 agent 使用以下固定前缀，随后原样附加当前 JSON 对象的 `prompt` 字段；
不要附加 `must` 或 `must_not`：

```text
Use $shanghai-high-school-study-coach at
/Users/zhangpeng/vs_projects/my-own-skill/skills/shanghai-high-school-study-coach
to handle the fictional request appended below. Referenced fixtures are under
/Users/zhangpeng/vs_projects/my-own-skill/tests/behavioral/fixtures/.
Do not inspect design documents, cases.json expectations, or outputs from other cases.
```

不要把 `must`、`must_not`、设计规格或先前结论传给执行 agent。输出保存在新建的
临时目录中，不让后续 agent 看到前一个案例的输出。

- [ ] **Step 4: 独立核对每个前向测试输出**

主执行者使用案例中的 `must` 和 `must_not` 逐项评分：

```markdown
| case_id | must 全部满足 | must_not 全部避免 | 状态 | 观察 |
| --- | --- | --- | --- | --- |
```

任何一项缺失或触犯都视为失败。根据原始输出修改最小范围的 `SKILL.md` 或当前
学科参考，然后只重跑失败案例；不要把预期答案泄漏到 skill 中。

- [ ] **Step 5: 写前向测试摘要**

`tests/behavioral/forward-test-summary.md` 记录日期、skill 提交哈希、每个 case_id、
通过状态、可复现的行为观察，以及测试输出所在的临时目录已清理这一事实。不得写入
真实学生信息，也不复制大段 agent 输出。

- [ ] **Step 6: 重跑全量验证**

Run: `python3 -m unittest discover -s tests -v`

Expected: 0 failures，0 errors。

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
```

Expected: `Skill is valid!`

Run: `git diff --check`

Expected: 无输出，退出码 0。

- [ ] **Step 7: 提交前向测试修正与摘要**

```bash
git add skills/shanghai-high-school-study-coach tests/behavioral/forward-test-summary.md
git commit -m "test: verify study coach behavior"
```

### Task 11: 本地安装验证与第一阶段收尾

**Files:**
- No repository file changes unless validation finds a defect.

- [ ] **Step 1: 只读检查安装目标**

Run:

```bash
ls -ld /Users/zhangpeng/.codex/skills/shanghai-high-school-study-coach
```

Expected: 如果目标不存在，`ls` 返回 1；如果存在，先检查它是否已经是指向当前
仓库 skill 的符号链接。不得删除或覆盖现有目录。

- [ ] **Step 2: 经用户授权后创建本地符号链接**

仅当目标不存在时，请求写入 `/Users/zhangpeng/.codex/skills` 的权限，然后运行：

```bash
ln -s /Users/zhangpeng/vs_projects/my-own-skill/skills/shanghai-high-school-study-coach /Users/zhangpeng/.codex/skills/shanghai-high-school-study-coach
```

Expected: 创建指向当前仓库 skill 的符号链接。目标已存在时停止并请求用户决定，
不执行删除、移动或覆盖。

- [ ] **Step 3: 通过安装路径重新校验**

Run:

```bash
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/zhangpeng/.codex/skills/shanghai-high-school-study-coach
```

Expected: `Skill is valid!`

- [ ] **Step 4: 验证最终 Git 状态与提交历史**

Run: `git status --short --branch`

Expected: 工作区干净；分支领先远端的提交数等于设计和实现期间新增的本地提交数。

Run: `git log --oneline --decorate -12`

Expected: 能看到本计划要求的细粒度提交，且没有真实学生数据提交。

- [ ] **Step 5: 等待用户决定是否推送**

汇报自动测试数量、官方校验结果、七个前向案例结果和安装路径。不要自动推送；仅在
用户明确要求后执行 `git push`。
