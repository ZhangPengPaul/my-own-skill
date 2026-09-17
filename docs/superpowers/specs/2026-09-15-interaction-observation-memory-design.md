# 日常互动观察记忆层设计

## 目标

将上海高中学习教练从显式任务驱动的诊断器扩展为日常陪伴型教练：学生可以自然地随手拍题、问知识点、问英文单词或追问解法；教练优先解决当前问题，同时从学生的提问、作答、解释和提示依赖中积累结构化观察。跨两次不同互动出现相似线索后，教练再进行低打扰验证；只有验证产生正式学生表现证据时，才更新掌握状态。

## 非目标

日常互动观察层不保存完整题目、原始回答、图片或 PDF 内容；学生明确进入批改、复盘或正式掌握验证后，现有 session evidence 可保存完成该任务所必需的作答证据。不引入向量数据库或外部服务；不让日常观察直接改变 `stable`、`confirmed_gap` 等正式状态；不强制每次日常互动运行完整的订正—变式—复测流程。

## 方案

新增独立的 `interaction_observation` 不可变事实层，和现有 `session`、`plan_item` 并列。观察 schema 可表示弱线索或重复线索，但本 Skill 对每次日常互动的新观察一律写为 `weak`，重复性由跨互动聚合结果表达；现有 session evidence 仍是正式掌握证据的唯一入口。

```text
日常互动 → 自然回答 → 结构化观察 → 跨互动聚合 → 内部待验证状态
→ 自然小检查 → 学生真实验证 → session evidence → state.json
```

## 数据模型

新增 `observations/` 目录。每个文件名为 `<record_id>.json`，包含：

- `schema_version` 为整数 `1`，`record_type` 为 `interaction_observation`，`record_id` 在 session、plan_item、observation 三类事实之间全局唯一；`record_id` 和 `interaction_id` 必须匹配 `^[a-z0-9][a-z0-9-]{0,95}$`，只使用 ASCII 小写字母、数字和连字符
- `interaction_id`, `occurred_at`
- `subject`, `module_id`, `target_kind`, `target_id`, `target_name`
- `signal_kind`, `signal`
- `evidence_strength`：schema 允许 `weak`、`repeated`；本 Skill 的日常互动新观察只写 `weak`
- `interaction_kind`, `student_action`
- `uncertainty`

只允许结构化摘要。`signal` 描述可复用的学习行为，不复制题目或学生原文。无法可靠归一化的目标使用 `pending-normalization`，不参与合并。`target_name`、`signal`、`student_action`、`uncertainty` 分别限制为 120、240、160、240 字符；`signal_kind` 是最长 64 字符的 ASCII slug；`target_id` 是匹配学科的 dotted slug；canonical JSON 不超过 4 KiB，并拒绝明显的 PDF、data URI、base64 或 hex 媒体载荷。完整写入约定位于 `references/observation-memory.md`，只在实际写入时加载。

观察必须来自不同 `interaction_id` 才能计为两次；同一题重试或幂等重试不得重复计数。观察不包含掌握状态字段，也不能单独生成正式 evidence。观察层不使用 `confirmed`；`confirmed` 只能由正式 `session evidence` 产生。

## 日常教练行为

优先回应当前问题。仅在任务性质不清、需要批改/保存/计划，或不同路径会明显影响结果时确认任务模式。

持久化学生 ID 的新互动先读取已验证的正式状态、未解决单次弱线索和待验证观察，作为写入前历史基线；读取失败不阻塞当前答疑，但不得声称存在历史规律。观察是后台动作，不要求每次互动都记录；出现清晰且可复用的学习行为线索时写入一条 `weak` 观察，没有有效线索时不为凑记录而写入。学生明确表示不知道、不会判断或发生混淆，且问题指向可再次观察的知识、规则或步骤时，即使没有提交解题尝试，也属于应记录的弱线索；记录不得虚构作答，并注明尚未观察到独立表现。单纯要求换一种讲法、确认已给答案或表达兴趣不自动构成线索。写入并校验后立即重跑汇总，并与写入前基线比较。低打扰验证只在本轮新增观察使同一 `subject`、`module_id`、`target_kind`、`target_id`、`signal_kind` 五字段组从恰好一个历史 `interaction_id` 首次变为两个不同 `interaction_id` 时触发；已有待验证组、本轮未新增匹配观察或任一字段不一致都不触发。例如反复漏条件、只给结论、概念能复述但不会应用、词义或词性混淆、依赖提示或换表示后失效。`signal` 和 `student_action` 只能概括可复用行为，不得逐字复制题目、回答或大段连续文本。

