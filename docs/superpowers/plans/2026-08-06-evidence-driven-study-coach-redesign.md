# Evidence-Driven Study Coach Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recenter `shanghai-high-school-study-coach` on evidence-based weakness diagnosis and targeted reinforcement for six subjects, while removing exam-policy behavior and making persistent learning records structurally valid, symlink-safe, and concurrency-safe.

**Architecture:** Keep one core coaching skill and load exactly one subject reference for subject-specific diagnosis. Store immutable structured session and plan revisions as facts, derive `state.json` from the active fact revisions, and route every persistent write through one locked transactional script. Keep one-off tutoring fully stateless.

**Tech Stack:** Codex Skills, Markdown, JSON, Python 3.9 standard library, POSIX `dir_fd`/`O_NOFOLLOW`/`fcntl.flock`, `unittest`, Git.

---

## Execution Constraints

- Work on the existing `feature/shanghai-study-coach-phase-1` branch. Do not create a worktree.
- Do not push or create a pull request without explicit user instruction.
- Use only fictional workspaces under `tempfile.TemporaryDirectory()` in tests.
- Do not access exam-policy websites or place policy URLs in the Skill package.
- Follow strict TDD for every behavior change: add one failing test, observe the expected failure, implement the minimum behavior, then rerun the focused and affected suites.
- After every task, run separate spec-compliance and code-quality reviews. Fix findings and repeat the relevant review before starting the next task.

## File Responsibility Map

**Create:**

- `skills/shanghai-high-school-study-coach/scripts/learning_state.py`: pure schemas, fact validation, revision-chain selection, and deterministic reconciliation.
- `skills/shanghai-high-school-study-coach/scripts/commit_learning_state.py`: the only post-initialization fact/state writer; owns locking and atomic publication.
- `tests/workspace_fixtures.py`: canonical fictional state, session, plan, and workspace builders shared by tests.
- `tests/test_learning_state.py`: fact-schema and reconciliation tests.
- `tests/test_commit_learning_state.py`: transactional, retry, failure, and concurrency tests.

**Rewrite or substantially modify:**

- `skills/shanghai-high-school-study-coach/SKILL.md`: core evidence-driven coaching protocol.
- `skills/shanghai-high-school-study-coach/references/{chinese,mathematics,english,politics,history,geography}.md`: fixed modules, dynamic-unit normalization, diagnosis, detailed explanation, reinforcement, and transfer rules.
- `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py`: descriptor-safe workspace loading and schema-v2 consistency validation.
- `skills/shanghai-high-school-study-coach/scripts/init_student.py`: descriptor-relative schema-v2 workspace construction.
- `skills/shanghai-high-school-study-coach/scripts/summarize_progress.py`: derived weakness, pattern, review, and priority summary.
- `skills/shanghai-high-school-study-coach/assets/student-workspace-template/{profile.md,state.json}`: six-subject schema-v2 initial workspace.
- `skills/shanghai-high-school-study-coach/agents/openai.yaml`: weakness-diagnosis-centered UI metadata.
- `tests/test_{skill_contract,reference_contracts,validate_student_data,init_student,summarize_progress,behavioral_fixtures}.py`: redesigned contracts and regressions.
- `tests/behavioral/{cases.json,forward-test-summary.md}`: redesigned isolated scenarios and final tested commit.
- `.gitignore`: restore `/.worktrees/` while retaining student privacy ignores.

**Delete:**

- `skills/shanghai-high-school-study-coach/references/shanghai-curriculum-and-exams.md`
- `skills/shanghai-high-school-study-coach/assets/session-record-template.md`
- `skills/shanghai-high-school-study-coach/assets/mistake-record-template.md`
- `skills/shanghai-high-school-study-coach/assets/student-workspace-template/plans/current.md`

## Canonical Schema-V2 Contract

Use these constants in code and tests:

```python
SUBJECTS = (
    "chinese",
    "mathematics",
    "english",
    "politics",
    "history",
    "geography",
)
TASK_MODES = (
    "assessment",
    "explanation",
    "practice",
    "grading",
    "review",
    "planning",
)
CONTENT_STATES = (
    "unassessed",
    "suspected_gap",
    "confirmed_gap",
    "strengthening",
    "provisionally_mastered",
    "stable",
    "transferable",
)
PATTERN_STATES = (
    "observed_once",
    "recurring",
    "improving",
    "controlled",
)
EVIDENCE_TYPES = (
    "initial_attempt",
    "diagnostic",
    "correction",
    "variant",
    "delayed_retest",
    "transfer",
)
HINT_LEVELS = (
    "none",
    "locate",
    "principle",
    "next_step",
    "worked_example",
)
```

A session revision uses this shape:

```json
{
  "schema_version": 2,
  "record_type": "session",
  "record_id": "record-math-001",
  "session_id": "session-math-001",
  "supersedes_record_id": null,
  "status": "completed",
  "subject": "mathematics",
  "task_mode": "practice",
  "completed_at": "2026-08-06T10:00:00+00:00",
  "source_materials": ["fictional exercise 1"],
  "student_attempt": "I used the midpoint but did not prove both lines perpendicular.",
  "observations": [
    {
      "evidence_id": "evidence-math-001",
      "target_kind": "knowledge_unit",
      "module_id": "geometry",
      "target_id": "mathematics.geometry.dihedral-angle",
      "target_name": "二面角的平面角",
      "aliases": [],
      "evidence_type": "diagnostic",
      "outcome": "incorrect",
      "hint_level": "principle",
      "student_response": "I only proved CQ is perpendicular to PB.",
      "first_substantive_error": "The second perpendicular line was not established.",
      "student_explanation": null,
      "next_review_at": null,
      "uncertainty": null
    }
  ],
  "remaining_uncertainty": []
}
```

A plan revision uses this shape:

```json
{
  "schema_version": 2,
  "record_type": "plan_item",
  "record_id": "record-plan-001",
  "item_id": "item-math-001",
  "supersedes_record_id": null,
  "status": "pending",
  "subject": "mathematics",
  "target_kind": "knowledge_unit",
  "target_id": "mathematics.geometry.dihedral-angle",
  "task": "Complete one no-hint dihedral-angle variant.",
  "estimated_minutes": 15,
  "due_at": "2026-08-13T10:00:00+00:00",
  "priority": 1,
  "completion_evidence_id": null
}
```

### Task 1: Remove Exam-Policy Scope and Restore Repository Ignore Contract

**Files:**

- Modify: `.gitignore`
- Modify: `tests/test_skill_contract.py`
- Modify: `tests/test_reference_contracts.py`
- Modify: `skills/shanghai-high-school-study-coach/SKILL.md`
- Modify: `skills/shanghai-high-school-study-coach/references/politics.md`
- Delete: `skills/shanghai-high-school-study-coach/references/shanghai-curriculum-and-exams.md`

- [ ] **Step 1: Add a failing package-level policy-absence contract**

Add this test to `SkillContractTest`:

