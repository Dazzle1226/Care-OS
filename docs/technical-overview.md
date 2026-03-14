# 赫兹 Hertz 项目技术说明

## 1. 项目概览

赫兹（Hertz）是一个面向 ASD 家庭支持场景的前后端一体化系统，目标是把家庭建档、每日签到、场景干预、48 小时计划、复盘学习与训练支持放在同一个工作台中完成。

当前主路径为：

- 后端：FastAPI
- 数据层：SQLAlchemy + SQLite / PostgreSQL + pgvector
- 智能能力：多 Agent 编排 + 检索增强 + 规则降级
- 前端：React + Vite + TypeScript + PWA

系统强调三个约束：

- 非医疗系统，不做诊断和处方
- 高风险场景优先阻断，不继续生成普通建议
- 输出必须带证据引用，避免无依据生成

## 2. 仓库结构

```text
Care OS/
├── backend/                 # FastAPI 服务、数据模型、Agent、服务层、测试
├── frontend/                # React PWA 前端
├── docs/                    # 项目补充文档
├── scripts/                 # 本地开发与冒烟脚本
├── docker-compose.yml       # Compose 启动入口
└── README.md                # 快速启动说明
```

其中最核心的代码目录如下：

- `backend/app/api/routes/`：按业务域拆分的 HTTP 路由
- `backend/app/agents/`：Signal / Plan / Safety / Coach 等 Agent
- `backend/app/services/`：编排、检索、知识库、训练、复盘等服务
- `backend/app/models/`：SQLAlchemy 实体模型
- `backend/app/schemas/`：Pydantic 输入输出模型与领域常量
- `frontend/src/pages/`：页面级组件
- `frontend/src/components/`：复用 UI 组件
- `frontend/src/lib/`：API 请求、流程状态、前端业务逻辑

## 3. 技术栈

### 3.1 后端

- Python 3
- FastAPI
- SQLAlchemy 2.x
- Pydantic 2 + `pydantic-settings`
- `psycopg` / PostgreSQL
- `pgvector`
- `httpx`
- `pytest`

依赖定义见 [backend/requirements.txt](../backend/requirements.txt)。

### 3.2 前端

- React 18
- TypeScript
- Vite 6
- Tailwind CSS 4
- Framer Motion
- Node 原生测试运行器（`node --test`）

依赖与脚本定义见 [frontend/package.json](../frontend/package.json)。

## 4. 整体架构

系统采用“前端工作台 + API 服务 + 数据存储 + 检索/Agent 编排”结构。

```text
React PWA
  -> FastAPI API
    -> Route Layer
      -> Service Layer
        -> Agent Layer
        -> Retrieval / Knowledge
        -> SQLAlchemy Models
          -> SQLite / PostgreSQL
```

### 4.1 启动流程

后端应用入口在 [backend/app/main.py](../backend/app/main.py)：

- 创建 FastAPI 应用
- 注册 CORS
- 暴露 `/healthz`
- 在 `lifespan` 中执行 `init_db(seed_strategy_cards=True)`
- 将所有业务路由挂载到 `/api`

这意味着服务启动时会自动初始化数据库，并在需要时种入策略卡。

### 4.2 配置体系

配置集中在 [backend/app/core/config.py](../backend/app/core/config.py)。

关键特点：

- 默认 API 前缀为 `/api`
- 数据库支持 `sqlite` 和 `postgres`
- embedding、生成、rerank 都通过环境变量切换
- 未显式配置数据库 URL 时，会根据 `CARE_OS_DATABASE_BACKEND` 自动推导
- 默认允许本地开发地址的 CORS

## 5. 后端设计

### 5.1 API 分层

路由统一在 [backend/app/api/router.py](../backend/app/api/router.py) 注册，按业务可分为几组：

- 基础业务：`auth`、`family`、`profile`、`onboarding`
- 日常照护：`checkin`、`plan`、`scripts`、`review`、`report`、`supportcard`
- 支持场景：`respite`、`training`
- 可观测与追踪：`decision_trace`
- 能力扩展：`v2_generation`、`v2_ingestions`、`v2_knowledge`、`v2_policy_memory`、`v2_benchmarks`、`v2_retrieval`
- 自适应会话：`v3_friction_sessions`、`v3_training_sessions`

这种拆分方式的优点是：路由负责协议层，复杂业务下沉到 `services/` 与 `agents/`。

### 5.2 数据模型

实体定义位于 [backend/app/models/entities.py](../backend/app/models/entities.py)。从领域上可以归为以下几类：

- 账户与家庭：`User`、`Family`
- 儿童画像：`ChildProfile`
- 日常记录：`DailyCheckin`、`IncidentLog`、`Review`
- 干预与计划：`Plan48h`、训练任务、训练状态、调整日志
- 周期输出：`WeeklyReport`、`ReportFeedback`
- 决策追踪：`DecisionTrace`、检索运行记录
- 知识与检索：策略卡、知识文档、知识块、embedding、候选结果
- 多模态输入：上传/解析/入库相关实体

