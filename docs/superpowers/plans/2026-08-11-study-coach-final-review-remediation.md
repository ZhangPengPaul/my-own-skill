# Study Coach Final Review Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every confirmed Critical and Important finding from the final independent specification review while preserving descriptor-safe workspaces and immutable evidence.

**Architecture:** Keep immutable session and plan facts as the only source of truth. Publish facts from complete temporary files, validate a stricter schema at ingress, reduce full evidence history through explicit state transitions, reject inconsistent plan completion, and render evidence references from the validated snapshot. Keep the existing single transactional writer and schema version 2 because this branch has no released real-data migration surface.

**Tech Stack:** Python 3.9 standard library, `unittest`, Markdown Skill contracts, JSON facts, POSIX directory descriptors and advisory locking.

---

## File Responsibility Map

- `scripts/commit_learning_state.py`: temporary fact creation, atomic no-clobber publication, global record-ID conflict checks, locked reconciliation.
- `scripts/learning_state.py`: fixed-module/schema validation, global fact identity, revision selection, evidence-history reduction, plan-completion validation.
- `scripts/summarize_progress.py`: render evidence IDs from a previously validated snapshot.
- `SKILL.md`: complete priority factors, override order, and bounded plan shape.
- `tests/workspace_fixtures.py`: canonical schema-v2 task and mode-transition fixture fields.
- `tests/test_learning_state.py`: schema, transition, metadata, ID, and plan-completion regressions.
- `tests/test_commit_learning_state.py`: interrupted publication and cross-directory conflict regressions.
- `tests/test_summarize_progress.py`: evidence-reference rendering regressions.
- `tests/test_skill_contract.py`: priority protocol contract.
- `tests/behavioral/forward-test-summary.md`: refreshed isolated results tied to the final behavior commit.

### Task 1: Publish Complete Facts Atomically and Enforce Global Record IDs

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/commit_learning_state.py`
- Modify: `skills/shanghai-high-school-study-coach/scripts/learning_state.py`
- Modify: `tests/test_commit_learning_state.py`
- Modify: `tests/test_learning_state.py`

- [ ] **Step 1: Add failing atomic-publication and global-ID tests**

Add `test_interrupted_fact_write_never_exposes_final_name` to mock `_write_all`, assert the final
`<record_id>.json` is absent while bytes are written to a hidden unique temporary name, inject an
`OSError`, and assert both final and temporary names are absent afterward.

Add `test_cross_type_record_id_is_rejected` to call:

```python
with self.assertRaisesRegex(ValidationError, "record_id"):
    reconcile_state(
        "student-a",
        [session_fact(record_id="record-shared")],
        [plan_fact(record_id="record-shared")],
        now=NOW,
    )
```

Add a commit-level version that first commits a session, attempts a plan with the same `record_id`,
then asserts the plan directory and state are unchanged.

- [ ] **Step 2: Run the new tests and observe RED**

Run:

```bash
python3 -m unittest \
  tests.test_commit_learning_state.CommitLearningStateTest.test_interrupted_fact_write_never_exposes_final_name \
  tests.test_commit_learning_state.CommitLearningStateTest.test_cross_type_record_id_conflict_preserves_workspace \
  tests.test_learning_state.ReconciliationTest.test_cross_type_record_id_is_rejected -v
```

Expected: FAIL because the final fact name exists during `_write_all`, and session/plan IDs are only
checked inside separate collections.

- [ ] **Step 3: Implement complete temporary publication and global identity validation**

Change `_publish_fact_no_clobber` to:

1. Create `.<record-id>-<uuid>.tmp` relative to the held fact-directory descriptor with
   `O_CREAT | O_EXCL | O_NOFOLLOW`.
2. Write canonical JSON, `fsync`, and close the temporary descriptor.
3. Atomically create the final name without overwrite by linking the complete temporary inode to
   `<record-id>.json` in the same directory; `FileExistsError` enters the existing byte-for-byte
   idempotency/conflict branch.
4. `fsync` the directory, unlink the owned temporary name, and `fsync` again.
5. On every failure, close descriptors and remove only the owned temporary name. Never unlink an
   existing final fact.

At the start of `reconcile_state`, build one `record_id` set from `sessions + plan_items` and reject
any duplicate before selecting active revisions. In `commit_fact`, use the first locked snapshot to
reject a candidate whose `record_id` already exists in the other fact directory before publication.

- [ ] **Step 4: Run focused and integration tests**

Run:

```bash
python3 -m unittest tests.test_commit_learning_state tests.test_learning_state tests.test_validate_student_data -v
```

Expected: PASS. Existing identical retries remain no-op, conflicting same-type reuse remains an
error, and state-replacement retry still derives exactly one recorded session.

- [ ] **Step 5: Commit Task 1**

```bash
git add skills/shanghai-high-school-study-coach/scripts/commit_learning_state.py \
  skills/shanghai-high-school-study-coach/scripts/learning_state.py \
  tests/test_commit_learning_state.py tests/test_learning_state.py
