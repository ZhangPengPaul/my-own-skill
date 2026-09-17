# 日常互动观察记忆最终审查

日期：2026-09-16；更新：2026-09-17

## 审查结论

本轮实现已达到既定的“日常陪伴型教练”目标，可以在当前专项覆盖范围内验收。学生可以直接问问题、问知识点或继续追问；教练先解决眼前问题，在后台只保存低强度结构化观察。只有本轮新观察让同一行为线索首次从一个互动变为两个互动，才顺手加入一个最小检查；已经存在待验证组时，后续普通互动不会再次主动追问。单次提问和重复观察都不会直接改变正式掌握状态。

这不是仅修改 `SKILL.md` 的提示词方案。实现包含 observation 事实层、事务写入与校验、跨会话汇总、身份门禁、删除与迁移、行为评测 runner、隔离 grader 和回归测试。正式状态仍只接受真实学生表现形成的 session evidence，日常观察与正式诊断保持分离。

综合 2026-09-16 的文本数学跨会话专项和 2026-09-17 的完整 14 案例回归，本实施计划的必做验收项已经完成。当前源码对应的 14 案例证据覆盖 PDF、SVG、六科材料处理、普通数学问答、不可读输入和英语重复观察场景；跨会话专项证明 observation 的真实本地写入及 `1 -> 2 -> 3` 边沿行为。两组评测覆盖范围和源码版本不同，具体边界见下文，不能互相替代。

## 教练目标核对

| 目标 | 当前行为 | 结论 |
| --- | --- | --- |
| 日常使用不被流程打断 | 直接回答当前问题；只有任务性质不清或显式进入批改、复盘、计划时才确认模式 | 符合 |
| 潜移默化积累线索 | 清晰、可复用的提问或表现写为 `weak` observation；不保存完整题目、原回答或媒体 | 符合 |
| 跨时间识别重复 | 以宿主提供的稳定不透明 student ID 定位本地工作区，按五字段和不同 `interaction_id` 聚合 | 符合 |
| 不凭一次互动下结论 | 单次 observation 只表示未确认线索，不宣布薄弱点，也不更新正式状态 | 符合 |
| 重复后自然检查 | 只在本轮首次 `1 -> 2` 时加入一个与共同表现匹配的最小任务 | 符合 |
| 检查不是机械复述 | 候选识别须有多个候选或干扰项；计算和语言任务须改变数值、条件或语境，并把答案留给学生 | 符合 |
| 不反复追问 | `2 -> 3` 仍保留一个 pending group，但不再次追加检查 | 符合 |
| 观察和掌握证据分离 | 只有合格 session evidence 能更新正式状态并精确关闭更早 observation | 符合 |
| 不暴露后台判断 | 学生可见回复不提历史观察、重复、记忆、诊断、内部标签或薄弱点判断 | 符合 |

## 真实模型专项证据

最终采纳的三轮证据位于：

- `skills/shanghai-high-school-study-coach-workspace/iteration-2/final-coach-v4-run-1`
- `skills/shanghai-high-school-study-coach-workspace/iteration-2/final-coach-v4-run-2`
- `skills/shanghai-high-school-study-coach-workspace/iteration-2/final-coach-v4-run-3`

三轮均使用独立临时工作区和独立 `codex exec --ephemeral` 阶段。每轮结果相同：

| 项目 | 每轮结果 |
| --- | --- |
| case / stage | 2 / 4，全部 `passed` |
| 自动检查 | 76/76 通过 |
| grader expectation | 25/25 通过 |
| first | observation/pending `1/0`，先回答，无检查 |
| second | `2/1`，恰好一个候选辨认检查，答案未提前出现 |
| third | `3/1`，正确回答，无再次检查 |
| empty-history control | `1/0`，正确回答，无检查 |

三轮第二阶段分别要求从以下候选中重新选择：