```python
def test_exam_policy_surface_is_absent(self):
    package = SKILL.parent
    paths = [SKILL, OPENAI_YAML, *sorted((package / "references").glob("*.md"))]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for forbidden in (
        "shanghai-curriculum-and-exams.md",
        "上海市教育考试院",
        "上海市教育委员会",
        "https://edu.sh.gov.cn/",
        "https://www.shmeea.edu.cn/",
        "考试政策",
        "评分口径",
        "官方原文 URL",
    ):
        with self.subTest(forbidden=forbidden):
            self.assertNotIn(forbidden, combined)
```

Replace the module-level `REFERENCE` constant with `REFERENCE_DIR`, update subject-reference reads
from `REFERENCE.parent / filename` to `REFERENCE_DIR / filename`, and delete
`test_source_governance_is_explicit`, `test_verified_source_table_has_complete_official_rows`, and
`test_exam_goals_can_overlap_and_require_student_confirmation`. Add:

```python
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
```

In the politics contract for this task, require headings
`("诊断", "材料边界", "答题组织", "练习与状态证据")` and phrases
`("材料依据", "概念", "分点", "材料不能支持的推断")`; remove every requirement for dates,
official sources, URLs, or policy validity.

- [ ] **Step 2: Run the new tests and observe the expected failures**

Run:

```bash
python3 -m unittest \
  tests.test_skill_contract.SkillContractTest.test_exam_policy_surface_is_absent \
  tests.test_reference_contracts.ReferenceContractTest.test_only_six_subject_references_exist -v
```

Expected: FAIL because the policy reference exists and the current Skill and politics reference contain policy-routing text.

- [ ] **Step 3: Remove the policy surface with the minimum contract-preserving edit**

Delete `references/shanghai-curriculum-and-exams.md`. Remove the policy-loading paragraph and official-source priority from `SKILL.md`. Replace the politics `## 时效与来源` section with this subject-only material rule:

```markdown
## 材料边界

区分题目材料明确陈述的内容、可由学科概念解释的关系和材料不能支持的推断。
只根据学生当前教材、教师材料和题目给定信息完成学习任务；缺少依据时标记不确定性，
不补写材料之外的事实。
```

Restore `.gitignore` to:

```gitignore
/.worktrees/
/student-workspaces/
__pycache__/
*.py[cod]
```

- [ ] **Step 4: Run focused contracts and repository privacy tests**

Run:

```bash
python3 -m unittest tests.test_skill_contract tests.test_reference_contracts tests.test_repository_privacy -v
```

Expected: PASS. No test may require a policy URL or policy source file.

- [ ] **Step 5: Commit**

```bash
git add .gitignore skills/shanghai-high-school-study-coach tests/test_skill_contract.py tests/test_reference_contracts.py
git commit -m "refactor: remove exam policy scope from study coach"
```

### Task 2: Add Structured Fact Schemas and Canonical Test Fixtures

**Files:**

- Create: `skills/shanghai-high-school-study-coach/scripts/learning_state.py`
- Create: `tests/workspace_fixtures.py`
- Create: `tests/test_learning_state.py`

- [ ] **Step 1: Write failing schema tests**

Add fixture builders with explicit defaults:

```python
def session_fact(**overrides):
    value = {
        "schema_version": 2,
        "record_type": "session",
        "record_id": "record-session-001",
        "session_id": "session-001",
        "supersedes_record_id": None,
        "status": "completed",
        "subject": "mathematics",
        "task_mode": "practice",
        "completed_at": "2026-08-06T10:00:00+00:00",
        "source_materials": ["fictional prompt"],
        "student_attempt": "fictional student attempt",
        "observations": [],
        "remaining_uncertainty": [],
    }
    value.update(overrides)
    return value


def knowledge_observation(**overrides):
    value = {
        "evidence_id": "evidence-001",
        "target_kind": "knowledge_unit",
        "module_id": "geometry",
        "target_id": "mathematics.geometry.dihedral-angle",
        "target_name": "二面角的平面角",
        "aliases": [],
        "evidence_type": "diagnostic",
        "outcome": "incorrect",
        "hint_level": "principle",
        "student_response": "fictional response",
        "first_substantive_error": "fictional first error",
        "student_explanation": None,
        "next_review_at": None,
        "uncertainty": None,
    }
    value.update(overrides)
    return value
```

Test these exact behaviors in `tests/test_learning_state.py`:

```python
def test_completed_session_may_record_direct_explanation_without_evidence(self):
    validate_session_fact(session_fact(student_attempt=None, observations=[]))


def test_observation_requires_nonempty_student_response(self):
    fact = session_fact(observations=[knowledge_observation(student_response="")])
    with self.assertRaisesRegex(ValidationError, "student_response"):
        validate_session_fact(fact)


def test_transfer_requires_no_hint_and_student_explanation(self):
    fact = session_fact(observations=[knowledge_observation(
        evidence_type="transfer",
        outcome="correct",
        hint_level="principle",
        first_substantive_error=None,
        student_explanation=None,
    )])
    with self.assertRaisesRegex(ValidationError, "transfer"):
        validate_session_fact(fact)


def test_record_and_stable_ids_reject_path_characters(self):
    with self.assertRaisesRegex(ValidationError, "record_id"):
        validate_session_fact(session_fact(record_id="../escape"))
```

- [ ] **Step 2: Run tests and observe the missing-module failure**

Run:

```bash
python3 -m unittest tests.test_learning_state -v
```

Expected: ERROR because `learning_state.py` does not exist.

- [ ] **Step 3: Implement pure fact validators**

Create `learning_state.py` with the canonical constants above and these public APIs:

