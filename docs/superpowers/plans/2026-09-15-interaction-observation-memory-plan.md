# 日常互动观察记忆层实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为学习教练增加默认本地记录的结构化日常观察，并在本轮新观察使同类线索首次从一次变为两次互动时触发一次低打扰验证。

**Architecture:** 新增独立 `interaction_observation` 不可变事实层，与现有 session evidence 分离。观察只产生弱/重复线索；正式掌握状态仍只能由 session evidence 更新。

**Tech Stack:** Python 3 标准库、JSON 文件、文件描述符安全访问、现有 unittest 测试体系。

**Spec:** `docs/superpowers/specs/2026-09-15-interaction-observation-memory-design.md`

**完成状态（2026-09-17）：** Task 1 至 Task 9 的功能交付和最终验收均已完成，剩余必做实现任务为 0。计划仍保留 8 个未勾选的早期 RED 阶段执行记录：对应测试已经存在且当前通过，但当时“新测试先失败”的命令输出没有归档，不能事后补写为已验证失败。这 8 项是测试过程的审计留痕缺口，不代表缺少实现或当前回归覆盖。

## Global Constraints

- 只保存结构化观察摘要，不保存完整题目、原始回答、图片或 PDF。
- 观察不得直接改变正式掌握状态。
- 聚合在不同 `interaction_id` 的两次相似观察后升级为待验证线索；学生可见验证只在本轮完整五字段组首次从 1→2 时触发一次，已有 pending、本轮无新增匹配观察或字段不全同都不触发。
- 重复观察的最小共同表现只在后台用于选题；学生可见回复不提历史、重复事实、记忆、诊断过程、可能原因或薄弱点判断。
- 写入必须复用工作区锁、事务发布、幂等和校验流程。
- 默认使用持久化学生 ID 时启用本地观察记忆，并首次告知用户。
- 宿主为同一学生稳定注入不透明、非个人身份信息的学生 ID 和同一私有可写根目录；模型不向学生索要或猜测身份信息来生成 ID。
- 没有持久化学生 ID 或私有可写根目录时一律使用零写入临时会话，不能仅凭工作区路径绕过身份要求。
- 持久化 ID 必须解析到稳定根目录；失败时不得静默退回当前工作目录。所有持久化 CLI 都必须携带并校验匹配的 `--student-id`。
- 区分存储链路测试与真实模型行为评测，两者都通过后才宣称跨会话目标达成。
- 保持完整测试套件通过。

### Task 1: Observation schema and reconciliation

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/learning_state.py`
- Test: `tests/test_learning_state.py`

**Interfaces:**
- Add `validate_observation_fact(fact) -> None`.
- Add `aggregate_observations(observations) -> tuple` returning deterministic pending-validation summaries.
- Extend `validate_fact` to accept `record_type == "interaction_observation"`.

- [ ] Write failing tests for valid observation, forbidden raw-material fields, duplicate interaction exclusion, target mismatch exclusion, and two-interaction aggregation.
- [ ] Run `python3 -m unittest tests.test_learning_state -v` and verify the new tests fail.
- [x] Implement exact schema validation, strength rules, and deterministic aggregation.
- [x] Re-run the focused tests and then the full suite.

### Task 2: Workspace observation directory and validation

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/init_student.py`
- Modify: `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py`
- Modify: `tests/workspace_fixtures.py`
- Test: `tests/test_init_student.py`, `tests/test_validate_student_data.py`

**Interfaces:**
- Add `observations` to required workspace directories.
- Include validated observation facts in `WorkspaceSnapshot`.
- Create an empty observations directory for new and migrated workspaces.

- [ ] Add failing tests for directory creation, old-workspace migration, invalid observation filenames, symlinks, and malformed facts.
- [ ] Run focused tests and verify failure.
- [x] Implement descriptor-safe directory creation, reading, and snapshot validation.
- [x] Run focused and full suites.

### Task 3: Atomic observation commit

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/commit_learning_state.py`
- Test: `tests/test_commit_learning_state.py`

**Interfaces:**
- Route observation facts to `observations/`.
- Preserve cross-type `record_id` conflict checks and idempotent identical retry behavior.

- [ ] Add failing tests for publish, retry, conflict, concurrent commits, and failure isolation.
- [ ] Run focused tests and verify failure.
- [x] Implement routing using existing atomic publish primitives and workspace lock.
- [x] Run focused and full suites.

### Task 4: Observation summaries and deletion

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/summarize_progress.py`
- Create: `skills/shanghai-high-school-study-coach/scripts/delete_observations.py`
- Test: `tests/test_summarize_progress.py`, `tests/test_summarize_observations.py`, `tests/test_delete_observations.py`

**Interfaces:**
- Render deterministic unresolved singleton and pending-validation observations.
- Close an older observation only when later qualifying evidence names its `signal_kind` in `resolves_observation_signal_kinds` and the complete target matches, without mutating fact files.
- Add CLI `delete_observations.py <workspace> --student-id <student-id> [--subject] [--target-id] [--before]`.

- [x] Add failing tests for singleton/repeated rendering, formal-evidence closure, filters, deterministic ordering, and deletion followed by disappearance from summaries.
- [x] Run focused tests and verify failure.
- [x] Implement read-only summary integration, lifecycle closure, and descriptor-safe filtered deletion under lock.
- [x] Run focused and full suites.