可以把 `Family` 理解为聚合根，大部分业务数据都围绕 `family_id` 组织。

### 5.3 Schema 与领域约束

Pydantic 模型集中在 [backend/app/schemas/domain.py](../backend/app/schemas/domain.py)。

这里承担了三类职责：

- 定义请求/响应结构
- 定义领域枚举与字面量约束
- 提供高摩擦场景的 preset 与标签

例如：

- 登录请求限制 `role`
- 建档请求限制字段长度与数量
- 训练状态、难度、帮助度等使用 `Literal` 做显式边界
- 高摩擦 preset 预置了默认场景、照护者压力、环境变化等输入

这能保证前后端之间的协议比较稳定，也便于测试覆盖。

### 5.4 Agent 与决策编排

核心编排逻辑在 [backend/app/services/decision_orchestrator.py](../backend/app/services/decision_orchestrator.py)。

当前决策图（`GRAPH_VERSION = "v2"`）主要阶段包括：

- `context_ingestion`
- `signal_eval`
- `evidence_recall`
- `candidate_generation`
- `safety_critic`
- `evidence_critic`
- `policy_adjust_hint`
- `finalizer`

对应的职责大致如下：

- `SignalAgent`：判断当前风险/触发信号
- `PlanAgent`：生成 48h 计划或场景脚本
- `FrictionAgent`：生成高摩擦时刻支持方案
- `SafetyAgent`：检查高风险、禁忌冲突、是否需要阻断
- `EvidenceCritic`：检查输出和证据是否匹配
- `PolicyLearningService`：根据历史反馈给出个性化偏置

如果从输出角度理解，后端不是“直接调一个模型”，而是“先做上下文整合与检索，再做候选生成，最后走安全和证据审查”。

### 5.5 协调层

[backend/app/agents/coordinator.py](../backend/app/agents/coordinator.py) 负责在高摩擦支持场景下做协调决策。

它会结合：

- 安全结论
- 情绪/负荷评估
- 证据审查结果
- 现场是否有支持者

然后在以下策略中选择其一：

- `continue`：继续当前方案
- `lighter`：压缩成更轻、更短的一步
- `handoff`：优先交接
- `block`：安全阻断

这层设计的价值是把“输出建议”与“当前现场能不能执行”分开处理。

### 5.6 检索增强与知识体系

检索核心在 [backend/app/services/retrieval.py](../backend/app/services/retrieval.py)。

其特点不是单一向量检索，而是混合打分：

- 语义相似度
- 词面重叠
- 场景匹配
- 儿童画像匹配
- 历史效果
- 家庭策略偏好
- 执行成本奖励
- 风险惩罚
- 禁忌冲突惩罚

最终会输出：

- 入选策略卡
- 候选分数明细
- 证据单元与知识块引用
- 覆盖度评分
- 是否“证据不足”

这也是项目里“必须有 citations”这一机制的技术基础。

### 5.7 降级与安全策略

从配置和服务设计可以看出，系统支持多重降级：

- embedding 提供方可切换
- 生成模型可配置主次提供方
- 可强制开启规则降级 `CARE_OS_FORCE_RULE_FALLBACK`
- 高风险关键词命中后优先走阻断链路

这让系统在外部模型能力不可用时，仍保留一个可控的最低可用路径。

## 6. 前端设计

### 6.1 应用结构

前端入口在 [frontend/src/App.tsx](../frontend/src/App.tsx)。

应用核心状态包括：

- 当前 tab
- 登录 token
- 当前家庭 ID
- 建档摘要
- 操作流上下文
- 低刺激模式状态
- 微休息弹窗状态

页面层主要包括：

- `HomePage`
- `PlanPage`
- `ScriptsPage`
- `ReviewPage`
- `FamilyPage`
- `OnboardingPage`

与 `README` 中提到的工作台结构是一致的。

### 6.2 前端职责划分

前端代码分层比较清晰：

- `pages/`：页面组合与业务入口
- `components/`：流程卡片、表单、模态框等复用 UI
- `lib/api.ts`：API 请求封装
- `lib/*.ts`：流程状态、表单映射、展示文案、请求保护等逻辑
- `styles/`：设计 token 与应用样式
- `pwa/registerSW.ts`：PWA 注册逻辑

从实现上看，前端承担的不只是展示，还包含一定程度的流程编排，例如：

- 本地存储 token / family_id
- 保持 action flow 上下文
- 当家庭不存在时回退到重新建档
- 管理低刺激模式和 UI 切换

### 6.3 PWA 与体验设计

项目具备明显的 PWA 特征：

- `public/manifest.json`
- `public/sw.js`
- `src/pwa/registerSW.ts`

同时前端使用了：

- Tailwind 4 做样式组织
- Framer Motion 做页面与内容过渡动画
- 低刺激模式切换主题变量与浏览器 `theme-color`

