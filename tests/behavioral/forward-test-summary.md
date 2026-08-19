# 隔离前向测试摘要

- 日期：2026-08-11
- 最终测试提交：`d9910849063b7c8ae80f43867d8d9318b41b778f`
- 无 Skill 早期基线：9/12 完整满足，3/12 部分满足
- 启用 Skill（本轮干净 HEAD 重跑）：12/12 通过

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

## 启用 Skill 的最终结果

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

## 隔离与清理

每个启用 Skill 的案例都在上述最终测试提交上使用全新隔离线程重跑。执行代理只看到原始请求、必要的虚构材料
和使用 `$shanghai-high-school-study-coach` 的指令；未看到 `must`、`must_not`、案例目录、
设计规格、基线输出或其他代理输出。所有案例均为只读执行，没有创建学生工作区、临时
输出或持久化记录，因此没有遗留待删除的评估文件。所有请求与材料均为虚构内容，未使用
真实学生信息；`git ls-files student-workspaces` 与本地工作区检查均为空，仓库中未保留
学生工作区。