工作区定位、历史读取、观察提交和校验默认在后台完成。除 `created` 或 `migrated` 时的一次性告知外，不向学生播报 Skill、学生 ID、工作区、文件、命令、写入、历史观察、重复事实、诊断过程或内部状态。运行环境要求进度消息时，整轮最多一句学习问题导向的自然过渡，并先给当前问题的关键答案。

单次表现只创建 `weak` 观察，不向学生宣布确定薄弱点。本轮首次形成待验证组时，后台比较所有成员观察，以每条成员都支持的最小共同表现选择验证内容；这个共同表现只用于选题，不在学生可见回复中说明。教练先完整回答当前问题，再像自然教学中的顺手检查一样加入一个最小验证问题、局部重做或短变式；不提历史观察、不同互动中的重复、记忆、诊断过程、可能原因或“是否属于薄弱点”。验证题必须让学生直接执行重复信号中尚未完成的同一类动作并留给学生回答，不能只问前置条件、定义片段或相关但更简单的问题。最小新情境必须改变足以阻止照抄答案的信息；仅重命名点、射线或字母且可机械替换刚讲过的符号关系，不算有效验证。对于计算或语言运用，改变数值、条件或语境可以构成最小变式，但仍须让学生独立执行待验证动作且不得提前泄露答案。若信号是从候选中识别目标，验证题须加入至少一个干扰项或多个候选，不能只给唯一两条已识别射线让学生照写角名。具体答案不得在此前任何可见消息中出现。同一判断下的关联空格或小步骤算一个任务，多个独立题目或练习组不算。当前互动与该观察组无关、学生表示没空或只要答案、希望先完成当前题或要求切题时不插入验证；无论本轮插入还是延期，这次边沿触发都不在后续普通互动中反复主动追问。日常问单词或单步理由时，解释深度与当前问题相称；没有本轮 1→2 边沿时不自动追加练习。

## 聚合与升级

新增观察汇总逻辑，按 `subject`、`module_id`、`target_kind`、`target_id`、`signal_kind` 聚合。目标可靠且只有一个 interaction 时，汇总为未解决单次弱线索，供下一会话建立历史基线；来源 interaction 不同的两条或以上观察生成并持续保留 `pending-validation`。聚合状态与用户可见触发分开：`pending-validation` 可以在后续汇总中继续存在，只有写入前后对比显示本轮首次从一个 interaction 变成两个时，才允许自然加入一次小检查。聚合结果展示目标、次数、最近时间、代表性线索和不确定性，不直接改状态。

验证产生正式 session evidence 后，继续沿用现有状态机和证据门槛；只有这类正式证据才能产生 `confirmed`。正式 evidence 可选填写 `resolves_observation_signal_kinds`，只列出该证据实际验证过的行为线索。只有 active、completed session 中的 evidence，且 `completed_at` 晚于该条观察、`subject`、`module_id`、`target_kind`、`target_id` 全部匹配、`signal_kind` 明确列在该字段中，并且 evidence 类型为 `diagnostic`、`variant`、`delayed_retest` 或 `transfer` 时，才关闭对应的较早观察；字段缺失、空列表、同目标下未列出的其他 `signal_kind`、`initial_attempt` 和 `correction` 都不关闭观察。事实文件保持不可变，验证后新出现的观察开始新的生命周期。没有验证表现时，观察只能作为待验证线索。

## 持久化、迁移和隐私

首次使用持久化学生 ID 时告知已启用本地学习记忆，并说明日常答疑只保存结构化观察；同时说明学生以后明确进入批改、复盘或正式掌握验证时，才可能保存该任务必需的作答证据。观察写入沿用现有事务写入器和工作区锁；观察提交失败不能污染正式状态，也不应阻塞当前答疑。

私有可写性属于宿主部署责任，CLI 的身份匹配不能替代根目录权限配置。模型不得向学生索要真实身份、猜测 ID 或从姓名、学校、班级等信息派生 ID；缺少稳定 ID 或私有可写根目录时走零写入临时会话。

宿主必须为同一学生稳定注入同一个不透明持久化学生 ID，并提供仅该学生和当前运行环境可访问的私有可写根目录；不能使用姓名、学校、班级等可识别信息充当 ID。持久化学生 ID 统一通过 `init_student.py --ensure --report-status <student-id>` 路由。命令按 `--root`、绝对路径环境变量 `SHANGHAI_HIGH_SCHOOL_STUDY_COACH_ROOT`、`~/.local/share/shanghai-high-school-study-coach/student-workspaces/` 的顺序选择根目录；显式 `--root` 可为绝对路径或相对路径，相对路径按命令调用时的工作目录解析。命令输出含绝对 `workspace` 路径及 `created`、`migrated` 或 `existing` 状态的 JSON；后续命令只使用该路径。`created` 和 `migrated` 触发首次观察记忆告知，`existing` 不重复告知。根目录不可用时明确失败，不能退回当前工作目录。`--ensure` 在工作区缺失时创建，在已有时持有同一根目录描述符完成身份校验；旧工作区须先只读验证状态和学生 ID，再在同一把排他锁内创建 `observations/` 并完成最终校验。

