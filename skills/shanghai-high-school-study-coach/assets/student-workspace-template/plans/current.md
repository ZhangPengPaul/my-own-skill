# 当前周计划

## 目标

## 计划项目

每个项目按以下字段记录：

- item_id:
- subject:
- task:
- estimated_effort:
- status: pending
- evidence:

`item_id` 必须唯一稳定，项目调整或重试时继续复用。只有存在完成证据时才能写
`status: completed`；否则保持未完成状态。重复 ID 或缺少完成证据的项目不计入完成数。
