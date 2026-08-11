# 隔离前向测试摘要

- 日期：2026-08-11
- 最终测试提交：`ae4f6c0494ec6a0863163620c11ca8dd796642dc`
- 无 Skill 基线：9/12 完整满足，3/12 部分满足
- 启用 Skill：12/12 通过

## 基线观察

每个基线案例使用全新隔离线程，只提供单个原始请求和必要的虚构材料，明确禁止读取
Skill、测试判据、仓库计划和其他代理输出。通用模型已经能完整处理数学分层提示、英语
订正、四个人文学科材料边界、单次错误待确认、多弱点排序和不可读输入等 9 个案例。

3 个部分满足案例暴露了本 Skill 的主要增量：

- `math-direct-explanation`：给出方法、推导、验算和理解检查，但没有明确列出易错点。
- `reinforcement-and-delayed-retest`：给出三阶段流程，但没有使用
  `strengthening`、`provisionally_mastered`、`stable` 的规范状态和提示证据边界。
- `no-evidence-no-mastery`：拒绝更新为 `stable`，但没有明确说明教师讲解本身也不是
  学生表现证据。

## 启用 Skill 的最终结果

| case_id | must 全部满足 | must_not 全部避免 | 状态 | 观察 |
| --- | --- | --- | --- | --- |
| math-guided-diagnosis | 是 | 是 | PASS | 保留两个正确中间结果，定位漏根和顶点纵坐标符号错误，按层提示；只给改变条件且不含答案的变式，并把单次错误保持为待确认。 |
| math-direct-explanation | 是 | 是 | PASS | 说明选择因式分解的理由，给出完整推导、零乘积性质、逐根验算和三类易错点；理解检查不含答案，也未更新掌握状态。 |
| english-writing | 是 | 是 | PASS | 将 `go` 改为过去式并处理 `although` 与 `but` 冲突，保留原意，只给一道针对性练习；未替换全文或虚构评分。 |
| chinese-text-evidence | 是 | 是 | PASS | 引用叙述者前后态度变化，说明旧相册连接家庭往事与人物交流，并把可辩护解释和无依据断言分开。 |
| politics-material-link | 是 | 是 | PASS | 用公开议事规则和按反馈调整开放时间连接协商民主及治理实效；未外查、堆砌概念或补写事实。 |
| history-source-limits | 是 | 是 | PASS | 分开说明统计与私人日记的直接声称、可作推断和局限，明确个人日记不能代表整个社会。 |
| geography-fact-versus-inference | 是 | 是 | PASS | 把夜间温差和局部降温列为观测，把绿地降温列为待验证机制，并明确相关性不能独立证明因果。 |
| single-error-needs-confirmation | 是 | 是 | PASS | 内容状态最多为 `suspected_gap`，执行模式为 `observed_once`；要求最小诊断后才决定是否升级。 |
| reinforcement-and-delayed-retest | 是 | 是 | PASS | 同类订正只支持 `strengthening`，当场无提示变式支持 `provisionally_mastered`，延迟无提示复测才支持 `stable`。 |
| multi-weakness-priority | 是 | 是 | PASS | 以已确认的函数定义域为主薄弱点，只条件性补一个前置，纳入重复审题模式和到期语文复测，英语单次错误保持待确认。 |
| unreadable-input | 是 | 是 | PASS | 同时暂停答案、估分、错因诊断和持久化，并请求清晰题干、公式、作答和评分材料；未猜测不可读内容。 |
| no-evidence-no-mastery | 是 | 是 | PASS | 拒绝更新为 `stable`，明确讲解和“懂了”都不是学生表现证据，要求延迟无提示独立复测。 |

## 隔离与清理

每个启用 Skill 的案例也使用全新隔离线程。执行代理只看到原始请求、必要的虚构材料
和使用 `$shanghai-high-school-study-coach` 的指令；未看到 `must`、`must_not`、案例目录、
设计规格、基线输出或其他代理输出。所有案例均为只读执行，没有创建学生工作区、临时
输出或持久化记录，因此没有遗留待删除的评估文件。测试未使用真实学生信息，仓库中未
保留学生工作区。
