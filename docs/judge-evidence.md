# 赫兹 Hertz Judge Evidence

## 一句话定位

`赫兹 Hertz 不是通用聊天 AI，而是把“签到、风险判断、现场支持、训练推进、复盘学习、周期报告”串起来的 ASD 家庭照护操作系统。`

## 评委最关心的四类证据

### 1. 真实场景闭环

- 首页签到与今日聚焦：[DailyFlowPage.tsx](/Users/oynxdai/Desktop/Care%20OS/frontend/src/components/DailyFlowPage.tsx)
- 高摩擦支持与危机卡：[Scripts.tsx](/Users/oynxdai/Desktop/Care%20OS/frontend/src/pages/Scripts.tsx)
- 长期训练与反馈学习：[TrainingPlanWorkspace.tsx](/Users/oynxdai/Desktop/Care%20OS/frontend/src/components/TrainingPlanWorkspace.tsx)
- 周报/月报复盘：[ReviewCard.tsx](/Users/oynxdai/Desktop/Care%20OS/frontend/src/components/ReviewCard.tsx)

### 2. 安全与可靠性

- 高风险阻断与禁忌冲突校验：[safety.py](/Users/oynxdai/Desktop/Care%20OS/backend/app/agents/safety.py)
- 策略卡引用与检索：[retrieval.py](/Users/oynxdai/Desktop/Care%20OS/backend/app/services/retrieval.py)
- 多角色接手与解释输出：[friction.py](/Users/oynxdai/Desktop/Care%20OS/backend/app/agents/friction.py)

### 3. 系统会学习

- 训练反馈后自动调整：[training_adjustments.py](/Users/oynxdai/Desktop/Care%20OS/backend/app/services/training_adjustments.py)
- 周报策略排序依据：[reporting.py](/Users/oynxdai/Desktop/Care%20OS/backend/app/services/reporting.py)
- 家庭内偏好权重更新：[coach.py](/Users/oynxdai/Desktop/Care%20OS/backend/app/agents/coach.py)

### 4. 可复现评测

- 评测用例目录：[backend/evals/cases](/Users/oynxdai/Desktop/Care%20OS/backend/evals/cases)
- 统一回归入口：[test_eval_regression.py](/Users/oynxdai/Desktop/Care%20OS/backend/tests/test_eval_regression.py)

## 当前评测集覆盖点

- `checkin_today_flow`
  - 验证首页签到后能生成风险判断、今日聚焦和行动计划。
- `friction_support_explainability`
  - 验证高摩擦支持具备推荐依据、已排除动作、多角色接手话术和引用卡片。
- `script_high_risk_block`
  - 验证高风险输入不会继续生成普通建议，而会进入安全阻断。
- `training_learning_loop`
  - 验证长期训练会生成优先能力、能力详情，并在反馈后形成自动调整。
- `weekly_report_reasoning`
  - 验证周报能输出策略排序依据、下周动作与单点聚焦。

## 评测命令

### 后端全量

```bash
cd /Users/oynxdai/Desktop/Care\ OS/backend
pytest -q
```

### 只跑评测集

```bash
cd /Users/oynxdai/Desktop/Care\ OS/backend
pytest -q tests/test_eval_regression.py
```

### 前端验证

```bash
cd /Users/oynxdai/Desktop/Care\ OS
npm --prefix frontend test
npm --prefix frontend run build
```

## 路演时怎么用这份证据

- 先演示 `首页 -> 高摩擦支持 -> 长期训练 -> 周报` 这一条固定路径。
- 再补一句：`我们没有只做 Demo，还把五类高频场景做成了本地评测集，每次改动都能回归。`
- 最后给评委看这三条命令，强调产品既有体验，也有稳定性和安全回归。