```python
from datetime import datetime
import re


ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,95}$")


class ValidationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def _require_id(value, field):
    require(isinstance(value, str) and ID.fullmatch(value), f"{field} is invalid")


def _require_timestamp(value, field, allow_none=False):
    if allow_none and value is None:
        return
    require(isinstance(value, str) and value.strip(), f"{field} is required")
    try:
        datetime.fromisoformat(value)
    except ValueError as error:
        raise ValidationError(f"{field} must be an ISO-8601 timestamp") from error


def _require_exact_keys(value, expected, label):
    require(set(value) == expected,
            f"{label} fields are invalid: {sorted(set(value) ^ expected)}")


def validate_observation(observation, subject):
    require(isinstance(observation, dict), "observation must be an object")
    _require_exact_keys(observation, {
        "evidence_id", "target_kind", "module_id", "target_id", "target_name",
        "aliases", "evidence_type", "outcome", "hint_level", "student_response",
        "first_substantive_error", "student_explanation", "next_review_at",
        "uncertainty",
    }, "observation")
    _require_id(observation.get("evidence_id"), "evidence_id")
    require(observation.get("target_kind") in ("knowledge_unit", "pattern"),
            "target_kind is invalid")
    _require_id(observation.get("module_id"), "module_id")
    target_id = observation.get("target_id")
    require(isinstance(target_id, str) and target_id.startswith(subject + "."),
            "target_id must match session subject")
    require(isinstance(observation.get("target_name"), str)
            and observation["target_name"].strip(), "target_name is required")
    require(isinstance(observation.get("aliases"), list)
            and all(isinstance(value, str) and value.strip()
                    for value in observation["aliases"]), "aliases is invalid")
    require(observation.get("evidence_type") in EVIDENCE_TYPES,
            "evidence_type is invalid")
    require(observation.get("outcome") in ("correct", "incorrect"),
            "outcome is invalid")
    require(observation.get("hint_level") in HINT_LEVELS,
            "hint_level is invalid")
    require(isinstance(observation.get("student_response"), str)
            and observation["student_response"].strip(),
            "student_response is required")
    if observation["outcome"] == "incorrect":
        require(isinstance(observation.get("first_substantive_error"), str)
                and observation["first_substantive_error"].strip(),
                "first_substantive_error is required for incorrect evidence")
    else:
        require(observation.get("first_substantive_error") is None,
                "first_substantive_error must be null for correct evidence")
    if observation["evidence_type"] == "transfer" and observation["outcome"] == "correct":
        require(observation["hint_level"] == "none"
                and isinstance(observation.get("student_explanation"), str)
                and observation["student_explanation"].strip(),
                "correct transfer evidence requires no hint and a student explanation")


def validate_session_fact(fact):
    require(isinstance(fact, dict), "session fact must be an object")
    _require_exact_keys(fact, {
        "schema_version", "record_type", "record_id", "session_id",
        "supersedes_record_id", "status", "subject", "task_mode", "completed_at",
        "source_materials", "student_attempt", "observations",
        "remaining_uncertainty",
    }, "session fact")
    require(fact.get("schema_version") == 2
            and type(fact.get("schema_version")) is int,
            "schema_version must be the integer 2")
    require(fact.get("record_type") == "session", "record_type must be session")
    _require_id(fact.get("record_id"), "record_id")
    _require_id(fact.get("session_id"), "session_id")
    supersedes = fact.get("supersedes_record_id")
    require(supersedes is None or (isinstance(supersedes, str) and ID.fullmatch(supersedes)),
            "supersedes_record_id is invalid")
    require(fact.get("status") in ("incomplete", "completed"), "status is invalid")
    require(fact.get("subject") in SUBJECTS, "subject is invalid")
    require(fact.get("task_mode") in TASK_MODES, "task_mode is invalid")
    _require_timestamp(fact.get("completed_at"), "completed_at",
                       allow_none=fact["status"] == "incomplete")
    require(isinstance(fact.get("source_materials"), list)
            and all(isinstance(value, str) and value.strip()
                    for value in fact["source_materials"]),
            "source_materials is invalid")
    require(fact.get("student_attempt") is None
            or isinstance(fact.get("student_attempt"), str),
            "student_attempt must be null or a string")
    require(isinstance(fact.get("observations"), list), "observations must be a list")
    require(isinstance(fact.get("remaining_uncertainty"), list)
            and all(isinstance(value, str) and value.strip()
                    for value in fact["remaining_uncertainty"]),
            "remaining_uncertainty is invalid")
    for observation in fact["observations"]:
        validate_observation(observation, fact["subject"])
    evidence_ids = [item["evidence_id"] for item in fact["observations"]]
    require(len(evidence_ids) == len(set(evidence_ids)),
            "evidence_id values must be unique within a session")


def validate_plan_fact(fact):
    require(isinstance(fact, dict), "plan fact must be an object")
    _require_exact_keys(fact, {
        "schema_version", "record_type", "record_id", "item_id",
        "supersedes_record_id", "status", "subject", "target_kind", "target_id",
        "task", "estimated_minutes", "due_at", "priority",
        "completion_evidence_id",
    }, "plan fact")
    require(fact.get("schema_version") == 2
            and type(fact.get("schema_version")) is int,
            "schema_version must be the integer 2")
    require(fact.get("record_type") == "plan_item", "record_type must be plan_item")
    _require_id(fact.get("record_id"), "record_id")
    _require_id(fact.get("item_id"), "item_id")
    supersedes = fact.get("supersedes_record_id")
    require(supersedes is None or (isinstance(supersedes, str) and ID.fullmatch(supersedes)),
            "supersedes_record_id is invalid")
    require(fact.get("status") in ("pending", "completed"), "status is invalid")
    require(fact.get("subject") in SUBJECTS, "subject is invalid")
    require(fact.get("target_kind") in ("knowledge_unit", "pattern"),
            "target_kind is invalid")
    require(isinstance(fact.get("target_id"), str)
            and fact["target_id"].startswith(fact["subject"] + "."),
            "target_id must match plan subject")
    require(isinstance(fact.get("task"), str) and fact["task"].strip(),
            "task is required")
    require(type(fact.get("estimated_minutes")) is int
            and fact["estimated_minutes"] > 0,
            "estimated_minutes must be a positive integer")
    _require_timestamp(fact.get("due_at"), "due_at", allow_none=True)
    require(type(fact.get("priority")) is int and 1 <= fact["priority"] <= 4,
            "priority must be an integer from 1 to 4")
    if fact["status"] == "completed":
        _require_id(fact.get("completion_evidence_id"), "completion_evidence_id")
    else:
        require(fact.get("completion_evidence_id") is None,
                "pending plan item cannot have completion evidence")


def validate_fact(fact):
    require(isinstance(fact, dict), "fact must be an object")
    if fact.get("record_type") == "session":
        validate_session_fact(fact)
    elif fact.get("record_type") == "plan_item":
        validate_plan_fact(fact)
    else:
        raise ValidationError("record_type is invalid")
```

- [ ] **Step 4: Run the schema tests**

Run:

```bash
python3 -m unittest tests.test_learning_state -v
```

Expected: PASS for all schema tests.

- [ ] **Step 5: Commit**

```bash
git add skills/shanghai-high-school-study-coach/scripts/learning_state.py tests/workspace_fixtures.py tests/test_learning_state.py
git commit -m "feat: define structured learning fact schemas"
```

### Task 3: Reconcile Immutable Facts into Evidence-Based State

**Files:**

- Modify: `skills/shanghai-high-school-study-coach/scripts/learning_state.py`
- Modify: `tests/test_learning_state.py`
- Modify: `tests/workspace_fixtures.py`

- [ ] **Step 1: Add failing revision and transition tests**

Cover these exact cases:

