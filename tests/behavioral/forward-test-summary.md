# 隔离前向测试摘要

- 历史模型评估日期：2026-08-11
- 历史 12 案例测试提交：`d9910849063b7c8ae80f43867d8d9318b41b778f`
- 无 Skill 早期基线：9/12 完整满足，3/12 部分满足
- 历史启用 Skill 结果：12/12 通过，仅适用于上述提交与当时的案例版本。
- 当前完整模型评估日期：2026-09-17；当前目录共 14 个案例，14/14 通过。
- 最终证据：`skills/shanghai-high-school-study-coach-workspace/iteration-3/full-14-case-run-2`。
- 最终 run 的 executor 与隔离 grader 均正常完成，152/152 项判据通过；全部实际可见回复已经人工复核。
- `cases.json` SHA-256：`8b1add90977407206dd58eeb9b01d364f59fb98d00f89d5e806b6a79102838f0`；`SKILL.md` SHA-256：`2731c1f3eafc2879956865841e482a3069ee4ec4efbfa3cb54efc29fc4698a49`。

## 基线观察

每个基线案例使用全新隔离线程，只提供单个原始请求和必要的虚构材料，明确禁止读取
Skill、测试判据、仓库计划和其他代理输出。通用模型已经能完整处理数学分层提示、英语
订正、四个人文学科材料边界、单次错误待确认、多弱点排序和不可读输入等 9 个案例。
该基线来自扩展六学科完整表现链之前的同 ID 案例，本轮没有重跑无 Skill 基线，因此只作
历史增量参考，不作为与本轮扩展请求的直接横向对比。

3 个部分满足案例暴露了本 Skill 的主要增量：

- 直接解析基线：给出方法、推导、验算和理解检查，但没有明确列出易错点。
- 强化与延迟复测基线：给出三阶段流程，但没有使用
  `strengthening`、`provisionally_mastered`、`stable` 的规范状态和提示证据边界。
- 无表现证据基线：拒绝更新为 `stable`，但没有明确说明教师讲解本身也不是
  学生表现证据。

## 当前完整 14 案例结果

| case_id | must 全部满足 | must_not 全部避免 | 状态 | 观察 |
| --- | --- | --- | --- | --- |
| math-guided-diagnosis | 是 | 是 | PASS | 保留 `x=2` 和顶点横坐标 `1`，定位漏根与顶点纵坐标符号错误并分层提示；变式改变条件且不含答案，单次错误仍待确认。 |
| math-direct-explanation | 是 | 是 | PASS | 说明因式分解的选择理由，给出完整推导、零乘积性质、逐根验算和符号易错点；理解检查不含答案。 |
| english-writing | 是 | 是 | PASS | 保留原意并修正过去时及连接词；表现链依次达到 `suspected_gap`、`confirmed_gap`、`strengthening`、`provisionally_mastered`、`stable`，只给一道练习且未追溯升级。 |
| chinese-text-evidence | 是 | 是 | PASS | 引用前后态度变化并区分文本事实、可辩护解释和无依据断言；完整表现链最高到 `stable`，明确拒绝把此前变式追认为 `transferable`。 |
| politics-material-link | 是 | 是 | PASS | 用公开议事规则和按反馈调整开放时间连接协商民主与治理效果；完整表现链最高到 `stable`，未外查或补写事实。 |
| history-source-limits | 是 | 是 | PASS | 分开说明统计与私人日记的直接声称、可作推断和来源局限；完整表现链最高到 `stable`，未把个人材料当作社会共识。 |
| geography-fact-versus-inference | 是 | 是 | PASS | 区分温度观测、绿地机制与因果证据边界；完整表现链最高到 `stable`，未断言绿地是唯一原因或追溯升级。 |
| single-error-needs-confirmation | 是 | 是 | PASS | A 标为 `suspected_gap` 与 `observed_once`；B 保留既有 `stable`，两者都要求后续最小诊断。 |
| reinforcement-and-delayed-retest | 是 | 是 | PASS | 同类订正只支持 `strengthening`，当场无提示变式支持 `provisionally_mastered`，延迟无提示复测支持 `stable`；不追溯为迁移。 |
| multi-weakness-priority | 是 | 是 | PASS | 以已确认的函数定义域为主薄弱点，只条件性补一个前置，纳入重复审题模式和到期语文复测，英语单次错误保持待确认。 |
| unreadable-input | 是 | 是 | PASS | 同时暂停答案、估分、错因诊断和持久化，并请求清晰题干、公式、作答和评分材料；未猜测不可读内容。 |
| no-evidence-no-mastery | 是 | 是 | PASS | 拒绝更新为 `stable`，明确讲解和“懂了”都不是学生表现证据，要求延迟无提示独立复测。 |
| ordinary-question-first | 是 | 是 | PASS | 对清晰标出的零乘积步骤直接解释当前问题；未盘问模式、宣布薄弱点、公开后台观察或追加练习。 |
| repeated-observation-validation | 是 | 是 | PASS | 首条消息只纠正并解释当前句子，不提上周、历史、重复、记忆或薄弱点；答案后只加入一个含关联空格的新语境填空。 |

