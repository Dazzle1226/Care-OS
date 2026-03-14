# 赫兹 Hertz（听见那些未曾开口的爱）

赫兹是一个面向 ASD 家庭支持场景的照护工作台，当前产品主路径已经从早期的“脚本生成器”扩展为：

- 家庭建档与画像沉淀
- 今日签到与首页 AI 分流
- 高摩擦时刻支持
- 训练计划与自适应训练会话
- 复盘、周报与策略学习
- 检索增强、多模态摄入、证据引用与安全阻断

当前主技术路径：`FastAPI + PostgreSQL/pgvector + 多 Agent / RAG + React PWA`  
同时保留 `SQLite` 作为本地开发和兜底路径。

## 当前产品能力

### 1. 照护主流程
- `Onboarding`：登录、家庭创建、儿童画像建档
- `Today / Home`：首页 AI 主卡自动判断优先显示签到、今日行动流、训练建议或复盘入口
- `Check-in`：记录睡眠、过渡难度、照护者压力、支持资源、环境变化等每日状态
- `Review`：记录触发器、使用过的卡片、结果评分和后续动作
- `Weekly Report`：按周汇总趋势、触发因素与训练/支持结果

### 2. 干预与支持
- `高摩擦支持`：针对过渡、睡前、作业、外出等场景生成即时支援步骤
- `48h 计划`：生成短周期可执行计划，而不是泛化建议
- `Micro Respite`：照护者即时喘息入口
- `Support Card`：支持卡导出与引用

### 3. 训练与自适应能力
- `训练方案`：查看今日训练重点、最近调整方向和执行上下文
- `v3/training-sessions`：训练支持会话支持 `start / events / close`
- `v3/friction-sessions`：高摩擦支持会话支持 `start / events / confirm / close / trace`
- `policy memory`：基于历史反馈保留家庭策略偏好
- `decision trace`：保留编排链路与关键决策痕迹，方便解释与调试

### 4. 检索、知识与多模态
- `v2/knowledge`：知识文档与知识块管理
- `v2/retrieval`：混合检索、重排与证据召回
- `v2/ingestions`：多模态输入摄入
- `benchmark / eval`：对检索、编排、多模态、策略学习做回归校验

### 5. 安全约束
- 非医疗系统：不做诊断，不提供医疗处方
- 高风险信号优先阻断，不继续输出普通建议
- 禁忌冲突阻断：避免输出和家庭禁忌相冲突的建议
- 证据约束：关键输出要求带 citations，降低“无依据生成”
- 模型不可用时支持规则降级

## 当前架构

### 后端
- `backend/app/api/routes/`：业务路由，覆盖 `auth / onboarding / family / profile / checkin / plan / scripts / review / report / supportcard / training`
- `v2` 路由：`generation / ingestions / knowledge / policy_memory / benchmarks / retrieval`
- `v3` 路由：`friction-sessions / training-sessions`
- `backend/app/agents/`：`Signal / Plan / Safety / Coach / Friction / Emotion / Coordinator / Support Cards`
- `backend/app/services/`：决策编排、训练系统、知识检索、证据审查、策略学习、多模态解析

### 前端
- `frontend/` 是 React + Vite + TypeScript PWA
- 当前主页面：`首页 / 高摩擦支持 / 训练方案 / 复盘 / 家庭档案`
- 首页已升级为 AI 主卡分流界面，不再只是静态导航
- 支持低刺激模式与本地状态保留

## 仓库结构

- `backend/`：FastAPI 服务、SQLAlchemy 模型、Agent、服务层、测试
- `frontend/`：React PWA 前端
- `docs/technical-overview.md`：更完整的技术说明
- `docs/demo-script.md`：演示脚本
- `backend/evals/cases/`：评测集用例
- `scripts/dev.sh`：本机开发一键启动
- `scripts/smoke.sh`：API 快速冒烟
- `docker-compose.yml`：Compose 启动入口

## 快速开始

### 方式 1：Docker Compose（推荐跑完整主路径）
```bash
docker compose up --build
```

启动后：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:4173`
- 数据库：`postgres://careos:careos@localhost:5432/care_os`

默认 Compose 配置会：

- 启动 `pgvector/pgvector:pg16`
- 让后端使用 PostgreSQL
- 让前端通过 `VITE_API_BASE_URL=http://localhost:8000/api` 访问后端

### 方式 2：本机脚本（适合快速开发）
```bash
./scripts/dev.sh
```

这个脚本会：

- 创建 `.venv`
- 安装 `backend/requirements.txt`
- 执行 demo 数据注入
- 安装前端依赖
- 启动 `uvicorn` 和 `vite`

启动后：

- 后端：`http://localhost:8000`
- 前端：`http://localhost:5173`

## Demo 数据

### 生成策略卡
```bash
python3 backend/scripts/generate_strategy_cards.py
```

### 注入 demo 家庭与历史数据
```bash
PYTHONPATH=backend python3 backend/scripts/seed_demo.py
```

## 测试与验证

### 后端测试
```bash
cd backend
pytest -q
```

### 前端测试
```bash
cd frontend
npm test
```

### 评测回归
```bash
cd backend
pytest -q tests/test_eval_regression.py
```

评测样例位于：

- `backend/evals/cases/`
- `docs/judge-evidence.md`

### 快速冒烟
```bash
./scripts/smoke.sh
```

该脚本会串起一条最小闭环：

- 登录
- 创建家庭
- 建档
- 提交签到
- 生成 48h 计划
- 生成场景脚本
- 提交复盘
- 拉取周报

## 环境变量

可参考 `.env.example`。

### 数据与基础配置
- `CARE_OS_DATABASE_BACKEND`：`postgres` 或 `sqlite`
- `CARE_OS_DATABASE_URL`：数据库连接字符串
- `CARE_OS_JWT_SECRET`：JWT 密钥

### 模型与检索
- `OPENAI_API_KEY`：可选，开启兼容 OpenAI 的模型能力
- `OPENAI_BASE_URL`：OpenAI 兼容网关地址
- `OPENAI_CHAT_MODEL`：对话模型
- `OPENAI_VISION_MODEL`：视觉模型
- `OPENAI_AUDIO_MODEL`：音频模型
- `OPENAI_ENABLE_THINKING`：是否开启思考模式
- `CARE_OS_EMBEDDING_PROVIDER`：embedding 提供方
- `CARE_OS_EMBEDDING_FALLBACK_PROVIDER`：embedding 回退提供方
- `CARE_OS_GENERATION_PRIMARY_PROVIDER`：主生成提供方
- `CARE_OS_GENERATION_SECONDARY_PROVIDER`：次生成提供方
- `CARE_OS_RERANK_PROVIDER`：重排提供方
- `CARE_OS_PROVIDER_TIMEOUT_SECONDS`：外部模型超时时间
- `CARE_OS_CORPUS_VERSION`：知识库版本标签

### 多模态与降级
- `CARE_OS_MULTIMODAL_AUTO_INCLUDE_CONFIDENCE`：多模态自动纳入上下文的置信度阈值
- `CARE_OS_FORCE_RULE_FALLBACK`：`true` 时强制走规则降级

## 适合先读哪里

- 产品/技术总览：`docs/technical-overview.md`
- API 入口：`backend/app/api/router.py`
- 前端入口：`frontend/src/App.tsx`
- 首页分流逻辑：`frontend/src/pages/Home.tsx`
- 决策编排：`backend/app/services/decision_orchestrator.py`

## 项目边界

- 本项目不是医疗系统
- 不替代医生、治疗师或线下应急处理
- 高风险场景应该优先寻求人类支持与专业帮助