```python
def test_single_initial_error_is_only_suspected(self):
    fact = session_fact(observations=[knowledge_observation(
        evidence_type="initial_attempt", outcome="incorrect")])
    state = reconcile_state("student-a", [fact], [], now=NOW)
    unit = state["subjects"]["mathematics"]["knowledge_units"][
        "mathematics.geometry.dihedral-angle"
    ]
    self.assertEqual("suspected_gap", unit["status"])


def test_diagnostic_error_confirms_gap_and_variant_does_not_skip_hint_rule(self):
    first = session_fact(observations=[knowledge_observation()])
    second = session_fact(
        record_id="record-session-002",
        session_id="session-002",
        completed_at="2026-08-06T10:10:00+00:00",
        observations=[knowledge_observation(
            evidence_id="evidence-002",
            evidence_type="variant",
            outcome="correct",
            hint_level="principle",
            first_substantive_error=None,
        )],
    )
    state = reconcile_state("student-a", [first, second], [], now=NOW)
    unit = state["subjects"]["mathematics"]["knowledge_units"][
        "mathematics.geometry.dihedral-angle"
    ]
    self.assertEqual("strengthening", unit["status"])


def test_delayed_no_hint_success_is_stable(self):
    fact = session_fact(observations=[knowledge_observation(
        evidence_type="delayed_retest",
        outcome="correct",
        hint_level="none",
        first_substantive_error=None,
    )])
    state = reconcile_state("student-a", [fact], [], now=NOW)
    self.assertEqual(
        "stable",
        state["subjects"]["mathematics"]["knowledge_units"][
            "mathematics.geometry.dihedral-angle"
        ]["status"],
    )


def test_plan_completion_requires_matching_active_evidence(self):
    session = session_fact(observations=[knowledge_observation(
        outcome="correct", evidence_type="variant", hint_level="none",
        first_substantive_error=None)])
    plan = plan_fact(status="completed", completion_evidence_id="evidence-001")
    state = reconcile_state("student-a", [session], [plan], now=NOW)
    self.assertEqual(1, state["process"]["completed_plan_items"])


def test_revision_chain_rejects_fork(self):
    root = session_fact(status="incomplete")
    left = session_fact(record_id="record-left", supersedes_record_id=root["record_id"])
    right = session_fact(record_id="record-right", supersedes_record_id=root["record_id"])
    with self.assertRaisesRegex(ValidationError, "fork"):
        reconcile_state("student-a", [root, left, right], [], now=NOW)
```

Add the following named tests with the stated arrangement and assertion:

| Test | Arrangement | Required assertion |
| --- | --- | --- |
| `test_duplicate_record_id_is_rejected` | Two session facts reuse one `record_id` | Raises `ValidationError` containing `duplicate record_id` |
| `test_revision_cycle_is_rejected` | Two records supersede each other | Raises an error containing `cycle` |
| `test_revision_cannot_change_session_id` | Child record supersedes a parent but uses another `session_id` | Raises an error containing `stable id` |
| `test_duplicate_active_evidence_id_is_rejected` | Two active completed sessions reuse one `evidence_id` | Raises an error containing `evidence_id` |
| `test_pattern_progresses_from_once_to_recurring_to_controlled` | Two incorrect pattern observations followed by a no-hint delayed success | Status sequence is `observed_once`, `recurring`, then `controlled` |
| `test_later_diagnostic_failure_lowers_stable_mastery` | Stable evidence precedes a later incorrect diagnostic | Final content status is `confirmed_gap` |
| `test_reconciliation_is_idempotent_and_preserves_updated_at` | Reconcile identical facts against the first result using a later `now` | Entire second state equals the first state |

- [ ] **Step 2: Run focused tests and observe missing reconciliation**

Run:

```bash
python3 -m unittest tests.test_learning_state.ReconciliationTest -v
```

Expected: FAIL because `reconcile_state` is not implemented.

- [ ] **Step 3: Implement revision selection and deterministic transitions**

Add these public functions and transition rules:

```python
def _active_revisions(records, stable_field, validator):
    by_record_id = {}
    children = {}
    for record in records:
        validator(record)
        record_id = record["record_id"]
        require(record_id not in by_record_id, f"duplicate record_id: {record_id}")
        by_record_id[record_id] = record
    for record in records:
        parent_id = record["supersedes_record_id"]
        if parent_id is None:
            continue
        require(parent_id in by_record_id,
                f"missing superseded record: {parent_id}")
        parent = by_record_id[parent_id]
        require(parent[stable_field] == record[stable_field],
                "revision must preserve stable id")
        require(parent_id not in children, f"revision fork at {parent_id}")
        children[parent_id] = record["record_id"]
    for record in records:
        seen = set()
        current = record
        while current["supersedes_record_id"] is not None:
            require(current["record_id"] not in seen, "revision cycle detected")
            seen.add(current["record_id"])
            current = by_record_id[current["supersedes_record_id"]]
    leaves = {}
    for record in records:
        if record["record_id"] not in children:
            stable_id = record[stable_field]
            require(stable_id not in leaves, f"multiple active revisions for {stable_id}")
            leaves[stable_id] = record
    return leaves


def _content_status(observation):
    if observation["outcome"] == "incorrect":
        if observation["evidence_type"] == "initial_attempt":
            return "suspected_gap"
        return "confirmed_gap"
    if observation["hint_level"] != "none" or observation["evidence_type"] == "correction":
        return "strengthening"
    if observation["evidence_type"] in ("initial_attempt", "diagnostic", "variant"):
        return "provisionally_mastered"
    if observation["evidence_type"] == "delayed_retest":
        return "stable"
    return "transferable"


def _pattern_status(observation, prior_incorrect_count):
    if observation["outcome"] == "incorrect":
        return "recurring" if prior_incorrect_count >= 1 else "observed_once"
    if observation["evidence_type"] in ("delayed_retest", "transfer") \
            and observation["hint_level"] == "none":
        return "controlled"
    return "improving"
```

`reconcile_state(student_id, sessions, plan_items, previous_state=None, now=None)` must:

1. Select one active revision per stable ID.
2. Ignore active session revisions whose status is `incomplete`.
3. Sort completed active sessions by `(completed_at, session_id, record_id)`.
4. Reject duplicate active `evidence_id` values.
5. Build six subject entries with `knowledge_units` and `patterns` maps.
6. Store each target's canonical name, module, aliases, status, evidence IDs, last evidence time, and next review time.
7. Count unique completed active sessions.
8. Count only active completed plan items whose completion evidence exists and matches subject, target kind, and target ID.
9. Preserve the old `updated_at` and exact old state when normalized output is unchanged; otherwise use `now`.

- [ ] **Step 4: Run reconciliation and schema tests**

Run:

```bash
python3 -m unittest tests.test_learning_state -v
```

Expected: PASS, including demotion, revision-chain, plan-evidence, and no-op tests.

- [ ] **Step 5: Commit**

```bash
git add skills/shanghai-high-school-study-coach/scripts/learning_state.py tests/test_learning_state.py tests/workspace_fixtures.py
git commit -m "feat: reconcile learning state from immutable facts"
```

### Task 4: Make Workspace Validation Descriptor-Safe

**Files:**

- Rewrite: `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py`
- Rewrite: `tests/test_validate_student_data.py`
- Modify: `tests/workspace_fixtures.py`

- [ ] **Step 1: Write failing empty-state symlink and consistency tests**

Parameterize every required child, including children that contain no evidence:

```python
def test_rejects_symlinked_required_children_in_empty_workspace(self):
    for relative, is_directory in (
        ("profile.md", False),
        ("state.json", False),
        (".workspace.lock", False),
        ("sessions", True),
        ("plan-items", True),
        ("summaries", True),
        ("materials", True),
    ):
        with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "student-a"
            create_workspace(workspace)
            target = workspace / relative
            outside = root / ("outside-dir" if is_directory else "outside-file")
            if is_directory:
                outside.mkdir()
                target.rmdir()
            else:
                outside.write_text("outside", encoding="utf-8")
                target.unlink()
            target.symlink_to(outside, target_is_directory=is_directory)
            with self.assertRaisesRegex(ValidationError, "symlink|regular|directory"):
                validate_workspace(workspace)


def test_rejects_state_not_derived_from_active_facts(self):
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp) / "student-a"
        create_workspace(workspace)
        state = json.loads((workspace / "state.json").read_text(encoding="utf-8"))
        state["process"]["recorded_sessions"] = 9
        (workspace / "state.json").write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValidationError, "derived|reconcile|recorded_sessions"):
            validate_workspace(workspace)
```