git commit -m "fix: publish complete learning facts atomically"
```

### Task 2: Validate Complete Evidence and Reduce State from History

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/learning_state.py`
- Modify: `tests/workspace_fixtures.py`
- Modify: `tests/test_learning_state.py`
- Modify: tests that construct session facts through the shared fixture only if their assertions change.

- [ ] **Step 1: Add failing schema and identity tests**

Extend the canonical session fixture with:

```python
"task_id": "task-001",
"mode_transitions": [],
```

Add tests that require:

- nonempty valid `task_id`;
- each mode transition has exactly `from_mode`, `to_mode`, and nonempty `reason`, uses defined task
  modes, and changes the mode;
- completed sessions with observations have at least one nonempty source description and a nonempty
  `student_attempt`;
- `student_explanation` and `uncertainty` are null or nonempty strings;
- `next_review_at` is null or an ISO-8601 timestamp;
- every observation module belongs to the fixed module set for its subject;
- a target's canonical name and module cannot change across active evidence; aliases are merged as a
  sorted union instead of overwritten;
- duplicate `session_id` values across unrelated revision roots are rejected.

Use the exact fixed modules already asserted in `tests/test_reference_contracts.py`. Change the
pattern fixture module from generic `reasoning` to the subject module `geometry`.

- [ ] **Step 2: Add failing transition and plan-completion tests**

Replace the old mismatched-plan test with rejection assertions. Add exact regressions:

```python
def test_single_diagnostic_error_remains_suspected(self): ...
def test_second_matching_error_confirms_gap(self): ...
def test_initial_or_diagnostic_success_does_not_claim_provisional_mastery(self): ...
def test_successful_variant_requires_prior_gap_or_strengthening(self): ...
def test_successful_variant_does_not_lower_stable(self): ...
def test_delayed_retest_requires_prior_provisional_mastery(self): ...
def test_transfer_requires_prior_stable_state(self): ...
def test_completed_plan_rejects_missing_or_mismatched_evidence(self): ...
```

The state path must follow these evidence rules:

- first incorrect content evidence -> `suspected_gap`;
- a later incorrect diagnostic/correction/variant for the same target, or a new diagnostic failure
  that conflicts with an existing provisional/stable/transferable state -> `confirmed_gap`;
- correction or any hinted correct response -> at most `strengthening` and never lowers a higher
  non-conflicting state;
- an unhinted correct `variant` after a documented gap/strengthening state ->
  `provisionally_mastered`;
- an unhinted correct `delayed_retest` after provisional mastery -> `stable`;
- an unhinted correct `transfer` with explanation after stable -> `transferable`;
- correct evidence never lowers state; incorrect conflicting evidence may lower it.

- [ ] **Step 3: Run the new tests and observe RED**

Run:

```bash
python3 -m unittest tests.test_learning_state -v
```

Expected: FAIL on missing schema fields, accepted invalid metadata, single-observation upgrades,
successful-state downgrade, and silently ignored invalid plan completion.

- [ ] **Step 4: Implement strict schema and history reduction**

Add `SUBJECT_MODULES`, `_validate_mode_transition`, and optional-string validation helpers.
Validate all new fields and evidence metadata before reconciliation. In `reconcile_state`:

1. Sort active completed sessions as today.
2. Maintain one target object and an explicit current status per target.
3. Require stable name/module identity and union aliases.
4. Pass current status and prior evidence history to a transition reducer rather than mapping the
   newest observation in isolation.
5. Require completed plan evidence to exist and match subject, target kind, and target ID; raise
   `ValidationError` on any mismatch.

Keep `evidence_ids`, last evidence time, next review time, deterministic ordering, idempotent
`updated_at`, and pattern-state behavior intact.

- [ ] **Step 5: Run all schema consumers**

Run:

```bash
python3 -m unittest \
  tests.test_learning_state \
  tests.test_commit_learning_state \
  tests.test_validate_student_data \
  tests.test_init_student \
  tests.test_summarize_progress -v
```

Expected: PASS with no fixture-local duplicate schema definitions.

- [ ] **Step 6: Commit Task 2**