### Task 5: Coach behavior contract

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/SKILL.md`
- Modify: `tests/test_skill_contract.py`
- Modify: `tests/behavioral/cases.json`

**Interfaces:**
- Document ordinary photo questions, knowledge questions, and vocabulary questions as natural-response interactions.
- Document observation creation, write-before/write-after summaries, the current-round 1→2 edge, implicit natural validation, exact formal-evidence closure, and first-use notice.

- [x] Add failing contract cases asserting current-question-first behavior, no immediate diagnosis from one interaction, and natural validation after repeated signals.
- [x] Run focused tests and verify failure.
- [x] Update the skill contract, operational observation reference, and behavioral fixtures with concrete examples.
- [x] Run full unittest suite and inspect generated behavioral summary.

### Task 6: Migration and end-to-end verification

**Files:**
- Modify: `tests/test_repository_privacy.py`
- Create: `tests/test_interaction_observation_e2e.py`

- [ ] Add failing end-to-end test covering initialize → commit two observations → summarize → create validation session → state update.
- [ ] Run the test and verify failure.
- [x] Implement only missing integration glue identified by the test.
- [x] Run `python3 -m unittest discover -v` and record all passing results.
- [x] Run static checks for forbidden raw-material fields and repository privacy.

### Task 7: Stable local root and idempotent workspace routing

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/scripts/init_student.py`
- Modify: `skills/shanghai-high-school-study-coach/scripts/validate_student_data.py`
- Modify: `skills/shanghai-high-school-study-coach/SKILL.md`
- Test: `tests/test_init_student.py`, `tests/test_validate_student_data.py`, `tests/test_skill_contract.py`

**Interfaces:**
- Add `init_student.py --ensure --report-status [--root <root>] <student-id>` while preserving the path-only form for compatibility.
- Root precedence is `--root`, `SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT`, then the per-user data directory.
- Print the canonical workspace path plus `created`/`migrated`/`existing` status as JSON and reuse the path for every later command; use status to make first-use notice deterministic.
- Require the same host-provided `--student-id` on commit, validation, summary, and deletion CLIs; reject missing or mismatched identity before returning or changing persistent data.

- [x] Add failing tests for precedence, default permissions, idempotence, concurrency, student-path symlinks, alias retargeting, disappearance after conflict, and invalid legacy migration.
- [x] Hold one resolved root descriptor across create/conflict recovery and reject identity changes.
- [x] Validate a legacy workspace and expected student ID before migration under the same exclusive lock.
- [x] Reject invalid IDs before opening the workspace; under the held lock, compare the `state.json` identity before reading any complete fact snapshot.
- [x] Route persistent IDs through `--ensure`; retain zero-write behavior whenever no persistent ID is present.
- [x] Run focused suites and the final full suite after all documentation and runner changes.

### Task 8: Implicit repeated-signal validation

**Files:**
- Modify: `skills/shanghai-high-school-study-coach/SKILL.md`
- Modify: `tests/behavioral/cases.json`
- Modify: `skills/shanghai-high-school-study-coach/evals/evals.json`
- Test: `tests/test_skill_contract.py`

- [x] Compare all member observations and use only their minimum common behavior for backend validation selection.
- [x] Keep student-facing replies implicit: answer first, then transition naturally to one small check without exposing history, repetition, memory, diagnosis, possible causes, or weakness judgments.
- [x] Limit normal follow-up to exactly one minimal task, with linked blanks or steps counting as one task.
- [x] Re-run the current `cases.json` complete 14-case behavioral evaluation and inspect actual replies; final evidence is `iteration-3/full-14-case-run-2` with 14/14 cases and 152/152 expectations passed, after preserving and remediating the 9/14 first run.

### Task 9: Repeatable cross-session model regression

**Files:**
- Create: `skills/shanghai-high-school-study-coach/evals/cross-session-memory.json`
- Create: `tests/behavioral/run_cross_session_eval.py`
- Create: `tests/test_cross_session_eval_runner.py`
- Extend: `tests/test_interaction_observation_e2e.py`

- [x] Add two-process Python E2E with separate working directories and a shared root/student ID.
- [x] Add a dry-run-by-default manifest runner using independent `codex exec --ephemeral` stages.
- [x] Add an empty-history control and persist raw JSONL, stderr, all visible messages, final message, sanitized artifact summaries, source/response hashes, exit codes, and report metadata.
- [x] Add an offline fake-Codex test for cwd/root isolation, prompt non-propagation, and failure-code handling.
- [x] Grade response behavior with an isolated schema-constrained model grader, and gate workspace counts, unresolved pending count, state bytes, material absence, and privacy canaries independently.
- [x] Add a third matching stage that requires count 3, one existing pending group, and no second validation; fingerprint the parsed manifest bytes, runner, and every non-cache regular file in the Skill tree.
- [x] Run the current manifest in at least three new directories and manually review every saved visible message, artifact summary, and `third-existing-pending` result against every expectation. Final accepted evidence is in `iteration-2/final-coach-v4-run-1`, `final-coach-v4-run-2`, and `final-coach-v4-run-3`; each run passed 76 automated checks and 25 grader expectations, and an independent no-history review found no blocking discrepancy.
- [x] Store new artifacts under `skills/shanghai-high-school-study-coach-workspace/iteration-2/`; do not overwrite iteration 1.

### Task 3 follow-up verification

- Fixed `commit_fact` so `interaction_observation` publication skips both state reconciliation passes.
- Observation commits still perform the final workspace consistency read, while leaving the existing `state.json` bytes untouched.
- Added a regression test that fails if observation commits call `reconcile_state`.
- Focused verification: 2 tests passed.
- Full verification: `python3 -m unittest discover -v` passed, 204 tests.