Add these named tests:

| Test | Fixture mutation | Required assertion |
| --- | --- | --- |
| `test_rejects_symlinked_session_fact` | `sessions/record-session-001.json` points outside | Raises an error containing `invalid type` or `symlink` |
| `test_rejects_non_utf8_session_fact` | Write `b"\xff\xfe"` to a regular session fact | Raises an error containing `UTF-8` |
| `test_rejects_plan_record_in_sessions_directory` | Put a valid `plan_item` JSON under `sessions/` | Raises an error containing `record_type` |
| `test_rejects_state_evidence_not_present_in_active_facts` | Add `evidence-missing` to one state target | Raises an error containing `derived` or `evidence` |
| `test_cli_reports_invalid_workspace_without_traceback` | Run the CLI against each invalid fixture | Exit code is 1, stderr starts with `INVALID:`, and stderr lacks `Traceback` |

- [ ] **Step 2: Run the validator tests and observe failures**

Run:

```bash
python3 -m unittest tests.test_validate_student_data -v
```

Expected: FAIL because current required children follow symlinks and schema-v1 state trusts counters and arbitrary files.

- [ ] **Step 3: Implement descriptor-safe snapshot loading**

Define:

```python
@dataclass(frozen=True)
class WorkspaceSnapshot:
    state: dict
    sessions: tuple
    plan_items: tuple


def _directory_flags():
    require(hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW"),
            "descriptor-safe workspace access is unavailable")
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _regular_flags():
    require(hasattr(os, "O_NOFOLLOW"),
            "descriptor-safe workspace access is unavailable")
    return os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)


def _open_child(parent_fd, name, expected_directory):
    entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    expected = stat.S_ISDIR if expected_directory else stat.S_ISREG
    require(expected(entry.st_mode), f"required child has invalid type: {name}")
    flags = _directory_flags() if expected_directory else _regular_flags()
    child_fd = os.open(name, flags, dir_fd=parent_fd)
    opened = os.fstat(child_fd)
    require(expected(opened.st_mode)
            and (opened.st_dev, opened.st_ino) == (entry.st_dev, entry.st_ino),
            f"required child identity changed: {name}")
    return child_fd
```

Open the workspace once with `resolved = Path(workspace).resolve(strict=True)` followed by
`os.open(os.fspath(resolved), _directory_flags())`. From then on, access only descriptor-relative
child names. Read regular files by repeated `os.read` until EOF and decode UTF-8. Enumerate fact
directories with their directory descriptors; accept only regular `.json` entries and parse each
with the matching pure validator.

Expose:

```python
def read_workspace_snapshot(workspace, require_consistent_state=True):
    """Return an immutable snapshot read from one held workspace descriptor."""


def open_workspace_descriptor(workspace):
    """Resolve once and return a no-follow directory descriptor for the workspace."""


def read_workspace_snapshot_fd(root_fd, require_consistent_state=True):
    """Read all required children relative to an already held workspace descriptor."""


def _open_existing_regular(parent_fd, name, writable=False):
    """Open one verified regular child without following symlinks."""


def _open_existing_directory(parent_fd, name):
    """Open one verified directory child without following symlinks."""


def validate_state(state, sessions, plan_items):
    """Validate schema-v2 shape, evidence references, and derived consistency."""


def validate_workspace(workspace):
    return read_workspace_snapshot(workspace, require_consistent_state=True)


def validate_workspace_fd(root_fd):
    return read_workspace_snapshot_fd(root_fd, require_consistent_state=True)
```

For consistency, call `reconcile_state` with `now=state["updated_at"]` and compare the complete candidate with the loaded state. Error messages must identify the first mismatched top-level field.

- [ ] **Step 4: Run validator, learning-state, and privacy tests**

Run:

```bash
python3 -m unittest tests.test_learning_state tests.test_validate_student_data tests.test_repository_privacy -v
```

Expected: PASS. Empty workspaces with any required-child symlink must fail.

- [ ] **Step 5: Commit**

```bash
git add skills/shanghai-high-school-study-coach/scripts/validate_student_data.py tests/test_validate_student_data.py tests/workspace_fixtures.py
git commit -m "fix: validate student workspaces without following symlinks"
```

### Task 5: Build Schema-V2 Workspaces Through Held Directory Descriptors

**Files:**

- Modify: `skills/shanghai-high-school-study-coach/scripts/init_student.py`
- Modify: `skills/shanghai-high-school-study-coach/assets/student-workspace-template/profile.md`
- Modify: `skills/shanghai-high-school-study-coach/assets/student-workspace-template/state.json`
- Delete: `skills/shanghai-high-school-study-coach/assets/student-workspace-template/plans/current.md`
- Delete: `skills/shanghai-high-school-study-coach/assets/session-record-template.md`
- Delete: `skills/shanghai-high-school-study-coach/assets/mistake-record-template.md`
- Modify: `tests/test_init_student.py`

- [ ] **Step 1: Write failing schema-v2 construction tests**

Update the expected tree:

```python
for relative in (
    "profile.md",
    "state.json",
    ".workspace.lock",
    "sessions",
    "plan-items",
    "summaries",
    "materials",
):
    self.assertTrue((workspace / relative).exists(), relative)
self.assertEqual(2, state["schema_version"])
self.assertEqual(
    {"chinese", "mathematics", "english", "politics", "history", "geography"},
    set(state["subjects"]),
)
```

Add an adversarial construction test that replaces the temporary directory name with a symlink after the first child creation. Patch a new `_mkdir_at(parent_fd, name)` helper, move the named temporary directory, replace its old name with a symlink to an outside directory, and assert that no expected child or file appears outside. Initialization must fail with an identity-change error and preserve the outside marker.

- [ ] **Step 2: Run init tests and observe expected failures**

Run:

```bash
python3 -m unittest tests.test_init_student -v
```

Expected: FAIL because current construction uses absolute `Path.mkdir()` and `Path.write_text()`, and creates the schema-v1 tree.

- [ ] **Step 3: Replace path-based construction with descriptor-relative helpers**

Implement and use:

```python
def _mkdir_at(parent_fd, name):
    os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    child_fd = os.open(name, _directory_open_flags(), dir_fd=parent_fd)
    opened = os.fstat(child_fd)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(child_fd)
        raise ValidationError("created child is not a directory: %s" % name)
    return child_fd


def _write_new_file(parent_fd, name, content, mode=0o600):
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | os.O_NOFOLLOW
        | getattr(os, "O_CLOEXEC", 0)
    )
    file_fd = os.open(name, flags, mode, dir_fd=parent_fd)
    try:
        data = content.encode("utf-8") if isinstance(content, str) else content
        offset = 0
        while offset < len(data):
            offset += os.write(file_fd, data[offset:])
        os.fsync(file_fd)
    finally:
        os.close(file_fd)
```

