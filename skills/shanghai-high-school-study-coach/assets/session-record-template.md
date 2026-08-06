# 学习会话记录

- session_id:
- status: incomplete
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
创建时分配唯一稳定的 `session_id`；中断重试必须复用该 ID，不创建重复记录。
仅在记录完整且成功落盘后，才通过同目录唯一临时文件和原子替换将
`status: completed` 写入会话记录。`status: incomplete` 的记录不计入完成会话。
