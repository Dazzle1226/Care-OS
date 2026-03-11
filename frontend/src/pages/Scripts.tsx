import { useState } from 'react';

import { FrictionCrisisCard } from '../components/FrictionCrisisCard';
import { SafetyBlockCard } from '../components/SafetyBlockCard';
import { generateFrictionSupport } from '../lib/api';
import {
  buildFrictionActionContext,
  frictionScenarioOptions,
  hasSchoolCollaborationMessage,
  normalizeFrictionScenario
} from '../lib/frictionSupport';
import { type ActionFlowContext, type CareTab } from '../lib/flow';
import type {
  FrictionChildState,
  FrictionScenario,
  FrictionSupportGenerateResponse
} from '../lib/types';

interface Props {
  token: string;
  familyId: number | null;
  lowStim: boolean;
  onToggleLowStim: () => void;
  onNavigate: (tab: CareTab) => void;
  onActionContextChange: (context: ActionFlowContext | null) => void;
}

type QuickPreset =
  | 'transition_now'
  | 'bedtime_push'
  | 'homework_push'
  | 'outing_exit'
  | 'meltdown_now'
  | 'wakeup_stall'
  | 'meal_conflict'
  | 'screen_off'
  | 'bath_resistance'
  | 'waiting_public';
type SupportAvailability = 'none' | 'one' | 'two_plus';
type SensoryLevel = 'none' | 'light' | 'medium' | 'heavy';
const CUSTOM_SCENARIO_VALUE = '__custom__';

interface PresetOption {
  id: QuickPreset;
  label: string;
  hint: string;
  scenario: FrictionScenario;
  childState: FrictionChildState;
  sensory: SensoryLevel;
  transitionDifficulty: number;
  meltdownCount: number;
  caregiverStress: number;
  caregiverFatigue: number;
  caregiverSleepQuality: number;
  supportAvailable: SupportAvailability;
  confidence: number;
  envChanges: string[];
  featured: boolean;
}

const PRESETS: PresetOption[] = [
  {
    id: 'transition_now',
    label: '过渡',
    hint: '切任务 / 出门 / 回家',
    scenario: 'transition',
    childState: 'transition_block',
    sensory: 'medium',
    transitionDifficulty: 8,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 7,
    caregiverSleepQuality: 4,
    supportAvailable: 'none',
    confidence: 5,
    envChanges: ['切换任务'],
    featured: true
  },
  {
    id: 'bedtime_push',
    label: '睡前',
    hint: '洗澡 / 上床 / 熄灯',
    scenario: 'bedtime',
    childState: 'emotional_wave',
    sensory: 'light',
    transitionDifficulty: 7,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 8,
    caregiverSleepQuality: 3,
    supportAvailable: 'one',
    confidence: 4,
    envChanges: ['睡前切换'],
    featured: true
  },
  {
    id: 'homework_push',
    label: '作业',
    hint: '开始 / 卡住 / 对抗',
    scenario: 'homework',
    childState: 'conflict',
    sensory: 'light',
    transitionDifficulty: 6,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 6,
    caregiverSleepQuality: 4,
    supportAvailable: 'one',
    confidence: 4,
    envChanges: ['学习任务'],
    featured: true
  },
  {
    id: 'outing_exit',
    label: '外出',
    hint: '人多 / 噪音 / 临时变动',
    scenario: 'outing',
    childState: 'sensory_overload',
    sensory: 'medium',
    transitionDifficulty: 7,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 6,
    caregiverSleepQuality: 5,
    supportAvailable: 'one',
    confidence: 4,
    envChanges: ['外出', '人多'],
    featured: true
  },
  {
    id: 'meltdown_now',
    label: '崩溃',
    hint: '已经接近失控',
    scenario: 'meltdown',
    childState: 'meltdown',
    sensory: 'heavy',
    transitionDifficulty: 9,
    meltdownCount: 3,
    caregiverStress: 9,
    caregiverFatigue: 8,
    caregiverSleepQuality: 4,
    supportAvailable: 'one',
    confidence: 2,
    envChanges: ['持续升级'],
    featured: true
  },
  {
    id: 'wakeup_stall',
    label: '起床',
    hint: '起床卡住 / 出门前拉扯',
    scenario: 'transition',
    childState: 'transition_block',
    sensory: 'light',
    transitionDifficulty: 7,
    meltdownCount: 0,
    caregiverStress: 6,
    caregiverFatigue: 7,
    caregiverSleepQuality: 4,
    supportAvailable: 'one',
    confidence: 5,
    envChanges: ['起床'],
    featured: false
  },
  {
    id: 'meal_conflict',
    label: '吃饭',
    hint: '坐下 / 收尾 / 食物冲突',
    scenario: 'transition',
    childState: 'conflict',
    sensory: 'light',
    transitionDifficulty: 6,
    meltdownCount: 1,
    caregiverStress: 6,
    caregiverFatigue: 6,
    caregiverSleepQuality: 5,
    supportAvailable: 'one',
    confidence: 5,
    envChanges: ['吃饭'],
    featured: false
  },
  {
    id: 'screen_off',
    label: '关屏',
    hint: '停平板 / 停电视',
    scenario: 'transition',
    childState: 'conflict',
    sensory: 'medium',
    transitionDifficulty: 8,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 6,
    caregiverSleepQuality: 5,
    supportAvailable: 'none',
    confidence: 4,
    envChanges: ['关屏'],
    featured: false
  },
  {
    id: 'bath_resistance',
    label: '洗澡',
    hint: '触碰 / 水声 / 切换',
    scenario: 'bedtime',
    childState: 'sensory_overload',
    sensory: 'medium',
    transitionDifficulty: 7,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 7,
    caregiverSleepQuality: 4,
    supportAvailable: 'one',
    confidence: 4,
    envChanges: ['洗澡'],
    featured: false
  },
  {
    id: 'waiting_public',
    label: '等待',
    hint: '排队 / 公共场所',
    scenario: 'outing',
    childState: 'emotional_wave',
    sensory: 'medium',
    transitionDifficulty: 8,
    meltdownCount: 1,
    caregiverStress: 7,
    caregiverFatigue: 6,
    caregiverSleepQuality: 5,
    supportAvailable: 'one',
    confidence: 4,
    envChanges: ['等待', '排队'],
    featured: false
  }
];