这与项目照护场景下“降低界面刺激强度”的目标是匹配的。

## 7. 关键业务流

### 7.1 登录与建档

典型链路如下：

1. 前端调用登录接口获取 token
2. 若无家庭档案，则进入 `OnboardingPage`
3. 创建家庭、儿童画像与摘要信息
4. 前端保存 `family_id`
5. 后续页面都围绕该家庭上下文工作

### 7.2 计划/脚本生成

生成链路可概括为：

1. 读取家庭画像、签到、上下文输入
2. 评估信号与风险
3. 召回策略卡与证据
4. 生成候选计划或脚本
5. 做安全审查与证据审查
6. 记录决策追踪
7. 返回可执行内容与引用

### 7.3 高摩擦支持

高摩擦支持链路在计划生成之外增加了“协调决策”这一层：

1. 识别当前 preset 或现场参数
2. 生成支持方案
3. 结合情绪负荷、安全状态、证据完整性做协调
4. 输出继续 / 简化 / 交接 / 阻断中的一种结果

### 7.4 训练与复盘学习

从 `services/` 与测试命名可以看出，项目已经形成“训练任务 -> 反馈 -> 技能状态更新 -> 周期计划”的闭环。

相关能力包括：

- 训练任务编排
- 技能状态追踪
- 自适应训练会话
- 复盘学习
- 周报生成
- 家庭策略偏好更新

## 8. 部署与运行

### 8.1 Docker Compose

主启动方式见 [docker-compose.yml](../docker-compose.yml)。

包含三个服务：

- `postgres`：`pgvector/pgvector:pg16`
- `backend`：FastAPI 服务
- `frontend`：Vite 预览服务

默认端口：

- 后端 `8000`
- 前端 `4173`
- Postgres `5432`

### 8.2 本地开发脚本

[scripts/dev.sh](../scripts/dev.sh) 提供兜底开发方式，流程为：

1. 创建 `.venv`
2. 安装后端依赖
3. 注入 demo 数据
4. 安装前端依赖
5. 启动 `uvicorn --reload`
6. 启动 `vite dev`

适合单机开发和快速调试。

### 8.3 关键环境变量

项目最关键的环境变量包括：

- `CARE_OS_DATABASE_BACKEND`
- `CARE_OS_DATABASE_URL`
- `CARE_OS_JWT_SECRET`
- `CARE_OS_EMBEDDING_PROVIDER`
- `CARE_OS_EMBEDDING_FALLBACK_PROVIDER`
- `CARE_OS_GENERATION_PRIMARY_PROVIDER`
- `CARE_OS_GENERATION_SECONDARY_PROVIDER`
- `CARE_OS_RERANK_PROVIDER`
- `CARE_OS_CORPUS_VERSION`
- `OPENAI_API_KEY`
- `CARE_OS_FORCE_RULE_FALLBACK`

建议在不同环境下分别明确：

- 数据库类型
- 模型提供方
- 是否允许规则降级
- JWT 密钥

## 9. 测试与质量保障

项目测试覆盖比较完整，分布在：

- [backend/tests](../backend/tests)
- [frontend/tests](../frontend/tests)

从测试文件命名可以看出，后端重点覆盖：

- 高风险阻断
- 禁忌冲突
- LLM 回退
- 检索与证据完整性
- Onboarding 流程
- 训练/高摩擦会话
- 周报与复盘学习

前端重点覆盖：

- API 请求保护
- 建档与日流转
- 今日焦点与行动流上下文
- 复盘表单
- 多模态输入
- 训练追踪

这说明项目不是单纯原型，而是已经有一定程度的行为回归保障。

## 10. 当前架构特点与建议

### 优点

- 业务域边界比较清晰，API / Service / Agent 分层明显
- 数据结构完整，适合承载长期家庭画像与反馈学习
- 检索、安全、证据审查三层组合，降低“随意生成”风险
- 前端是完整工作台，不是单页演示
- 测试覆盖面较好

### 当前复杂度来源

- 业务域较多，`schemas` 与 `models` 已经比较庞大
- `services/` 同时承担检索、训练、复盘、知识库、多模态，后续需要持续维持边界
- Agent、critic、policy learning 叠加后，排查问题更依赖决策追踪

### 后续演进建议

- 持续强化 `decision_trace` 的可观测性，把关键阶段耗时和失败原因暴露得更直接
- 为外部模型依赖补充分环境配置文档
- 逐步补一份 API 接口清单文档，方便前后端联调与第三方接入
- 若知识库继续扩张，可考虑将检索配置和评分权重进一步配置化

## 11. 总结

赫兹 Hertz 当前已经具备一个完整照护支持系统的雏形：前端提供工作台体验，后端通过多 Agent、检索增强、安全阻断与反馈学习来生成更可执行、更可解释的建议。它不是“通用聊天机器人外壳”，而是围绕家庭支持场景做了明确结构化设计的垂直系统。