- run 1：`∠AOB / ∠BOC / ∠COD`，正确目标为 `∠COD`。
- run 2：`∠AOB / ∠AOD / ∠COD`，正确目标为 `∠AOD`。
- run 3：`∠MON / ∠MOP / ∠NOP`，其中 `OP` 是干扰线，正确目标为 `∠MON`。

三个正确答案在对应题目前的可见消息中均未出现。run 1 和 run 2 明确给出目标区域的边界射线，因此它们验证的是最低限度的候选角辨认，而不是更复杂的空间迁移；这符合当前设计中“多个候选或干扰项”的门槛，但不应被扩展解释为图形迁移能力证据。

三轮 `source_sha256` 的 21 项完全一致，并与 2026-09-16 专项验收时的文件重算结果一致：

- manifest：`0a0a2de13907f42d5bf919fc621ad7af45e093bc0f507e80e34721b080af6a8c`
- runner：`6bbb20f193ff9b1285921bfe4af65f7325f38c9b8b8a50fb5c0780bb130ef73b`
- `SKILL.md`：`c0e60579ab23bd00c30ede67f9febc41afeabe24f9eb9bb41bbd26ffda037f1b`
- 其余 18 项覆盖当时 Skill 树全部非缓存、非符号链接常规文件；当时 Skill 树共有 19 个此类文件。

Task 8 的后续修复将 `SKILL.md` 更新为 `2731c1f3eafc2879956865841e482a3069ee4ec4efbfa3cb54efc29fc4698a49`，因此上述三轮不是当前 `SKILL.md` 字节级一致的跨会话重跑。专项 manifest 和 runner 的当前哈希仍与上述记录一致；当前 Skill 的精确源码一致性由下述完整 14 案例 run 2 证明。

一个不继承本轮分析结论的独立审阅代理重新检查了三份 report、12 组阶段产物、可见消息、artifact summary、grader 结果和源码指纹。它未发现影响通过判定的问题，并明确复核了答案泄露、第三阶段重复追问、空历史对照、观察语义、状态不变和隐私 canary。

## 评测器回归

旧 `final-coach-run-1/2/3` 的第二阶段只替换点和射线名称，属于机械转写；这些目录保留为反例，不计入最终通过次数。`final-coach-v2-run-1` 因外层沙箱拒绝嵌套 app-server 而失败，属于基础设施失败。

`final-coach-v3-run-1/2` 通过，`final-coach-v3-run-3` 的教练行为、观察计数和第三阶段不重复检查均符合设计，但旧 runner 会在分号处分割第一句，grader 因而只评价分号前的半句并判 FAIL。修复采用测试先行：新增测试先复现 payload 只保留分号前内容，再将 opening boundary 改为完整第一句；分号分句作为同一句整体，真正的后续句子仍不能补救错误开头。runner 的 30 项聚焦测试随后全部通过。由于 runner 和 manifest 哈希发生变化，最终验收重新执行了上述三轮 `v4`，没有沿用旧结果充数。

## 完整 14 案例证据

当前源码的最终证据位于 `skills/shanghai-high-school-study-coach-workspace/iteration-3/full-14-case-run-2`。完整回归结果为 14/14 案例通过、152/152 项隔离 grader 判据通过，executor 与 grader 全部退出 0；14 组 `visible-messages.json` 均已人工复核。对应哈希为：

- `cases.json`：`8b1add90977407206dd58eeb9b01d364f59fb98d00f89d5e806b6a79102838f0`
- `SKILL.md`：`2731c1f3eafc2879956865841e482a3069ee4ec4efbfa3cb54efc29fc4698a49`
- runner：`7f0344d287c60aa9aeec345df400629f72cdddeaf4e70c191430e3f848abb630`

首轮完整回归为 9/14、142/150，暴露并修复了政治内容目标、不可读输入、伪掌握证据、普通问题夹具和 Skill 加载时序共五类问题。5 个失败案例的定向回归为 5/5、45/45；最终 run 2 从头重跑全部 14 个案例，没有用定向结果替代完整结果。逐项结果、人工复核和覆盖边界见[完整 14 案例行为验收](./2026-09-17-complete-14-case-behavioral-review.md)。