function parseEnvChanges(value: string): string[] {
  return value
    .split(/[,\n，]/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 4);
}

export function ScriptsPage({
  token,
  familyId,
  lowStim,
  onToggleLowStim,
  onNavigate,
  onActionContextChange
}: Props) {
  const [mode, setMode] = useState<'quick' | 'manual'>('quick');
  const [activePreset, setActivePreset] = useState<QuickPreset | null>('transition_now');
  const [scenario, setScenario] = useState<FrictionScenario>('transition');
  const [scenarioSelection, setScenarioSelection] = useState<FrictionScenario | typeof CUSTOM_SCENARIO_VALUE>('transition');
  const [customScenarioName, setCustomScenarioName] = useState('');
  const [childState, setChildState] = useState<FrictionChildState>('transition_block');
  const [sensoryOverloadLevel, setSensoryOverloadLevel] = useState<SensoryLevel>('medium');
  const [transitionDifficulty, setTransitionDifficulty] = useState(8);
  const [meltdownCount, setMeltdownCount] = useState(1);
  const [caregiverStress, setCaregiverStress] = useState(7);
  const [caregiverFatigue, setCaregiverFatigue] = useState(7);
  const [caregiverSleepQuality, setCaregiverSleepQuality] = useState(4);
  const [supportAvailable, setSupportAvailable] = useState<SupportAvailability>('none');
  const [confidenceToFollowPlan, setConfidenceToFollowPlan] = useState(5);
  const [envChangesInput, setEnvChangesInput] = useState('切换任务');
  const [freeText, setFreeText] = useState('');
  const [highRiskSelected, setHighRiskSelected] = useState(false);

  const [result, setResult] = useState<FrictionSupportGenerateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const featuredPresets = PRESETS.filter((item) => item.featured);
  const morePresets = PRESETS.filter((item) => !item.featured);
  const trimmedCustomScenarioName = customScenarioName.trim();

  const applyPreset = (presetId: QuickPreset) => {
    const preset = PRESETS.find((item) => item.id === presetId);
    if (!preset) return;
    const normalizedScenario = normalizeFrictionScenario(preset.scenario);
    setActivePreset(preset.id);
    setScenario(normalizedScenario);
    setScenarioSelection(normalizedScenario);
    setCustomScenarioName('');
    setChildState(preset.childState);
    setSensoryOverloadLevel(preset.sensory);
    setTransitionDifficulty(preset.transitionDifficulty);
    setMeltdownCount(preset.meltdownCount);
    setCaregiverStress(preset.caregiverStress);
    setCaregiverFatigue(preset.caregiverFatigue);
    setCaregiverSleepQuality(preset.caregiverSleepQuality);
    setSupportAvailable(preset.supportAvailable);
    setConfidenceToFollowPlan(preset.confidence);
    setEnvChangesInput(preset.envChanges.join('，'));
  };

  const openCustomScenarioBuilder = () => {
    setMode('manual');
    setActivePreset(null);
    setScenarioSelection(CUSTOM_SCENARIO_VALUE);
    setCustomScenarioName('');
  };

  const syncFrictionContext = (nextResult: FrictionSupportGenerateResponse | null) => {
    const sourceScenario = scenarioSelection === CUSTOM_SCENARIO_VALUE ? trimmedCustomScenarioName || '自定义场景' : undefined;
    const context = buildFrictionActionContext(nextResult, { scenario, sourceScenario });
    if (context) {
      onActionContextChange(context);
    }
  };

  const run = async () => {
    if (!familyId) {
      setError('请先创建家庭。');
      return;
    }

    setLoading(true);
    setError('');

    try {
      if (scenarioSelection === CUSTOM_SCENARIO_VALUE && !trimmedCustomScenarioName) {
        setError('请先填写新场景名称。');
        return;
      }

      const normalizedScenario = normalizeFrictionScenario(scenario);
      const payload: Record<string, unknown> = {
        family_id: familyId,
        quick_preset: mode === 'quick' ? activePreset : undefined,
        scenario: normalizedScenario,
        custom_scenario: scenarioSelection === CUSTOM_SCENARIO_VALUE ? trimmedCustomScenarioName : '',
        child_state: childState,
        support_available: supportAvailable,
        free_text: freeText.trim(),
        low_stim_mode_requested: lowStim,
        high_risk_selected: highRiskSelected
      };

      if (mode === 'manual') {
        payload.sensory_overload_level = sensoryOverloadLevel;
        payload.transition_difficulty = transitionDifficulty;
        payload.meltdown_count = meltdownCount;
        payload.caregiver_stress = caregiverStress;
        payload.caregiver_fatigue = caregiverFatigue;
        payload.caregiver_sleep_quality = caregiverSleepQuality;
        payload.confidence_to_follow_plan = confidenceToFollowPlan;
        payload.env_changes = parseEnvChanges(envChangesInput);
      }

      const data = await generateFrictionSupport(token, payload);
      setResult(data);
      if (!data.blocked && data.support) {
        syncFrictionContext(data);
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const goToReview = () => {
    syncFrictionContext(result);
    onNavigate('review');
  };

  const handleScenarioSelectionChange = (value: string) => {
    setActivePreset(null);
    if (value === CUSTOM_SCENARIO_VALUE) {
      setScenarioSelection(CUSTOM_SCENARIO_VALUE);
      return;
    }

    const normalizedScenario = normalizeFrictionScenario(value);
    setScenario(normalizedScenario);
    setScenarioSelection(normalizedScenario);
    setCustomScenarioName('');
  };

  return (
    <div className="grid">
      <section className="panel friction-entry-panel">
        <div className="focus-header">
          <div>
            <p className="eyebrow">高摩擦支援</p>
            <h3>先选最接近的场景，再照着行动卡做</h3>
            <p className="muted">先用快速模式；只有现场情况不太一样时，再打开微调。</p>
          </div>
          <div className="focus-actions">
            <button className={`chip-btn ${mode === 'quick' ? 'active' : ''}`} type="button" onClick={() => setMode('quick')}>
              快速模式
            </button>
            <button className={`chip-btn ${mode === 'manual' ? 'active' : ''}`} type="button" onClick={() => setMode('manual')}>
              微调
            </button>
          </div>
        </div>

        <div className="friction-preset-grid">
          {featuredPresets.map((preset) => (
            <button
              key={preset.id}
              className={`preset-card ${activePreset === preset.id ? 'active' : ''}`}
              type="button"
              onClick={() => applyPreset(preset.id)}
            >
              <strong>{preset.label}</strong>
              <span>{preset.hint}</span>
            </button>
          ))}
          <button
            className={`preset-card ${scenarioSelection === CUSTOM_SCENARIO_VALUE ? 'active' : ''}`}
            type="button"
            onClick={openCustomScenarioBuilder}
          >
            <strong>+ 新场景</strong>
            <span>自己命名并建立</span>
          </button>
        </div>

        <div className="chip-row extra-preset-row">
          {morePresets.map((preset) => (
            <button
              key={preset.id}
              className={`chip-btn ${activePreset === preset.id ? 'active' : ''}`}
              type="button"
              onClick={() => applyPreset(preset.id)}
            >
              {preset.label}
            </button>
          ))}
        </div>

        <div className="grid two friction-quick-grid">
          <label>
            <span className="label">孩子现在</span>
            <select className="input" value={childState} onChange={(e) => setChildState(e.target.value as FrictionChildState)}>
              <option value="transition_block">卡住了</option>
              <option value="emotional_wave">情绪波动</option>
              <option value="sensory_overload">感官过载</option>
              <option value="conflict">冲突升级</option>
              <option value="meltdown">已接近崩溃</option>
            </select>
          </label>
          <label>
            <span className="label">现在有人能接手吗</span>
            <select className="input" value={supportAvailable} onChange={(e) => setSupportAvailable(e.target.value as SupportAvailability)}>
              <option value="none">无人可接手</option>
              <option value="one">有 1 位支持者</option>
              <option value="two_plus">有 2 位以上支持者</option>
            </select>
          </label>
        </div>

        <div className="focus-actions">
          <button className={`chip-btn ${lowStim ? 'active' : ''}`} type="button" onClick={onToggleLowStim}>
            {lowStim ? '低刺激已开启' : '一键低刺激'}
          </button>
          <button
            className={`chip-btn ${highRiskSelected ? 'active' : ''}`}
            type="button"
            onClick={() => setHighRiskSelected((value) => !value)}
          >
            {highRiskSelected ? '已标记人身风险' : '有人身风险'}
          </button>
        </div>

        <label className="support-textarea">
          <span className="label">补充一句现场情况</span>
          <textarea
            className="input textarea"
            rows={3}
            value={freeText}
            onChange={(e) => setFreeText(e.target.value)}
            placeholder="例如：刚回家，一提换衣服就大哭。"
          />
        </label>

        {mode === 'manual' ? (
          <div className="friction-manual-shell">
            <div className="grid two">
              <label>
                <span className="label">感官负荷</span>
                <select
                  className="input"
                  value={sensoryOverloadLevel}
                  onChange={(e) => setSensoryOverloadLevel(e.target.value as SensoryLevel)}
                >
                  <option value="none">无</option>
                  <option value="light">轻微</option>
                  <option value="medium">中等</option>
                  <option value="heavy">严重</option>
                </select>
              </label>
              <label>
                <span className="label">场景</span>
                <select className="input" value={scenarioSelection} onChange={(e) => handleScenarioSelectionChange(e.target.value)}>
                  {frictionScenarioOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                  <option value={CUSTOM_SCENARIO_VALUE}>+ 新场景</option>
                </select>
              </label>
              {scenarioSelection === CUSTOM_SCENARIO_VALUE ? (
                <label>
                  <span className="label">新场景名称</span>
                  <input
                    className="input"
                    value={customScenarioName}
                    onChange={(e) => setCustomScenarioName(e.target.value)}
                    placeholder="例如：电梯里、理发店、餐厅等位"
                  />
                  <span className="label">这里是在建立正式场景，不是下面那条现场备注。</span>
                </label>
              ) : null}
              {scenarioSelection === CUSTOM_SCENARIO_VALUE ? (
                <label>
                  <span className="label">按最接近哪类处理</span>
                  <select className="input" value={scenario} onChange={(e) => setScenario(normalizeFrictionScenario(e.target.value))}>
                    {frictionScenarioOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
              <label>
                <span className="label">过渡难度：{transitionDifficulty} / 10</span>
                <input
                  className="input"
                  type="range"
                  min="0"
                  max="10"
                  value={transitionDifficulty}
                  onChange={(e) => setTransitionDifficulty(Number(e.target.value))}
                />
              </label>
              <label>
                <span className="label">今日升级次数：{meltdownCount}</span>
                <input
                  className="input"
                  type="range"
                  min="0"
                  max="3"
                  value={meltdownCount}
                  onChange={(e) => setMeltdownCount(Number(e.target.value))}
                />
              </label>
              <label>
                <span className="label">家长压力：{caregiverStress} / 10</span>
                <input
                  className="input"
                  type="range"
                  min="0"
                  max="10"
                  value={caregiverStress}
                  onChange={(e) => setCaregiverStress(Number(e.target.value))}
                />
              </label>
              <label>
                <span className="label">家长疲劳：{caregiverFatigue} / 10</span>
                <input
                  className="input"
                  type="range"
                  min="0"
                  max="10"
                  value={caregiverFatigue}
                  onChange={(e) => setCaregiverFatigue(Number(e.target.value))}
                />
              </label>
              <label>
                <span className="label">睡眠质量：{caregiverSleepQuality} / 10</span>
                <input
                  className="input"
                  type="range"
                  min="0"
                  max="10"
                  value={caregiverSleepQuality}
                  onChange={(e) => setCaregiverSleepQuality(Number(e.target.value))}
                />
              </label>
              <label>
                <span className="label">执行信心：{confidenceToFollowPlan} / 10</span>
                <input
                  className="input"
                  type="range"
                  min="0"
                  max="10"
                  value={confidenceToFollowPlan}
                  onChange={(e) => setConfidenceToFollowPlan(Number(e.target.value))}
                />
              </label>
            </div>

            <label className="support-textarea">
              <span className="label">环境变化</span>
              <textarea
                className="input"
                rows={2}
                value={envChangesInput}
                onChange={(e) => setEnvChangesInput(e.target.value)}
                placeholder="例如：外出、来客、学校临时变化"
              />
            </label>
          </div>
        ) : null}

        <div className="focus-actions">
          <button className="btn" type="button" onClick={run} disabled={loading}>
            {loading ? '生成中…' : '立即生成行动卡'}
          </button>
          <button className="btn secondary" type="button" onClick={() => onNavigate('plan')}>
            去长期训练跟踪
          </button>
        </div>
      </section>

      {result?.blocked && result.safety_block ? (
        <SafetyBlockCard block={result.safety_block} lowStim={lowStim} onToggleLowStim={onToggleLowStim} />
      ) : null}

      {!result?.blocked && result?.support ? (
        <>
          <FrictionCrisisCard
            plan={result.support}
            riskLevel={result.risk?.risk_level}
            lowStim={lowStim}
            onToggleLowStim={onToggleLowStim}
          />

          <section className="panel support-personalized-panel">
            <div className="focus-header">
              <div>
                <p className="eyebrow">个性化提醒</p>
                <h3>结合家庭档案补充注意点</h3>
              </div>
              <span className="status-pill">按家庭档案</span>
            </div>
            <ul className="list compact-list">
              {result.support.personalized_strategies.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          {hasSchoolCollaborationMessage(result.support.school_message) ? (
            <details className="panel support-secondary-panel">
              <summary>需要同步学校或其他照护者时再展开</summary>
              <blockquote className="quote-box">{result.support.school_message}</blockquote>
              <p className="muted support-citation">引用策略卡：{result.support.citations.join(', ')}</p>
            </details>
          ) : null}

          <section className="panel support-review-panel">
            <div className="focus-header">
              <div>
                <p className="eyebrow">做完后记录</p>
                <h3>直接进轻复盘，不再重复填反馈</h3>
              </div>
              <button className="btn secondary" type="button" onClick={goToReview}>
                去轻复盘
              </button>
            </div>
            <p>{result.support.feedback_prompt}</p>
            <p className="muted">轻复盘里只补结果、触发器和下次保留的一件事，避免在这里再填一遍。</p>
          </section>
        </>
      ) : null}

      {error ? <div className="panel error">{error}</div> : null}
    </div>
  );
}