Create `sessions`, `plan-items`, `summaries`, and `materials` with `_mkdir_at` against the held temporary descriptor. Write `profile.md`, `state.json`, and `.workspace.lock` with `_write_new_file` against that descriptor. Close each child descriptor explicitly. Validate the constructed inode with a new descriptor-based validator entry point before no-clobber publication.

The state template must contain schema version 2, exactly six subject objects, empty `knowledge_units` and `patterns`, and zero process counters. The profile template must contain grade, term, current materials, teacher priorities, learning preferences, available time, and learning goals; remove selected-exam and exam-date fields.

- [ ] **Step 4: Run init and validator suites**

Run:

```bash
python3 -m unittest tests.test_init_student tests.test_validate_student_data -v
```

Expected: PASS, including temporary-name replacement and cleanup regressions.

- [ ] **Step 5: Commit**

```bash
git add skills/shanghai-high-school-study-coach/assets skills/shanghai-high-school-study-coach/scripts/init_student.py tests/test_init_student.py
git commit -m "feat: initialize descriptor-safe learning workspaces"
```

### Task 6: Add Locked Fact Commit and Concurrent Reconciliation

**Files:**

- Create: `skills/shanghai-high-school-study-coach/scripts/commit_learning_state.py`
- Create: `tests/test_commit_learning_state.py`
- Modify: `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py`

- [ ] **Step 1: Write failing transaction tests**

Add these transaction tests before the concurrency test:

| Test | Required assertion |
| --- | --- |
| `test_session_commit_publishes_fact_and_reconciles_state` | Fact file exists, one session is counted, and the target status matches its observation |
| `test_completed_plan_revision_requires_and_counts_matching_evidence` | A completion revision supersedes pending, matches an active evidence ID, and increments the plan count once |
| `test_identical_record_retry_is_noop` | Second call reports no-op, creates no extra file, and preserves `updated_at` |
| `test_conflicting_record_reuse_is_rejected` | Same `record_id` with different canonical JSON raises and preserves the original bytes and state |
| `test_state_replace_failure_is_recoverable` | Injected pre-replace failure leaves the fact and old state; retry reconciles exactly once |

The concurrency assertion must be:

```python
def test_two_concurrent_session_commits_preserve_both_facts(self):
    first = session_fact(
        record_id="record-session-001",
        session_id="session-001",
        observations=[knowledge_observation(evidence_id="evidence-001")],
    )
    second = session_fact(
        record_id="record-session-002",
        session_id="session-002",
        completed_at="2026-08-06T10:01:00+00:00",
        observations=[knowledge_observation(
            evidence_id="evidence-002",
            target_id="mathematics.geometry.line-plane-perpendicular",
            target_name="线面垂直",
        )],
    )
    results = run_commits_concurrently(workspace, first, second)
    self.assertEqual([0, 0], sorted(result.returncode for result in results))
    snapshot = validate_workspace(workspace)
    self.assertEqual(2, snapshot.state["process"]["recorded_sessions"])
    self.assertEqual(
        {"record-session-001.json", "record-session-002.json"},
        {path.name for path in (workspace / "sessions").iterdir()},
    )
```

Inject a failure immediately before state replacement and assert that the published fact remains, old state remains readable, and retry reconciles the retained fact exactly once.

- [ ] **Step 2: Run transaction tests and observe the missing-script failure**

Run:

```bash
python3 -m unittest tests.test_commit_learning_state -v
```

Expected: ERROR because `commit_learning_state.py` does not exist.

- [ ] **Step 3: Implement the single transactional write path**

Expose:

```python
def commit_fact(workspace, fact, now=None):
    """Publish one immutable fact and reconcile state under one exclusive lock."""
```

The implementation order must be:

```python
validate_fact(fact)
root_fd = open_workspace_descriptor(workspace)
lock_fd = _open_existing_regular(root_fd, ".workspace.lock", writable=True)
fcntl.flock(lock_fd, fcntl.LOCK_EX)
snapshot = read_workspace_snapshot_fd(root_fd, require_consistent_state=False)
fact_dir_fd = _open_existing_directory(
    root_fd,
    "sessions" if fact["record_type"] == "session" else "plan-items",
)
published = _publish_fact_no_clobber(fact_dir_fd, fact)
snapshot = read_workspace_snapshot_fd(root_fd, require_consistent_state=False)
candidate = reconcile_state(
    snapshot.state["student_id"],
    snapshot.sessions,
    snapshot.plan_items,
    previous_state=snapshot.state,
    now=now or datetime.now(timezone.utc).isoformat(),
)
validate_state(candidate, snapshot.sessions, snapshot.plan_items)
_replace_state_atomically(root_fd, candidate)
read_workspace_snapshot_fd(root_fd, require_consistent_state=True)
```

`_publish_fact_no_clobber` must canonicalize JSON with sorted keys, UTF-8, indentation, and a final newline. Use `O_CREAT | O_EXCL | O_NOFOLLOW`; if the record filename exists, return no-op only when the existing canonical bytes exactly match. Otherwise raise `ValidationError`.

`_replace_state_atomically` must create a unique `.state-<uuid>.tmp` with `O_EXCL | O_NOFOLLOW`, fully write and `fsync` it, then call `os.replace` with both directory descriptors set to the held root. Clean only the owned temporary name on failure. Always release `flock` and close all descriptors in `finally` blocks.

CLI contract:

```bash
python3 <skill-root>/scripts/commit_learning_state.py <workspace> --fact-file <json-file>
```

Print `COMMITTED: <record_id>` for a new fact and `NO-OP: <record_id>` for an identical retry. Print `ERROR:` without a traceback for validation and I/O failures.

- [ ] **Step 4: Run transaction, validation, and init suites**

Run:

```bash
python3 -m unittest \
  tests.test_commit_learning_state \
  tests.test_learning_state \
  tests.test_validate_student_data \
  tests.test_init_student -v
```

Expected: PASS. The concurrent test must complete with both facts and both state contributions.

- [ ] **Step 5: Commit**

```bash
git add skills/shanghai-high-school-study-coach/scripts/commit_learning_state.py skills/shanghai-high-school-study-coach/scripts/validate_student_data.py tests/test_commit_learning_state.py
git commit -m "feat: commit learning facts under an exclusive lock"
```

### Task 7: Render Evidence-Based Progress Without Trusting Stored Counters

**Files:**

- Rewrite: `skills/shanghai-high-school-study-coach/scripts/summarize_progress.py`
- Rewrite: `tests/test_summarize_progress.py`

- [ ] **Step 1: Write failing summary tests**

Build workspaces only through initialization and `commit_fact`. Assert the summary contains:

```python
self.assertIn("待确认薄弱: 1", output)
self.assertIn("已确认薄弱: 1", output)
self.assertIn("强化中: 1", output)
self.assertIn("到期复测", output)
self.assertIn("重复出现", output)
self.assertIn("优先级 1", output)
self.assertNotIn("预计分数", output)
self.assertNotIn("qualification", output)
```

