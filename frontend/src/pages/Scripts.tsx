import { useEffect, useRef, useState } from 'react';

import { FrictionCrisisCard } from '../components/FrictionCrisisCard';
import { SafetyBlockCard } from '../components/SafetyBlockCard';
import {
  addFrictionSessionEventV3,
  closeFrictionSessionV3,
  confirmFrictionSessionV3,
  ingestAudio,
  ingestDocument,
  startFrictionSessionV3,
  uploadAudioFile,
  uploadDocumentFile,
  getUserFacingApiError
} from '../lib/api';
import {
  buildFrictionActionContext,
  CUSTOM_FRICTION_SCENARIO_VALUE,
  frictionScenarioOptions,
  hasSchoolCollaborationMessage,
  normalizeFrictionScenario,
  resolveFrictionScenarioSelection
} from '../lib/frictionSupport';
import { type ActionFlowContext, type CareTab } from '../lib/flow';
import { getAutoIncludedIngestionIds, shouldAutoIncludeIngestion } from '../lib/multimodal';
import type {
  AdaptiveSession,
  CriticReview,
  CoordinationDecision,
  DecisionGraphStageRun,
  EmotionAssessment,
  ExecutionState,
  FrictionChildState,
  FrictionScenario,
  FrictionSupportPlan,
  MultimodalIngestionResponse,
  PlanRevision,
  PlanRevisionDiff,
  RetrievalEvidenceBundle,
  SafetyBlockResponse,
  SignalOutput,
  TaskNode
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

const handoffTargetLabel = {
  family: '给家长',
  supporter: '给接手人',
  teacher: '给老师'
} as const;

const coordinationModeLabel = {
  continue: '继续当前方案',
  lighter: '换成更轻的一步',
  handoff: '转为协同接手',
  blocked: '暂缓执行'
} as const;

const riskLevelLabel = {
  green: '低',
  yellow: '中',
  red: '高'
} as const;

const childEmotionLabel = {
  calm: '平稳',
  fragile: '脆弱',
  escalating: '正在升级',
  meltdown_risk: '接近崩溃'
} as const;

const caregiverEmotionLabel = {
  calm: '平稳',
  strained: '吃力',
  anxious: '焦虑',
  overloaded: '过载'
} as const;

const criticLabel = {
  safety: '安全校验',
  evidence: '方案校验',
  plan: '计划校验'
} as const;

const criticDecisionLabel = {
  pass: '通过',
  revise: '需要调整',
  clarify: '需要澄清',
  needs_clarification: '信息不足',
  fallback_ok: '允许用保守方案',
  block: '阻断'
} as const;

const taskStatusLabel = {
  pending: '待开始',
  active: '进行中',
  completed: '已完成',
  failed: '未完成',
  dropped: '已移除'
} as const;

const taskKindLabel = {
  stabilize: '先稳定',
  co_regulate: '共同调节',
  transition: '完成过渡',
  handoff: '协同接手',
  exit: '安全收尾',
  observe: '继续观察'
} as const;

function formatTaskLabel(taskId: string | null | undefined, taskTree: TaskNode[]): string {
  if (!taskId) return '无';
  const index = taskTree.findIndex((item) => item.task_id === taskId);
  if (index >= 0) return `任务 ${index + 1}`;
  return '任务';
}

function formatTaskList(taskIds: string[], taskTree: TaskNode[]): string {
  if (!taskIds.length) return '无';
  return taskIds.map((taskId) => formatTaskLabel(taskId, taskTree)).join('、');
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
  const [scenarioSelection, setScenarioSelection] = useState<
    FrictionScenario | typeof CUSTOM_FRICTION_SCENARIO_VALUE
  >('transition');
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
  const [documentText, setDocumentText] = useState('');
  const [audioText, setAudioText] = useState('');
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [ingestions, setIngestions] = useState<MultimodalIngestionResponse[]>([]);
  const [importingSource, setImportingSource] = useState<'document' | 'audio' | null>(null);

  const [session, setSession] = useState<AdaptiveSession | null>(null);
  const [currentRisk, setCurrentRisk] = useState<SignalOutput | null>(null);
  const [currentEmotion, setCurrentEmotion] = useState<EmotionAssessment | null>(null);
  const [currentSupport, setCurrentSupport] = useState<FrictionSupportPlan | null>(null);
  const [currentCoordination, setCurrentCoordination] = useState<CoordinationDecision | null>(null);
  const [currentSafetyBlock, setCurrentSafetyBlock] = useState<SafetyBlockResponse | null>(null);
  const [currentEvidenceBundle, setCurrentEvidenceBundle] = useState<RetrievalEvidenceBundle | null>(null);
  const [traceSummary, setTraceSummary] = useState<DecisionGraphStageRun[]>([]);
  const [currentPlanRevision, setCurrentPlanRevision] = useState<PlanRevision | null>(null);
  const [currentActiveTask, setCurrentActiveTask] = useState<TaskNode | null>(null);
  const [currentTaskTree, setCurrentTaskTree] = useState<TaskNode[]>([]);
  const [currentExecutionState, setCurrentExecutionState] = useState<ExecutionState | null>(null);
  const [currentRevisionDiff, setCurrentRevisionDiff] = useState<PlanRevisionDiff | null>(null);
  const [currentCriticVerdicts, setCurrentCriticVerdicts] = useState<CriticReview[]>([]);
  const [currentReplanReason, setCurrentReplanReason] = useState<string | null>(null);
  const [sessionNote, setSessionNote] = useState('');
  const [learningSummary, setLearningSummary] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const customScenarioInputRef = useRef<HTMLInputElement | null>(null);

  const featuredPresets = PRESETS.filter((item) => item.featured);
  const morePresets = PRESETS.filter((item) => !item.featured);
  const trimmedCustomScenarioName = customScenarioName.trim();
  const includedIngestionIds = getAutoIncludedIngestionIds(ingestions);

  useEffect(() => {
    if (scenarioSelection !== CUSTOM_FRICTION_SCENARIO_VALUE) return;
    if (mode !== 'manual') return;

    const input = customScenarioInputRef.current;
    if (!input) return;

    input.scrollIntoView({ block: 'center', behavior: 'smooth' });
    input.focus();
    input.select();
  }, [mode, scenarioSelection]);

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
    setScenarioSelection(CUSTOM_FRICTION_SCENARIO_VALUE);
    setCustomScenarioName('');
  };

  const syncFrictionContext = (nextSupport: FrictionSupportPlan | null) => {
    const sourceScenario =
      scenarioSelection === CUSTOM_FRICTION_SCENARIO_VALUE ? trimmedCustomScenarioName || '自定义场景' : undefined;
    const context = buildFrictionActionContext(
      nextSupport
        ? {
            blocked: false,
            support: nextSupport
          }
        : null,
      { scenario, sourceScenario }
    );
    if (context) {
      onActionContextChange(context);
    }
  };

  const applySessionState = (params: {
    session?: AdaptiveSession | null;
    risk?: SignalOutput | null;
    emotion?: EmotionAssessment | null;
    support?: FrictionSupportPlan | null;
    coordination?: CoordinationDecision | null;
    safetyBlock?: SafetyBlockResponse | null;
    evidenceBundle?: RetrievalEvidenceBundle | null;
    trace?: DecisionGraphStageRun[];
    planRevision?: PlanRevision | null;
    activeTask?: TaskNode | null;
    taskTree?: TaskNode[];
    executionState?: ExecutionState | null;
    revisionDiff?: PlanRevisionDiff | null;
    criticVerdicts?: CriticReview[];
    replanReason?: string | null;
  }) => {
    setSession(params.session ?? null);
    setCurrentRisk(params.risk ?? null);
    setCurrentEmotion(params.emotion ?? null);
    setCurrentSupport(params.support ?? null);
    setCurrentCoordination(params.coordination ?? null);
    setCurrentSafetyBlock(params.safetyBlock ?? null);
    setCurrentEvidenceBundle(params.evidenceBundle ?? null);
    setTraceSummary(params.trace ?? []);
    setCurrentPlanRevision(params.planRevision ?? null);
    setCurrentActiveTask(params.activeTask ?? null);
    setCurrentTaskTree(params.taskTree ?? []);
    setCurrentExecutionState(params.executionState ?? null);
    setCurrentRevisionDiff(params.revisionDiff ?? null);
    setCurrentCriticVerdicts(params.criticVerdicts ?? []);
    setCurrentReplanReason(params.replanReason ?? null);
    if (params.support) {
      syncFrictionContext(params.support);
    }
  };

  const submitIngestion = async (sourceType: 'document' | 'audio') => {
    if (!familyId) {
      setError('请先创建家庭。');
      return;
    }

    const rawText = (sourceType === 'document' ? documentText : audioText).trim();
    const selectedFile = sourceType === 'document' ? documentFile : audioFile;
    if (!rawText && !selectedFile) {
      setError(sourceType === 'document' ? '请先粘贴通知、作业单或视觉日程内容。' : '请先粘贴现场语音转写或摘要。');
      return;
    }

    setImportingSource(sourceType);
    setError('');
    try {
      let response: MultimodalIngestionResponse;
      if (selectedFile) {
        const formData = new FormData();
        formData.set('family_id', String(familyId));
        formData.set('content_name', selectedFile.name);
        formData.set('file', selectedFile);
        response =
          sourceType === 'document' ? await uploadDocumentFile(token, formData) : await uploadAudioFile(token, formData);
      } else {
        response =
          sourceType === 'document'
            ? await ingestDocument(token, {
                family_id: familyId,
                source_type: 'document',
                content_name: '手动导入通知',
                raw_text: rawText
              })
            : await ingestAudio(token, {
                family_id: familyId,
                source_type: 'audio',
                content_name: '手动导入语音',
                raw_text: rawText
              });
      }
      setIngestions((current) => [...current, response]);
      if (sourceType === 'document') {
        setDocumentText('');
        setDocumentFile(null);
      } else {
        setAudioText('');
        setAudioFile(null);
      }
    } catch (err) {
      setError(
        getUserFacingApiError(
          err,
          sourceType === 'document'
            ? '文档解析失败，请改用手动粘贴通知摘要。'
            : '音频解析失败，请改用手动粘贴语音摘要。'
        )
      );
    } finally {
      setImportingSource(null);
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
      if (scenarioSelection === CUSTOM_FRICTION_SCENARIO_VALUE && !trimmedCustomScenarioName) {
        setError('请先填写新场景名称。');
        return;
      }

      const normalizedScenario = normalizeFrictionScenario(scenario);
      const payload: Record<string, unknown> = {
        family_id: familyId,
        quick_preset: mode === 'quick' ? activePreset : undefined,
        scenario: normalizedScenario,
        custom_scenario: scenarioSelection === CUSTOM_FRICTION_SCENARIO_VALUE ? trimmedCustomScenarioName : '',
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

      const data = await startFrictionSessionV3(token, {
        ...payload,
        ingestion_ids: includedIngestionIds
      });
      applySessionState({
        session: data.session ?? null,
        risk: data.risk ?? null,
        emotion: data.emotion ?? null,
        support: data.support ?? null,
        coordination: data.coordination ?? null,
        safetyBlock: data.safety_block ?? null,
        evidenceBundle: data.evidence_bundle ?? null,
        trace: data.trace_summary,
        planRevision: data.plan_revision ?? null,
        activeTask: data.active_task ?? null,
        taskTree: data.task_tree ?? [],
        executionState: data.execution_state ?? null,
        revisionDiff: data.revision_diff ?? null,
        criticVerdicts: data.critic_verdicts ?? [],
        replanReason: data.replan_reason ?? null
      });
      setLearningSummary([]);
      setSessionNote('');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const goToReview = () => {
    syncFrictionContext(currentSupport);
    onNavigate('review');
  };

  const handleScenarioSelectionChange = (value: string) => {
    setActivePreset(null);
    const nextSelection = resolveFrictionScenarioSelection(value);
    setScenarioSelection(nextSelection.scenarioSelection);
    if (nextSelection.scenario) {
      setScenario(nextSelection.scenario);
    }
    if (nextSelection.shouldResetCustomScenarioName) {
      setCustomScenarioName('');
    }
  };

  const pushSessionEvent = async (
    eventKind:
      | 'text_update'
      | 'audio_update'
      | 'status_check'
      | 'request_lighter'
      | 'request_handoff'
      | 'no_improvement'
      | 'support_arrived'
      | 'caregiver_overloaded'
      | 'child_escalating'
      | 'new_context_ingested'
  ) => {
    if (!session) return;
    setLoading(true);
    setError('');
    try {
      const response = await addFrictionSessionEventV3(token, session.session_id, {
        source_type:
          eventKind === 'audio_update'
            ? 'audio'
            : eventKind === 'text_update'
              ? 'text'
              : eventKind === 'new_context_ingested'
                ? 'document'
                : 'user_action',
        event_kind: eventKind,
        raw_text: sessionNote.trim()
      });
      applySessionState({
        session: response.session,
        risk: response.risk ?? currentRisk,
        emotion: response.emotion ?? currentEmotion,
        support: response.support ?? currentSupport,
        coordination: response.coordination ?? currentCoordination,
        safetyBlock: currentSafetyBlock,
        evidenceBundle: response.evidence_bundle ?? currentEvidenceBundle,
        trace: response.trace_summary.length ? response.trace_summary : traceSummary,
        planRevision: response.plan_revision ?? currentPlanRevision,
        activeTask: response.active_task ?? currentActiveTask,
        taskTree: response.task_tree?.length ? response.task_tree : currentTaskTree,
        executionState: response.execution_state ?? currentExecutionState,
        revisionDiff: response.revision_diff ?? currentRevisionDiff,
        criticVerdicts: response.critic_verdicts ?? currentCriticVerdicts,
        replanReason: response.replan_reason ?? currentReplanReason
      });
      if (response.replanned) {
        setSessionNote('');
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const confirmSessionAction = async (action: 'continue' | 'lighter' | 'handoff') => {
    if (!session) return;
    setLoading(true);
    setError('');
    try {
      const response = await confirmFrictionSessionV3(token, session.session_id, {
        action,
        note: sessionNote.trim()
      });
      applySessionState({
        session: response.session,
        risk: currentRisk,
        emotion: currentEmotion,
        support: response.support,
        coordination: response.coordination,
        safetyBlock: currentSafetyBlock,
        evidenceBundle: currentEvidenceBundle,
        trace: response.trace_summary.length ? response.trace_summary : traceSummary,
        planRevision: response.plan_revision ?? currentPlanRevision,
        activeTask: response.active_task ?? currentActiveTask,
        taskTree: response.task_tree?.length ? response.task_tree : currentTaskTree,
        executionState: response.execution_state ?? currentExecutionState,
        revisionDiff: response.revision_diff ?? currentRevisionDiff,
        criticVerdicts: response.critic_verdicts ?? currentCriticVerdicts,
        replanReason: response.replan_reason ?? currentReplanReason
      });
      if (action !== 'continue') {
        setSessionNote('');
      }
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const closeSession = async (effectiveness: 'helpful' | 'somewhat' | 'not_helpful') => {
    if (!session) return;
    setLoading(true);
    setError('');
    try {
      const response = await closeFrictionSessionV3(token, session.session_id, {
        effectiveness,
        child_state_after: effectiveness === 'helpful' ? 'settled' : effectiveness === 'somewhat' ? 'partly_settled' : 'still_escalating',
        caregiver_state_after: effectiveness === 'helpful' ? 'calmer' : effectiveness === 'somewhat' ? 'same' : 'more_overloaded',
        notes: sessionNote.trim()
      });
      setSession(response.session);
      setLearningSummary(response.learning_summary);
      setSessionNote('');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="content-page-shell scripts-page-shell">
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
            className={`preset-card ${scenarioSelection === CUSTOM_FRICTION_SCENARIO_VALUE ? 'active' : ''}`}
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

        <section className="multimodal-panel">
          <div className="focus-header">
            <div />
            {ingestions.length ? (
                  <button
                    className="chip-btn"
                    type="button"
                    onClick={() => {
                      setIngestions([]);
                      setDocumentFile(null);
                      setAudioFile(null);
                    }}
                  >
                    清空上下文
                  </button>
            ) : null}
          </div>

          <div className="grid two multimodal-grid">
            <label className="support-textarea">
              <span className="label">通知 / 作业 / 日程</span>
              <textarea
                className="input textarea"
                rows={4}
                value={documentText}
                onChange={(e) => setDocumentText(e.target.value)}
                placeholder="例如：学校通知，明天上午改去操场活动，数学作业两项，需要家长签字。"
              />
              <input
                className="input"
                type="file"
                accept=".jpg,.jpeg,.png,.heic,.pdf"
                onChange={(e) => setDocumentFile(e.target.files?.[0] ?? null)}
              />
              {documentFile ? <span className="muted">已选文件：{documentFile.name}</span> : null}
              <button
                className="btn secondary"
                type="button"
                onClick={() => submitIngestion('document')}
                disabled={importingSource === 'document'}
              >
                {importingSource === 'document' ? '导入中…' : '导入通知'}
              </button>
            </label>

            <label className="support-textarea">
              <span className="label">语音 / 摘要</span>
              <textarea
                className="input textarea"
                rows={4}
                value={audioText}
                onChange={(e) => setAudioText(e.target.value)}
                placeholder="例如：现场太吵，我很累，他一直说不要走，快点也没用。"
              />
              <input
                className="input"
                type="file"
                accept=".m4a,.mp3,.wav,.aac"
                onChange={(e) => setAudioFile(e.target.files?.[0] ?? null)}
              />
              {audioFile ? <span className="muted">已选文件：{audioFile.name}</span> : null}
              <button
                className="btn secondary"
                type="button"
                onClick={() => submitIngestion('audio')}
                disabled={importingSource === 'audio'}
              >
                {importingSource === 'audio' ? '导入中…' : '导入语音摘要'}
              </button>
            </label>
          </div>

          <p className="muted">已纳入 {includedIngestionIds.length} 条</p>

          {ingestions.length ? (
            <div className="multimodal-ingestion-list">
              {ingestions.map((item) => (
                <article key={item.ingestion_id} className="multimodal-card">
                  <div className="multimodal-card-head">
                    <span className="status-pill">{item.source_type === 'document' ? '文档' : '语音'}</span>
                    <strong>{item.content_name}</strong>
                    <span className="muted">置信度 {Math.round(item.confidence * 100)}%</span>
                    <span className="muted">{shouldAutoIncludeIngestion(item) ? '已纳入本次生成' : '仅参考，未纳入'}</span>
                  </div>
                  <p>{item.normalized_summary}</p>
                  <ul className="list compact-list">
                    {item.context_signals.map((signal) => (
                      <li key={`${item.ingestion_id}-${signal.signal_key}-${signal.signal_value}`}>
                        {signal.signal_label}：{signal.signal_value}
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          ) : null}
        </section>

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
                  <option value={CUSTOM_FRICTION_SCENARIO_VALUE}>+ 新场景</option>
                </select>
              </label>
              {scenarioSelection === CUSTOM_FRICTION_SCENARIO_VALUE ? (
                <label>
                  <span className="label">新场景名称</span>
                  <input
                    ref={customScenarioInputRef}
                    autoFocus
                    className="input"
                    value={customScenarioName}
                    onChange={(e) => setCustomScenarioName(e.target.value)}
                    placeholder="例如：电梯里、理发店、餐厅等位"
                  />
                  <span className="label">这里是在建立正式场景，不是下面那条现场备注。</span>
                </label>
              ) : null}
              {scenarioSelection === CUSTOM_FRICTION_SCENARIO_VALUE ? (
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

      {currentSafetyBlock ? (
        <SafetyBlockCard block={currentSafetyBlock} lowStim={lowStim} onToggleLowStim={onToggleLowStim} />
      ) : null}

      {!currentSafetyBlock && currentSupport ? (
        <>
          {session && currentCoordination && currentEmotion ? (
            <section className="panel support-action-panel">
              <div className="focus-header">
                <div>
                  <p className="eyebrow">会话式强建议</p>
                  <h3>现在先做这一步：{currentCoordination.now_step}</h3>
                  <p className="muted">
                    当前模式：{coordinationModeLabel[currentCoordination.active_mode]} · 会话版本 {session.current_state_version} ·{' '}
                    {session.next_check_in_hint}
                  </p>
                </div>
                <span className="status-pill">
                  风险 {currentRisk ? riskLevelLabel[currentRisk.risk_level] : '待判断'} / 孩子{' '}
                  {childEmotionLabel[currentEmotion.child_emotion]} / 家长 {caregiverEmotionLabel[currentEmotion.caregiver_emotion]}
                </span>
              </div>

              <div className="grid two">
                <article className="support-action-card">
                  <h4>为什么这样调</h4>
                  <p>{currentCoordination.summary}</p>
                  <blockquote className="quote-box">“{currentCoordination.now_script}”</blockquote>
                  <ul className="list compact-list">
                    {currentEmotion.reasoning.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
                <article className="support-action-card">
                  <h4>如果不行下一步</h4>
                  <p>{currentCoordination.next_if_not_working}</p>
                </article>
              </div>

              <label className="support-textarea">
                <span className="label">更新现场情况 / 语音摘要</span>
                <textarea
                  className="input textarea"
                  rows={3}
                  value={sessionNote}
                  onChange={(e) => setSessionNote(e.target.value)}
                  placeholder="例如：还是不肯动，开始捂耳朵；或：接手人已到场。"
                />
              </label>

              <div className="focus-actions">
                <button className="btn secondary" type="button" onClick={() => confirmSessionAction('continue')} disabled={loading}>
                  继续这个方案
                </button>
                <button className="btn secondary" type="button" onClick={() => confirmSessionAction('lighter')} disabled={loading}>
                  换更轻的
                </button>
                <button className="btn secondary" type="button" onClick={() => confirmSessionAction('handoff')} disabled={loading}>
                  需要交接
                </button>
                <button className="btn secondary" type="button" onClick={() => pushSessionEvent('text_update')} disabled={loading}>
                  更新现场情况
                </button>
                <button className="btn secondary" type="button" onClick={() => pushSessionEvent('status_check')} disabled={loading}>
                  3 分钟后复判
                </button>
                <button className="btn secondary" type="button" onClick={() => pushSessionEvent('no_improvement')} disabled={loading}>
                  还是没改善
                </button>
                <button className="btn secondary" type="button" onClick={() => pushSessionEvent('support_arrived')} disabled={loading}>
                  接手人已到场
                </button>
              </div>

              {learningSummary.length ? (
                <div className="support-personalized-panel">
                  <p className="eyebrow">本次已学习</p>
                  <ul className="list compact-list">
                    {learningSummary.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : (
                <div className="focus-actions">
                  <button className="chip-btn" type="button" onClick={() => closeSession('helpful')} disabled={loading || session.status === 'closed'}>
                    收尾并记录：有帮助
                  </button>
                  <button className="chip-btn" type="button" onClick={() => closeSession('somewhat')} disabled={loading || session.status === 'closed'}>
                    收尾并记录：一般
                  </button>
                  <button className="chip-btn" type="button" onClick={() => closeSession('not_helpful')} disabled={loading || session.status === 'closed'}>
                    收尾并记录：没帮助
                  </button>
                </div>
              )}
            </section>
          ) : null}

          {currentActiveTask && currentExecutionState ? (
            <section className="panel support-action-panel">
              <div className="focus-header">
                <div>
                  <p className="eyebrow">当前任务卡</p>
                  <h3>{currentActiveTask.goal}</h3>
                  <p className="muted">
                    第 {currentPlanRevision?.revision_no ?? session?.current_state_version ?? 1} 版 · 模式{' '}
                    {coordinationModeLabel[currentExecutionState.active_mode]}
                  </p>
                </div>
                <span className="status-pill">当前任务</span>
              </div>

              <div className="grid two">
                <article className="support-action-card">
                  <h4>现在做什么</h4>
                  <ul className="list compact-list">
                    {currentActiveTask.instructions.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                  <blockquote className="quote-box">“{currentActiveTask.say_this[0]}”</blockquote>
                </article>
                <article className="support-action-card">
                  <h4>如果无效怎么办</h4>
                  <p>{currentCoordination?.next_if_not_working ?? currentActiveTask.failure_signals[0]}</p>
                  <ul className="list compact-list">
                    {currentActiveTask.failure_signals.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </article>
              </div>
            </section>
          ) : null}

          {currentRevisionDiff || currentTaskTree.length ? (
            <section className="panel support-personalized-panel">
              <div className="focus-header">
                <div>
                  <p className="eyebrow">计划演化卡</p>
                  <h3>这次为什么改计划</h3>
                  <p className="muted">{currentReplanReason ?? currentRevisionDiff?.summary ?? '当前为初始任务树。'}</p>
                </div>
                <span className="status-pill">任务树</span>
              </div>

              {currentRevisionDiff ? (
                <div className="grid two">
                  <article className="support-action-card">
                    <h4>变更摘要</h4>
                    <ul className="list compact-list">
                      <li>触发源：{currentRevisionDiff.trigger.summary}</li>
                      <li>
                        当前任务变化：{formatTaskLabel(currentRevisionDiff.active_task_before, currentTaskTree)} →{' '}
                        {formatTaskLabel(currentRevisionDiff.active_task_after, currentTaskTree)}
                      </li>
                      <li>新增任务：{formatTaskList(currentRevisionDiff.added_task_ids, currentTaskTree)}</li>
                      <li>移除任务：{formatTaskList(currentRevisionDiff.dropped_task_ids, currentTaskTree)}</li>
                    </ul>
                  </article>
                  <article className="support-action-card">
                    <h4>复核结果</h4>
                    <ul className="list compact-list">
                      {currentCriticVerdicts.map((item) => (
                        <li key={`${item.critic}-${item.summary}`}>
                          {criticLabel[item.critic]}：{criticDecisionLabel[item.decision]} · {item.summary}
                        </li>
                      ))}
                    </ul>
                  </article>
                </div>
              ) : null}

              {currentTaskTree.length ? (
                <div className="support-action-grid balanced-card-grid cols-3">
                  {currentTaskTree.map((item, index) => (
                    <article key={item.task_id} className="support-action-card">
                      <span className="status-pill">{taskStatusLabel[item.status]}</span>
                      <h4>{`任务 ${index + 1}`}</h4>
                      <p>{item.goal}</p>
                      <p className="muted">任务类型：{taskKindLabel[item.kind]} · 层级 {item.depth}</p>
                      <p className="muted">下一步备选：{formatTaskList(item.fallback_task_ids, currentTaskTree)}</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}

          <FrictionCrisisCard
            plan={currentSupport}
            riskLevel={currentRisk?.risk_level}
            lowStim={lowStim}
            onToggleLowStim={onToggleLowStim}
          />

          <section className="panel support-action-panel">
            <div className="focus-header">
              <div>
                <p className="eyebrow">三步行动卡</p>
                <h3>不只告诉你做什么，也说明为什么先做这一步</h3>
              </div>
            </div>

            <div className="support-action-grid balanced-card-grid cols-3">
              {currentSupport.action_plan.map((item, index) => (
                <article key={`${item.title}-${index}`} className="support-action-card">
                  <span className="status-pill">{`步骤 ${index + 1}`}</span>
                  <h4>{item.title}</h4>
                  <p>{item.action}</p>
                  <blockquote className="quote-box">“{item.parent_script}”</blockquote>
                  <p className="muted">为什么先这样做：{item.why_it_fits}</p>
                </article>
              ))}
            </div>
          </section>

          <section className="panel support-personalized-panel">
            <div className="focus-header">
              <div>
                <p className="eyebrow">个性化提醒</p>
                <h3>结合家庭档案补充注意点</h3>
              </div>
              <span className="status-pill">按家庭档案</span>
            </div>
            <ul className="list compact-list">
              {currentSupport.personalized_strategies.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </section>

          <section className="panel support-handoff-panel">
            <div className="focus-header">
              <div>
                <p className="eyebrow">协同接手</p>
                <h3>同步给家长、老师或其他照护者的版本</h3>
              </div>
              <span className="status-pill">多角色输出</span>
            </div>

            <div className="support-handoff-grid balanced-card-grid cols-2">
              {currentSupport.handoff_messages.map((item) => (
                <article key={`${item.target}-${item.text}`} className="support-handoff-card">
                  <p className="eyebrow">{handoffTargetLabel[item.target]}</p>
                  <blockquote className="quote-box">{item.text}</blockquote>
                </article>
              ))}
            </div>

            {hasSchoolCollaborationMessage(currentSupport.school_message) ? (
              <p className="muted support-citation">策略卡引用：{currentSupport.citations.join(', ')}</p>
            ) : null}
          </section>

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
            <p>{currentSupport.feedback_prompt}</p>
            <p className="muted">轻复盘里只补结果、触发器和下次保留的一件事，避免在这里再填一遍。</p>
          </section>
        </>
      ) : null}

        {error ? <div className="panel error">{error}</div> : null}
      </div>
    </div>
  );
}
