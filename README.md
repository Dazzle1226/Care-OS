# Care OS Pro Max（ASD 家庭照护操作系统）

黑客松可交付版本：`FastAPI + SQLite + 多 Agent + React PWA`。

## 功能覆盖
- 后端 API：认证、家庭、画像、签到、风险、48h 计划、场景脚本、复盘、周报、支持卡导出
- 四 Agent：`Signal / Plan / Safety / Coach`
- 策略卡系统：严格 Schema、embedding 入库、检索重排、引用卡片 ID
- 安全治理：高风险阻断、禁忌冲突阻断、无 citations 阻断
- 前端 PWA：`Home / Plan / Scripts / Review / Family` 五页 + 低刺激模式
- 测试：禁忌冲突、高风险阻断、LLM 降级、citations 完整性、48h 触发、复盘学习

## 目录
- `backend/` FastAPI 服务
- `frontend/` React + Vite PWA
- `scripts/dev.sh` 本机一键启动
- `scripts/smoke.sh` API 快速冒烟
- `docker-compose.yml` Compose 一键启动

## 一键运行（主路径：Docker Compose）
```bash
docker compose up --build
```
- 后端: `http://localhost:8000`
- 前端: `http://localhost:4173`

## 一键运行（兜底：本机脚本）
```bash
./scripts/dev.sh
```
- 后端: `http://localhost:8000`
- 前端: `http://localhost:5173`

## Demo 数据
### 生成 100 张策略卡
```bash
python3 backend/scripts/generate_strategy_cards.py
```

### 注入 demo 家庭与历史数据
```bash
PYTHONPATH=backend python3 backend/scripts/seed_demo.py
```

## 测试
```bash
cd backend
pytest -q
```

## 快速冒烟
```bash
./scripts/smoke.sh
```

## 环境变量
- `CARE_OS_DATABASE_URL`：数据库连接（默认 SQLite 文件）
- `CARE_OS_JWT_SECRET`：JWT 密钥
- `CARE_OS_EMBEDDING_PROVIDER`：`hash` / `openai` / `auto`
- `OPENAI_API_KEY`：可选，开启 OpenAI embedding/LLM
- `CARE_OS_FORCE_RULE_FALLBACK`：`true` 时强制规则降级

## 说明
- 非医疗系统：不做诊断，不提供医疗处方。
- 高风险信号仅返回安全阻断页与求助建议。
- 资源信息来自静态配置，不由模型编造。