没有持久化学生 ID 时保持零写入，不接受仅凭工作区路径绕过身份要求。`commit_learning_state.py`、`validate_student_data.py`、`summarize_progress.py` 和 `delete_observations.py` 都必须接收 `--student-id`。入口先校验 expected student ID 的语法，非法 ID 在打开工作区前拒绝；持有工作区锁后，只读取 `state.json` 中的身份并比对，匹配后才读取 profile、完整 state、sessions、plan-items 和 observations。ID 不匹配时不得读取其他事实，即使其他事实损坏也应优先返回身份不匹配。增加按学生、目标或时间范围删除观察的能力；删除后汇总结果必须同步消失。默认不向外部服务发送观察或材料。

## 跨会话回归

跨进程存储测试使用两个不同工作目录和两个独立 CLI 进程，只共享同一个私有根目录及学生 ID。第一轮目录删除后，第二轮仍须通过 `--ensure` 找到同一绝对工作区；第一条观察不能产生待验证项，第二条不同 `interaction_id` 的相似观察应出现两次汇总，且两轮前后 `state.json` 字节不变，工作区内不得出现原题或原回答。

真实模型回归同样为每轮启动独立的 `codex exec --ephemeral`，后续 prompt 不携带此前题目或回答。每个 case 使用独立私有根目录，并设置“有历史”与“空历史”对照：两者都先准确回答当前问题；只有有历史分支在本轮首次形成待验证组后自然加入一个小检查，但不得向学生提及历史、重复观察、记忆或诊断边界。第三次匹配观察用于确认 2→3 时观察数为 3、pending group 仍为 1，且不再次追加验证任务。runner 保存每轮 JSONL、stderr、全部可见消息、最终回复、净化后的观察摘要、prompt 和回复哈希、退出码及汇总报告；`source_sha256` 记录实际解析的 manifest 原始字节、runner，以及 Skill 目录下全部非符号链接常规文件，只排除 `__pycache__`、`.pyc`、`.pyo` 等生成缓存。Python 测试证明存储和隔离链路；真实模型回归另行证明 Skill 在会话中的行为，两类结论不能互相替代。

## 组件变更

- `learning_state.py`：新增 observation schema、校验和聚合输入约束，并校验 session evidence 的可选 `resolves_observation_signal_kinds`。
- `commit_learning_state.py`：支持 observation fact 的原子发布、幂等重试和跨类型 ID 冲突检查，并强制校验学生 ID。
- `validate_student_data.py`：校验 `observations/`，并纳入 workspace snapshot；即使跳过派生状态一致性检查，也必须验证三类事实 record_id 全局唯一，并强制校验学生 ID。
- `summarize_progress.py`：展示未解决单次弱线索、待验证观察和正式状态，按完整目标和 `resolves_observation_signal_kinds` 精确关闭已有匹配正式验证的旧线索，保持确定性排序，并强制校验学生 ID。
- `delete_observations.py`：在锁内按筛选条件删除观察，强制校验学生 ID，并使删除结果立即反映到汇总。
- `init_student.py`：实现稳定根目录选择和 `--ensure`，为新工作区创建 observations 目录，并安全复用或迁移已有工作区。
- `SKILL.md`：规定日常互动、隐性观察、本轮 1→2 边沿后的低打扰验证和用户可见约束。
- `run_cross_session_eval.py`：以独立临时会话执行有历史与空历史对照，保存可审阅的原始产物和报告。

## 验证标准

必须覆盖：观察 schema 与隐私上限校验；同一 interaction 去重；单次线索跨会话可见；仅本轮 1→2 边沿触发一次低打扰验证；第三次匹配观察使计数从 2 变为 3 时仍只有一个 pending group，且不再次追加验证；目标不一致不合并；pending-normalization 不合并；观察不改变 state；正式验证按完整目标和 `resolves_observation_signal_kinds` 精确关闭旧线索并按证据门槛更新 state；验证后新观察重新计数；观察摘要不含原始材料；删除和迁移；稳定根目录、并发 `--ensure`、符号链接和迁移前只读校验；所有持久化 CLI 在身份不匹配时先于完整事实读取拒绝操作；观察写入失败的隔离性；跨进程 E2E；有历史与空历史的真实模型对照，并人工确认前台不暴露历史观察或诊断过程；现有全部测试保持通过。