## 2026-09-17 完整重跑与修复

新增 `tests/behavioral/run_behavioral_eval.py`，以独立 `codex exec --ephemeral` 会话运行每个案例，执行模型只看到 `$shanghai-high-school-study-coach`、当前学生请求和必要虚构材料，不看到 `must`/`must_not`。每个案例随后由独立、schema 约束的 grader 检查全部学生可见消息；runner 保存执行 JSONL、stderr、可见消息、最终回复、grader 原文、逐项结果和 Skill/案例/材料哈希，并对 executor 与 grader 设置 600 秒超时。

首轮 `iteration-3/full-14-case-run-1` 为 9/14 案例、142/150 判据通过，保留为反例。它发现：政治材料题遗漏“材料—概念连接”内容状态、不可读输入没有明确暂停错因判断、讲解后只说“懂了”时没有同时排除教练讲解、普通问题案例本身缺少可回答步骤且错误要求可见回复暴露后台观察，以及 runner 在读取 Skill 前可能先发进度消息并泄露历史。

修复包括：用运行时 `$shanghai-high-school-study-coach` 预加载主 Skill；把普通问题案例改为含清晰零乘积步骤的可回答场景，并移除可见观察要求；明确政治材料连接是独立内容目标；要求不可读材料成组暂停四项动作；要求同时排除讲解和“懂了”两种伪证据。5 个失败场景在 `iteration-3/remediation-targeted-run-1` 中 5/5、45/45 通过。

随后从全新目录运行完整 `iteration-3/full-14-case-run-2`。结果为 14/14 案例、152/152 判据通过；人工逐条检查了 14 组 `visible-messages.json`。PDF/SVG 只在尚未读清材料时使用一句辨认进度；文本直答直接进入答案。六科证据链均区分内容与执行模式并止于 `stable`，不可读输入未猜测，普通日常问题没有流程打断，重复观察场景没有向学生暴露任何历史判断。

## 跨会话专项评测

2026-09-16 使用当时版本的 `evals/cross-session-memory.json` 对当时的未提交版本进行了三轮独立真实模型专项评测，产物分别保存在 `iteration-2/final-coach-run-1`、`final-coach-run-2` 和 `final-coach-run-3`。三轮自动检查和隔离 grader 均判 PASS，但独立人工复核判定不合格：有历史第二轮都只把刚讲过的两条射线换成新字母，再要求写出角名，没有加入候选角、干扰线或新的信息结构，实际测试的是符号复述而不是从新情境中选角。这三轮保留为反例，不计入最终通过次数；它们的有历史分支只有两个阶段，且报告只记录四项 source hash，不能证明当前第三阶段或完整 Skill tree 的行为。