Retain the current validated-snapshot race test: replace `state.json` after validation and prove rendering uses the returned snapshot rather than rereading paths. Add a test that a malicious newline in target name is escaped and cannot create a Markdown heading.

- [ ] **Step 2: Run summary tests and observe schema mismatch**

Run:

```bash
python3 -m unittest tests.test_summarize_progress -v
```

Expected: FAIL because the current renderer expects schema-v1 `goal_type`, qualification risk, and trusted counters.

- [ ] **Step 3: Implement deterministic rendering from the validated snapshot**

`render(workspace, now=None)` must:

1. Call `validate_workspace` once and retain the returned `WorkspaceSnapshot`.
2. Display process counts from the reconciled state.
3. Iterate the six canonical subjects.
4. Group content targets by the seven content states.
5. List recurring or improving patterns.
6. List active priority plan items ordered by `(priority, due_at, item_id)`.
7. Mark `next_review_at <= now` as due.
8. Escape all control characters before inserting values into Markdown.
9. Never print score predictions or policy information.

- [ ] **Step 4: Run affected tests**

Run:

```bash
python3 -m unittest tests.test_summarize_progress tests.test_commit_learning_state tests.test_validate_student_data -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/shanghai-high-school-study-coach/scripts/summarize_progress.py tests/test_summarize_progress.py
git commit -m "feat: summarize evidence-based learning priorities"
```

### Task 8: Rewrite the Core Coaching Protocol and Six Subject Adapters

**Files:**

- Rewrite: `skills/shanghai-high-school-study-coach/SKILL.md`
- Rewrite: `skills/shanghai-high-school-study-coach/references/chinese.md`
- Rewrite: `skills/shanghai-high-school-study-coach/references/mathematics.md`
- Rewrite: `skills/shanghai-high-school-study-coach/references/english.md`
- Rewrite: `skills/shanghai-high-school-study-coach/references/politics.md`
- Rewrite: `skills/shanghai-high-school-study-coach/references/history.md`
- Rewrite: `skills/shanghai-high-school-study-coach/references/geography.md`
- Modify: `skills/shanghai-high-school-study-coach/agents/openai.yaml`
- Rewrite: `tests/test_skill_contract.py`
- Rewrite: `tests/test_reference_contracts.py`

- [ ] **Step 1: Write failing core learning-loop contracts**

Require these behaviors through section-aware assertions rather than one global keyword bag:

```python
def test_direct_answer_requires_detailed_explanation_and_check(self):
    section = extract_section(self.content, "直接解析路径")
    for phrase in (
        "明确要求答案时立即提供完整解析",
        "条件和目标",
        "方法选择理由",
        "关键知识及适用条件",
        "完整过程",
        "容易出错",
        "结果或结论验证",
        "理解检查或最小变式",
        "解析本身不改变掌握状态",
    ):
        self.assertIn(phrase, section)


def test_single_error_is_suspected_before_diagnostic_confirmation(self):
    section = extract_section(self.content, "识别薄弱点")
    self.assertLess(section.index("suspected_gap"), section.index("confirmed_gap"))
    self.assertIn("单次错误", section)
    self.assertIn("追问或最小诊断", section)


def test_persistent_updates_use_only_transactional_writer(self):
    command = (
        "python3 <skill-root>/scripts/commit_learning_state.py "
        "<workspace> --fact-file <json-file>"
    )
    self.assertIn(command, self.content)
    self.assertNotIn("os.replace", self.content)
    self.assertNotIn("直接写入 `state.json`", self.content)
```

Require the seven content states, four pattern states, temporary-session zero writes, one-subject-at-a-time loading, source readability rules, first substantive error, minimal reinforcement, delayed retest, no-evidence-no-mastery, and no policy surface.

- [ ] **Step 2: Write failing subject-adapter contracts**

Each reference must contain exactly these operational headings:

```python
REQUIRED_HEADINGS = {
    "固定模块",
    "动态知识单元归一化",
    "诊断",
    "详细解析",
    "强化与迁移",
}
```

Require these fixed module IDs:

```python
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
```

Each adapter must explain how to distinguish content gaps from execution patterns, what a detailed explanation includes, how to create one same-type correction and one changed-context variant, and what independent transfer looks like for that subject.

- [ ] **Step 3: Run contracts and observe failures**

Run:

```bash
python3 -m unittest tests.test_skill_contract tests.test_reference_contracts -v
```

Expected: FAIL because current Skill uses the old mastery model, lacks a direct-answer section and transactional writer, and subject references lack fixed modules and normalization rules.

- [ ] **Step 4: Rewrite `SKILL.md` around the confirmed workflow**

Use this section order:

```markdown
# 上海高中学习教练

## 支持边界
## 定位学生工作区
## 识别任务模式
## 加载当前学科参考
## 选择学习路径
### 学习引导路径
### 直接解析路径
## 识别薄弱点
## 当场强化与延迟复测
## 记录学生表现证据
## 更新持久化状态
## 优先级和学习计划
## 图片与 PDF
## 隐私与失败
```

Frontmatter description must trigger on Shanghai high-school tutoring, real student attempts, exercises, grading, review, weakness diagnosis, targeted reinforcement, images/PDFs, and cross-session progress. It must mention only the six phase-one subjects and must not mention exam policies or official websites.

The persistent workflow must direct Codex to create a structured fact outside the workspace, validate that it records only real student behavior, call `commit_learning_state.py`, rerun `validate_student_data.py`, and delete its temporary fact file. It must never instruct Codex to edit `state.json`, session facts, or plan facts directly.

- [ ] **Step 5: Rewrite each subject adapter**

For each file, list its fixed module IDs as a Markdown table with module ID and Chinese meaning. Define normalization as:

1. Prefer an existing unit with the same learning objective and prerequisite boundary.
2. Add an alias only when the two names are demonstrably equivalent in the current material.
3. Keep two units separate when their applicability, evidence type, or prerequisite differs.
4. Create a pending-normalization unit rather than guessing when the mapping is ambiguous.

Keep the current valuable subject behavior: Chinese textual evidence and student-owned revision, mathematics first substantive error and condition checking, English meaning-preserving edits, politics concept-to-material linkage, history source limits, and geography observation-versus-inference boundaries. Remove all external policy verification behavior.

- [ ] **Step 6: Update UI metadata**

Use:

```yaml
interface:
  display_name: "上海高中学习教练"
  short_description: "根据学生真实作答识别六科薄弱点，并通过针对性练习持续强化"
  default_prompt: "Use $shanghai-high-school-study-coach to diagnose my current weak points from my actual work, teach the missing part, and guide one targeted verification step."
```

- [ ] **Step 7: Run contracts and Skill validation**

Run:

```bash
python3 -m unittest tests.test_skill_contract tests.test_reference_contracts -v
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
```

Expected: all tests PASS and validator prints `Skill is valid!`.

- [ ] **Step 8: Commit**