## 自动验证

最终验证命令包括：

```text
python3 -m unittest discover -q
python3 <skill-creator>/scripts/quick_validate.py skills/shanghai-high-school-study-coach
env PYTHONPYCACHEPREFIX=/private/tmp/shanghai-coach-pycache python3 -m compileall -q skills/shanghai-high-school-study-coach tests/behavioral/run_cross_session_eval.py tests/behavioral/run_behavioral_eval.py
git diff --check
```

全量单元测试为 314 项；Skill 结构校验、Python 字节码编译和差异空白检查均通过。未使用默认 macOS 字节码缓存路径，因为沙箱不允许写入工作区外的 `~/Library/Caches`；改用 `/private/tmp` 后编译通过。

## 证据边界

跨会话专项证明的范围是：

- 文本数学中的二面角平面角识别；
- 两次不同互动形成的 `1 -> 2` 首次自然检查；
- 已有 pending group 的 `2 -> 3` 不重复检查；
- 空历史对照不误触发检查；
- observation 持久化、计数、正式状态不变和指定原文 canary 未落盘；
- 学生可见回复不暴露历史、记忆或诊断过程。

当前源码的完整 14 案例回归另外证明：

- PDF 和 SVG 材料可按清晰度边界处理；
- 语文、数学、英语、政治、历史、地理的当前答疑或复盘行为符合案例契约；
- 普通数学提问优先解决当前问题，不启动流程或公开后台观察；
- 英语重复观察场景先回答，再自然加入一个最小检查，不暴露历史判断；
- 不可读输入暂停作答、评分、错因判断和持久化。

两组真实模型评测合并后仍未覆盖一般英文单词释义、真实位图附件、六学科真实跨会话观察组合、学生完成最小检查后生成正式 evidence，以及完整模型故障路径。无持久化 ID 零写入、首次启用告知、observation 精确关闭和删除等存储与身份不变量已有 Python 测试，但不能用单元测试替代尚未执行的真实模型场景。跨会话专项使用 Task 8 修复前的 `SKILL.md`；当前源码的跨会话机制继续由相同 runner/manifest 的回归测试和存储 E2E 覆盖，但没有在 Task 8 修复后重新执行三轮真实模型专项。

## 残余风险

- 跨会话 runner 的 executor 和 grader subprocess 尚无显式超时；模型进程异常挂起时需要人工终止。新增的完整 14 案例 runner 已对两类进程设置 600 秒超时。
- POSIX 没有“仅当 inode 仍匹配时原子 unlink”的标准接口。删除逻辑会在快照后和每次删除前复核 inode，但最终复核与 `unlink` 之间仍有极短竞态窗口；安全性依赖私有工作区和协作写入者遵守锁。
- 评测后私有临时工作区按设计销毁，`workspace_archived=false`；事后取证依赖哈希对应的 runner、净化摘要和自动检查结果。
- 隐私 canary 能证明指定完整原文及其归一化或编码形式未落盘，不等同于任意局部摘录检测或通用 PII 扫描。
- 源码指纹不包含 Codex/模型版本、推理配置和 executor 用户配置；三轮证明源码输入一致，不证明完整运行环境可复现。
- run 1 的两个 grader 出现非阻塞模型列表刷新超时，run 3 control 的一次临时文件补丁被沙箱拒绝后成功恢复。相关阶段最终均退出 0，所有检查通过，但这些 stderr 仍应作为运行环境噪声保留。

## 计划状态

实施计划中的 Task 1 至 Task 9 功能交付均已完成，剩余必做实现任务为 0。计划文件仍有 8 个早期 RED 阶段记录未勾选：对应测试和实现均已存在且当前通过，但当时的失败输出没有归档，因此没有事后补写为已验证失败。一般英文单词释义、真实位图、当前源码的三轮跨会话真实模型重跑和学生回答最小检查后的正式 evidence 可作为后续扩展验证，不属于本轮计划的未完成项。