加入 `third-existing-pending` 和完整 Skill-tree 指纹后，沙箱内的 `iteration-2/final-coach-v2-run-1` 因嵌套 Codex app-server 被拒绝而失败，属于基础设施失败，不计入模型行为结果。随后 `final-coach-v3-run-1`、`final-coach-v3-run-2` 通过；`final-coach-v3-run-3` 的回复、观察计数和“不重复检查”行为均符合设计，但当时 runner 在分号处分割首句，导致 grader 只评价分号前的半句并判 FAIL。该目录保留为评测器边界缺陷的回归证据，不计入最终三轮。

修正后的 runner 将包含分号分句的完整第一句作为一个单元，同时仍禁止用后续句子补救错误开头；该行为先由失败测试复现，再由回归测试锁定。使用修正后的相同源码在 `iteration-2/final-coach-v4-run-1`、`final-coach-v4-run-2` 和 `final-coach-v4-run-3` 完成三轮独立真实模型专项评测。每轮均有 2 个 case、4 个 stage，76/76 项自动检查和 25/25 项 grader expectation 通过；人工及无历史独立复核均判通过。三轮有历史分支依次为 observation/pending `1/0 -> 2/1 -> 3/1`，空历史对照为 `1/0`。第二阶段分别使用三个候选角或辅助线形成真实辨认任务，答案未提前出现；第三阶段和空历史对照均未追加检查，也未向学生暴露历史观察、记忆、诊断或薄弱点判断。

三轮 `source_sha256` 的 21 项完全一致，并与专项执行时的文件重算值一致：manifest 为 `0a0a2de13907f42d5bf919fc621ad7af45e093bc0f507e80e34721b080af6a8c`，runner 为 `6bbb20f193ff9b1285921bfe4af65f7325f38c9b8b8a50fb5c0780bb130ef73b`，当时的 `SKILL.md` 为 `c0e60579ab23bd00c30ede67f9febc41afeabe24f9eb9bb41bbd26ffda037f1b`；其余 18 项覆盖当时 Skill 树全部非缓存常规文件。Task 8 后续修复把当前 `SKILL.md` 更新为 `2731c1f3eafc2879956865841e482a3069ee4ec4efbfa3cb54efc29fc4698a49`，因此三轮专项不是当前 Skill 的字节级重跑；当前源码一致性由 `full-14-case-run-2/source/sha256.json` 证明。执行后的私有工作区按设计销毁，因此跨会话事后取证依赖旧哈希所对应 runner 保存的净化摘要与检查结果。

这项专项只覆盖文本数学“二面角平面角识别”、跨会话 `1->2` 首次验证、`2->3` 不重复验证、空历史对照、观察持久化和指定 canary 的隐私检查。它不覆盖图片/PDF、普通词汇问答、其余五科、无 ID 零写入、首次启用告知、学生回答小检查后的正式 evidence、观察精确关闭或完整故障路径；也没有指纹化 Codex/模型版本、推理配置和执行器用户配置。完整 14 案例重跑已补充 PDF、SVG、六科复盘、普通数学问答、不可读输入和英语重复观察等行为覆盖，但固定 prompt 中的历史记录是给定上下文，不等同于再次证明真实本地跨会话持久化。两组评测互补，不能互相替代；它们也对应不同的 `SKILL.md` 哈希。

## 隔离与清理

当前 14 个启用 Skill 案例均使用全新隔离会话；执行模型只看到原始请求、必要虚构材料和使用 `$shanghai-high-school-study-coach` 的指令，未看到 `must`、`must_not`、设计规格、基线输出或其他案例输出。执行沙箱为只读，案例未创建学生工作区或持久化记录。所有请求与材料均为虚构内容，未使用真实学生信息；评测只在 `skills/shanghai-high-school-study-coach-workspace/iteration-3/` 保存模型与 grader 证据。