```bash
git add skills/shanghai-high-school-study-coach tests/test_skill_contract.py tests/test_reference_contracts.py
git commit -m "feat: center study coach on weakness reinforcement"
```

### Task 9: Replace Behavioral Scenarios and Forward-Test the Redesigned Skill

**Files:**

- Modify: `tests/behavioral/cases.json`
- Modify: `tests/test_behavioral_fixtures.py`
- Rewrite: `tests/behavioral/forward-test-summary.md`

- [ ] **Step 1: Write the failing behavioral catalog contract**

Set the expected IDs to:

```python
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
```

Remove `source-conflict` and all exam-policy assertions. Keep the strict `{id,prompt,must,must_not}` schema. Add exact checks that every phase-one subject appears in at least one prompt and that the direct-answer case requires method rationale, full derivation, error points, result verification, and a comprehension check.

- [ ] **Step 2: Run fixture tests and observe catalog failure**

Run:

```bash
python3 -m unittest tests.test_behavioral_fixtures -v
```

Expected: FAIL because the old seven-case catalog still contains source conflict and lacks the redesigned cases.

- [ ] **Step 3: Replace `cases.json` with twelve fictional cases**

Use the IDs above. Preserve existing deterministic PDF, SVG, and humanities fixture references. The required outcomes must include:

- guided math: identify both errors, stop at layered hints, and propose one changed-condition variant;
- direct math: provide a detailed explanation and a no-answer comprehension check, but no mastery update;
- English: preserve student meaning, identify both language issues, and generate one targeted exercise;
- Chinese: cite text and distinguish defensible interpretation from unsupported assertion;
- politics: connect provided material to a concept without external lookup;
- history: separate source claim, inference, and source limitation;
- geography: separate observed pattern from mechanism and avoid causal overreach;
- single error: mark only `suspected_gap` until a diagnostic result exists;
- reinforcement: move through correction, immediate variant, and later no-hint retest without skipping states;
- priority: choose one primary gap, one prerequisite if needed, one recurring pattern, and due retests;
- unreadable: pause diagnosis, answer, scoring, and persistence;
- no evidence: refuse to raise mastery because Codex explained the topic.

- [ ] **Step 4: Run the complete automated suite before agent evaluation**

Run:

```bash
python3 -m unittest discover -s tests -v
```

Expected: PASS with zero failures and zero errors.

- [ ] **Step 5: Run baseline pressure scenarios without the Skill**

Use fresh isolated agents. Give each agent only one raw case prompt and its referenced fictional fixture; do not provide the Skill, `must`, `must_not`, expected diagnosis, or prior outputs. Record whether the baseline directly answers, over-diagnoses one error, treats explanation as mastery, or misses targeted reinforcement.

- [ ] **Step 6: Run forward scenarios with the installed Skill**

For every case, use a new isolated agent and provide only the raw case prompt, raw fixture, and instruction to use `$shanghai-high-school-study-coach`. Do not leak expected outcomes. Evaluate each output against `must` and `must_not`; any failure requires a new failing contract or behavioral test, the minimum Skill/reference fix, focused test rerun, and a fresh isolated rerun of that case.

- [ ] **Step 7: Record final evidence at the final tested commit**

Commit every behavior fix and confirm `git status --short` is empty. Then run `git rev-parse HEAD`
immediately before the final clean forward run. Write its full 40-character output, date, baseline
observations, each case result, and cleanup confirmation to `forward-test-summary.md`. The summary
must state that all temporary workspaces and outputs were deleted and no real student data was used.

- [ ] **Step 8: Commit**

```bash
git add tests/behavioral tests/test_behavioral_fixtures.py skills/shanghai-high-school-study-coach
git commit -m "test: verify evidence-driven coaching behavior"
```

### Task 10: Final Installation, Verification, and Independent Review

**Files:**

- Modify only when a verification or review finding requires a tested fix.

- [ ] **Step 1: Verify source and installed Skill paths**

Run:

```bash
readlink /Users/zhangpeng/.codex/skills/shanghai-high-school-study-coach
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py /Users/zhangpeng/.codex/skills/shanghai-high-school-study-coach
```

Expected: symlink resolves to the repository Skill directory and both validators print `Skill is valid!`.

- [ ] **Step 2: Run the full verification matrix**

Run separately and inspect every exit code:

```bash
python3 -m unittest discover -s tests -v
git diff --check
git status --short
git ls-files student-workspaces
rg -n "上海市教育考试院|上海市教育委员会|shmeea|edu\.sh\.gov\.cn|考试政策|评分口径" skills/shanghai-high-school-study-coach
rg -n "TO[D]O|TB[D]|placeholder" skills/shanghai-high-school-study-coach tests
```

Expected: tests pass; diff check is clean; no tracked student workspace; policy scan and placeholder scan produce no matches. `git status --short` may show only intentional final-summary changes before their commit.

- [ ] **Step 3: Run adversarial manual probes**

In temporary fictional workspaces, rerun these concrete probes:

1. Replace each required child with a symlink and verify CLI rejection without traceback.
2. Replace the initializer temporary name during construction and verify no outside write.
3. Commit two sessions concurrently and verify both facts and state contributions remain.
4. Publish a completed session, inject state-replacement failure, retry, and verify exactly-once counts.
5. Attempt `transferable` with an empty student response, non-none hint, wrong subject, or missing explanation and verify rejection.

- [ ] **Step 4: Request independent spec and quality reviews**

Give reviewers only the confirmed redesign spec, the branch diff from `main`, and verification commands. Require findings first with file/line references. Fix every Important or Critical finding through a failing regression test, rerun affected tests, and request re-review. Ask the original whole-branch reviewer to verify that all four earlier Important findings and all three minor findings are closed.

- [ ] **Step 5: Rerun final forward cases after the last code change**

If review changes Skill behavior, rerun all twelve isolated cases, update `forward-test-summary.md` to the new final Skill commit, and rerun the full verification matrix.

- [ ] **Step 6: Commit final verified artifacts**

```bash
git add tests/behavioral/forward-test-summary.md skills/shanghai-high-school-study-coach tests .gitignore
git commit -m "test: finalize study coach redesign verification"
```

Do not create an empty commit. If there are no final artifact changes, retain the existing final implementation commit and report the verified hash.

## Spec Coverage Self-Review

- Core goal and six-subject architecture: Tasks 1 and 8.
- Hybrid fixed-module/dynamic-unit classification: Task 8.
- Content and error-pattern state models: Tasks 2 and 3.
- Real-student-response evidence only: Tasks 2, 3, 8, and 9.
- Guided and direct-detailed-answer paths: Tasks 8 and 9.
- Immediate reinforcement, variation, and delayed retest: Tasks 3, 8, and 9.
- Priority planning: Tasks 3, 7, 8, and 9.
- Immutable facts, revision chains, and derived state: Tasks 2, 3, 4, and 6.
- Symlink and concurrent-write safety: Tasks 4, 5, 6, and 10.
- Policy removal: Tasks 1, 8, 9, and 10.
- Privacy, temporary sessions, and no real data: Tasks 4, 5, 8, 9, and 10.
- Automated, baseline, forward, and independent review: Tasks 9 and 10.