```bash
git add skills/shanghai-high-school-study-coach/scripts/learning_state.py \
  tests/workspace_fixtures.py tests/test_learning_state.py \
  tests/test_commit_learning_state.py tests/test_validate_student_data.py \
  tests/test_init_student.py tests/test_summarize_progress.py
git commit -m "fix: derive mastery from complete evidence history"
```

### Task 3: Expose Evidence in Summaries and Complete Priority Rules

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/summarize_progress.py`
- Modify: `skills/shanghai-high-school-study-coach/SKILL.md`
- Modify: `tests/test_summarize_progress.py`
- Modify: `tests/test_skill_contract.py`

- [ ] **Step 1: Add failing evidence-rendering and priority contracts**

Require every rendered knowledge unit and recurring/improving pattern to include the escaped,
comma-separated `evidence_ids` from the validated snapshot. The test must assert both target and
pattern evidence IDs, and ensure a control character in an evidence ID cannot create Markdown.

In the Skill contract, extract `优先级和学习计划` and require:

- teacher requirements and the student's current goal override automatic sorting;
- prerequisite impact, evidence strength, recurrence, current materials/teacher progress, due
  retests, and available time are all represented;
- each plan is bounded to one primary content gap, one necessary prerequisite, one recurring
  pattern, plus due retests.

- [ ] **Step 2: Run focused tests and observe RED**

Run:

```bash
python3 -m unittest \
  tests.test_summarize_progress.SummarizeProgressTest.test_reports_evidence_based_priorities \
  tests.test_skill_contract.SkillContractTest.test_priority_protocol_matches_confirmed_spec -v
```

Expected: FAIL because summaries omit evidence IDs and the Skill uses a shorter ordering rule.

- [ ] **Step 3: Implement minimal rendering and protocol changes**

Render each target as:

```text
- <name> [<state>; evidence: <id-1>, <id-2>]
```

Use the existing control-character escape function for names, state, and every evidence ID. Do not
reload fact files or state after `validate_workspace()`.

Rewrite only the `优先级和学习计划` section to state the confirmed override order, six automatic
factors, and four-part maximum plan shape. Retain the matching-evidence completion rule and no-score
policy.

- [ ] **Step 4: Run Skill and summary verification**

Run:

```bash
python3 -m unittest tests.test_summarize_progress tests.test_skill_contract -v
python3 /Users/zhangpeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/shanghai-high-school-study-coach
```

Expected: PASS and `Skill is valid!`.

- [ ] **Step 5: Commit Task 3**

```bash
git add skills/shanghai-high-school-study-coach/scripts/summarize_progress.py \
  skills/shanghai-high-school-study-coach/SKILL.md \
  tests/test_summarize_progress.py tests/test_skill_contract.py
git commit -m "fix: expose evidence and complete study priorities"
```

### Task 4: Final Forward Test, Matrix, and Re-Review

**Files:**
- Modify: `tests/behavioral/forward-test-summary.md`
- Modify only if a re-review finding requires a new failing regression.

- [ ] **Step 1: Run the full automated and safety matrix**

Run every Task 10 installation, `unittest`, diff, privacy, policy, placeholder, symlink, concurrent
commit, failed-state-retry, and invalid-transfer command from the parent redesign plan.

Expected: all automated tests pass; both Skill validators print `Skill is valid!`; scans are empty.

- [ ] **Step 2: Freeze the behavior commit and rerun isolated cases**

Confirm `git status --short` is empty, record `git rev-parse HEAD`, then run all 12 cases with a new
isolated agent per case. Give each agent only the raw request, fictional fixture, and instruction to
use `$shanghai-high-school-study-coach`; never provide `must`, `must_not`, prior output, review
findings, or expected diagnosis.

Update `forward-test-summary.md` with the full tested hash and any changed observations. If a case
fails, add a failing behavioral/contract test, make the minimum behavior fix, rerun focused tests,
commit, and repeat all 12 cases at the new clean hash.

- [ ] **Step 3: Request sequential independent reviews**

First request spec compliance against the confirmed redesign spec and branch diff. After it passes,
request code quality/security review. Give the closure reviewer the four original Important findings
and three original Minor findings verbatim and require explicit evidence that each is closed. Fix all
Critical/Important findings through TDD and re-review.

- [ ] **Step 4: Run final verification and commit evidence**

Run the complete matrix again after the last code or Skill change. If only the forward summary is
modified, commit:

```bash
git add tests/behavioral/forward-test-summary.md
git commit -m "test: finalize study coach redesign verification"
```

Do not create an empty commit. Do not push.
