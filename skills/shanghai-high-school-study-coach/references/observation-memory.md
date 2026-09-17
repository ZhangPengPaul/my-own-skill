# 日常互动观察写入参考

只在当前互动出现清晰、可复用的学习行为线索并且实际要写 observation 时读取本文件。没有持久化学生 ID 或没有有效线索时不要创建临时事实文件。

## Canonical observation

```json
{
  "schema_version": 1,
  "record_type": "interaction_observation",
  "record_id": "observation-20260916-001",
  "interaction_id": "interaction-20260916-001",
  "occurred_at": "2026-09-16T10:00:00+08:00",
  "subject": "english",
  "module_id": "vocabulary-and-grammar",
  "target_kind": "knowledge_unit",
  "target_id": "english.vocabulary-and-grammar.participial-adjectives",
  "target_name": "-ed 与 -ing 形容词辨析",
  "signal_kind": "adjective-form-selection",
  "signal": "描述个人感受时在 -ed 与 -ing 形式之间犹豫",
  "evidence_strength": "weak",
  "interaction_kind": "vocabulary_question",
  "student_action": "询问两个词形在句子中的区别",
  "uncertainty": "尚未看到学生独立选词"
}
```

允许值：

- `target_kind`：`knowledge_unit` 或 `pattern`。
- `interaction_kind`：`photo_question`、`knowledge_question`、`vocabulary_question`、`follow_up` 或 `other`。
- `evidence_strength`：schema 允许 `weak` 或 `repeated`。本 Skill 对每次日常互动的新观察一律写 `weak`，不要为了表达聚合结果而把第二条改成 `repeated`；两种值都不是正式掌握证据。

## 稳定标识与聚合

- 同一次学生互动产生的观察共用同一 `interaction_id`。一次互动里的追问、改口或幂等重试不换 ID，也不算第二次出现。
- 幂等重试复用同一 `record_id` 和完全相同的内容。新互动使用新的 `record_id` 和 `interaction_id`。
- `record_id` 和 `interaction_id` 必须匹配 `^[a-z0-9][a-z0-9-]{0,95}$`，只使用 ASCII 小写字母、数字和连字符。时间可写成 `observation-20260916-153403-001`；不要使用大写 `T`、冒号、下划线、小数点或时区符号。`occurred_at` 仍使用正常的带时区 ISO-8601 时间，不受这条 ID 格式限制。
- 只有真正相同的目标和行为线索才复用同一组 `subject`、`module_id`、`target_kind`、`target_id`、`signal_kind`，避免同一线索因标签漂移而无法聚合，也避免把不同问题硬合并。
- 无法可靠归一化目标时使用 `pending-normalization` 作为 `target_id`；这类观察不会进入重复线索聚合。
- 写入前保存 `python3 <skill-root>/scripts/summarize_progress.py <workspace> --student-id <student-id>` 的历史基线；写入后重新运行同一汇总，再比较前后结果。新汇总用于确定当前是否存在 pending validation，只有前后对比显示本轮匹配的五字段组首次从一个历史 `interaction_id` 变成两个不同 `interaction_id` 时，才触发一次低打扰验证；既有 pending 组不能仅凭写入后的汇总再次触发。

## 正式验证关闭观察

- 正式 session evidence 可选填 `resolves_observation_signal_kinds`，值为不重复的 `signal_kind` ASCII slug 列表。新证据只有在确实验证了相应行为线索时才列出该 slug。
- 字段缺失或列表为空时不关闭任何观察。旧 schema v2 evidence 无须补写该字段。
- 只有 `diagnostic`、`variant`、`delayed_retest` 或 `transfer` evidence 会关闭更早且 `subject`、`module_id`、`target_kind`、`target_id`、`signal_kind` 全部匹配的观察。同一目标下未列出的其他 `signal_kind` 保持未解决。
- `initial_attempt` 和 `correction` 即使带有该列表也不关闭观察。

## 内容与格式限制

- `target_name` 最长 120 字符，`signal` 和 `uncertainty` 最长 240 字符，`student_action` 最长 160 字符；不得含首尾空白或 Unicode 控制字符，`uncertainty` 也可以为 `null`。
- `signal_kind` 必须是最长 64 字符的 ASCII 小写 slug，可使用数字、连字符和下划线。
- `target_id` 必须是以学科开头的 dotted slug，例如 `english.vocabulary.word-class`，或使用 `pending-normalization`。
- canonical JSON 的 UTF-8 编码不得超过 4 KiB。
- 只写概括后的行为摘要。不得写完整题目、原始回答、大段连续文本、图片、PDF、data URI、base64 或 hex 媒体载荷。
- 如果提问本身是唯一可观察行为，`student_action` 只概括学生询问了什么判断或知识，`uncertainty` 明确尚未观察到独立表现；不得写成学生已经尝试或答错。

## 事务写入

在 workspace 外创建临时 JSON，提交后删除临时文件：

```text
python3 <skill-root>/scripts/commit_learning_state.py <workspace> --fact-file <json-file> --student-id <student-id>
python3 <skill-root>/scripts/validate_student_data.py <workspace> --student-id <student-id>
python3 <skill-root>/scripts/summarize_progress.py <workspace> --student-id <student-id>
```

任何校验、提交或复查失败都停止后续持久化并报告错误；不要直接编辑 workspace 内的 observation 文件或 `state.json`。
