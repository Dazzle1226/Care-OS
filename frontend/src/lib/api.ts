import type {
  CheckinResponse,
  CheckinTodayStatus,
  FamilyRead,
  FrictionSupportFeedbackResponse,
  FrictionSupportGenerateResponse,
  MicroRespiteFeedbackResponse,
  MicroRespiteGenerateResponse,
  MultimodalIngestionResponse,
  MonthlyReport,
  OnboardingSetupPayload,
  OnboardingSummary,
  ReportFeedbackResponse,
  ScriptGenerateResponse,
  TrainingDashboard,
  TrainingDomainDetail,
  TrainingFeedbackResponse,
  TrainingReminderResponse,
  V2FrictionSupportGenerateResponse,
  V3FrictionSessionCloseResponse,
  V3FrictionSessionConfirmResponse,
  V3FrictionSessionEventResponse,
  V3FrictionSessionStartResponse,
  V3TrainingSessionCloseResponse,
  V3TrainingSessionEventResponse,
  V3TrainingSessionStartResponse,
  WeeklyReport
} from './types';

function normalizeApiBase(value: string) {
  return value.replace(/\/+$/, '');
}

export function resolveApiBase(
  explicitBase = import.meta.env?.VITE_API_BASE_URL,
  locationLike:
    | Pick<Location, 'hostname' | 'origin' | 'port' | 'protocol'>
    | { hostname: string; origin: string; port: string; protocol: string }
    | undefined = typeof window !== 'undefined' ? window.location : undefined
) {
  const trimmedBase = explicitBase?.trim();
  if (trimmedBase) return normalizeApiBase(trimmedBase);

  if (!locationLike) {
    return 'http://localhost:8000/api';
  }

  if (locationLike.port === '5173') {
    return '/api';
  }

  if (locationLike.port === '4173') {
    return normalizeApiBase(`${locationLike.protocol}//${locationLike.hostname}:8000/api`);
  }

  return normalizeApiBase(`${locationLike.origin}/api`);
}

const API_BASE = resolveApiBase();
export const FAMILY_MISSING_EVENT = 'care-os:family-missing';

type Method = 'GET' | 'POST';
type RequestOptions = {
  timeoutMs?: number;
};

export class ApiError extends Error {
  status: number;
  statusText: string;
  detail?: string;
  bodyText: string;

  constructor(params: { message: string; status: number; statusText: string; detail?: string; bodyText: string }) {
    super(params.message);
    this.name = 'ApiError';
    this.status = params.status;
    this.statusText = params.statusText;
    this.detail = params.detail;
    this.bodyText = params.bodyText;
  }
}

function parseErrorDetail(text: string) {
  if (!text) return undefined;

  try {
    const parsed = JSON.parse(text) as { detail?: unknown };
    return typeof parsed.detail === 'string' ? parsed.detail : undefined;
  } catch {
    return undefined;
  }
}

export function isFamilyNotFoundError(error: unknown) {
  if (error instanceof ApiError) {
    return error.status === 404 && error.detail === 'Family not found';
  }

  return error instanceof Error && error.message.includes('Family not found');
}

export function getUserFacingApiError(error: unknown, fallbackMessage: string) {
  if (error instanceof ApiError) {
    return error.detail?.trim() || fallbackMessage;
  }

  if (error instanceof Error) {
    return error.message?.trim() || fallbackMessage;
  }

  return fallbackMessage;
}

export function getNetworkErrorMessage(error: unknown) {
  if (!(error instanceof Error)) return null;

  if (error.name === 'AbortError') {
    return '请求超时：本地后端响应过慢。请确认后端已启动完成后重试。';
  }

  if (error instanceof TypeError) {
    return '无法连接本地后端服务。请确认 http://localhost:8000 已启动，或检查 VITE_API_BASE_URL / Vite 代理配置。';
  }

  return null;
}

async function buildApiError(resp: Response) {
  const text = await resp.text();
  const detail = parseErrorDetail(text);
  const message = detail ? `${resp.status} ${resp.statusText}: ${detail}` : `${resp.status} ${resp.statusText}: ${text}`;

  const error = new ApiError({
    message,
    status: resp.status,
    statusText: resp.statusText,
    detail,
    bodyText: text
  });

  if (isFamilyNotFoundError(error) && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(FAMILY_MISSING_EVENT, { detail: { message } }));
  }

  return error;
}

async function request<T>(path: string, method: Method, token?: string, body?: unknown, options?: RequestOptions): Promise<T> {
  const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;
  const timeoutMs = options?.timeoutMs ?? null;
  const timeoutId =
    controller && timeoutMs
      ? globalThis.setTimeout(() => {
          controller.abort();
        }, timeoutMs)
      : null;

  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {})
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller?.signal
    });
  } catch (error) {
    if (timeoutId !== null) globalThis.clearTimeout(timeoutId);
    const message = getNetworkErrorMessage(error);
    if (message) {
      throw new Error(message);
    }
    throw error;
  }

  if (timeoutId !== null) globalThis.clearTimeout(timeoutId);

  if (!resp.ok) {
    throw await buildApiError(resp);
  }
  return (await resp.json()) as T;
}

async function requestFormData<T>(path: string, token: string, body: FormData): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`
    },
    body
  });

  if (!resp.ok) {
    throw await buildApiError(resp);
  }
  return (await resp.json()) as T;
}

export async function login(identifier: string) {
  return request<{ access_token: string; user_id: number }>('/auth/login', 'POST', undefined, {
    identifier,
    role: 'caregiver',
    locale: 'zh-CN'
  });
}

export async function createFamily(token: string, name: string): Promise<FamilyRead> {
  return request<FamilyRead>('/family', 'POST', token, { name, timezone: 'Asia/Shanghai' });
}

export async function completeOnboarding(
  token: string,
  payload: OnboardingSetupPayload
): Promise<OnboardingSummary> {
  return request<OnboardingSummary>('/onboarding/setup', 'POST', token, payload);
}

export async function getOnboardingFamily(
  token: string,
  familyId: number,
  options?: RequestOptions
): Promise<OnboardingSummary> {
  return request<OnboardingSummary>(`/onboarding/family/${familyId}`, 'GET', token, undefined, options);
}

export async function upsertProfile(token: string, payload: Record<string, unknown>) {
  return request('/profile', 'POST', token, payload);
}

export async function postCheckin(token: string, payload: Record<string, unknown>): Promise<CheckinResponse> {
  return request<CheckinResponse>('/checkin', 'POST', token, payload);
}

export async function getTodayCheckin(
  token: string,
  familyId: number,
  date: string
): Promise<CheckinTodayStatus> {
  return request<CheckinTodayStatus>(`/checkin/today/${familyId}?date=${date}`, 'GET', token);
}

export async function generateMicroRespite(
  token: string,
  payload: Record<string, unknown>
): Promise<MicroRespiteGenerateResponse> {
  return request<MicroRespiteGenerateResponse>('/respite/generate', 'POST', token, payload);
}

export async function submitMicroRespiteFeedback(
  token: string,
  payload: Record<string, unknown>
): Promise<MicroRespiteFeedbackResponse> {
  return request<MicroRespiteFeedbackResponse>('/respite/feedback', 'POST', token, payload);
}

export async function generateScript(token: string, payload: Record<string, unknown>): Promise<ScriptGenerateResponse> {
  return request<ScriptGenerateResponse>('/scripts/generate', 'POST', token, payload);
}

export async function generateFrictionSupport(
  token: string,
  payload: Record<string, unknown>
): Promise<FrictionSupportGenerateResponse> {
  return request<FrictionSupportGenerateResponse>('/scripts/friction-support', 'POST', token, payload);
}

export async function generateFrictionSupportV2(
  token: string,
  payload: Record<string, unknown>
): Promise<V2FrictionSupportGenerateResponse> {
  return request<V2FrictionSupportGenerateResponse>('/v2/scripts/friction-support', 'POST', token, payload);
}

export async function startFrictionSessionV3(
  token: string,
  payload: Record<string, unknown>
): Promise<V3FrictionSessionStartResponse> {
  return request<V3FrictionSessionStartResponse>('/v3/friction-sessions/start', 'POST', token, payload);
}

export async function addFrictionSessionEventV3(
  token: string,
  sessionId: number,
  payload: Record<string, unknown>
): Promise<V3FrictionSessionEventResponse> {
  return request<V3FrictionSessionEventResponse>(`/v3/friction-sessions/${sessionId}/events`, 'POST', token, payload);
}

export async function confirmFrictionSessionV3(
  token: string,
  sessionId: number,
  payload: Record<string, unknown>
): Promise<V3FrictionSessionConfirmResponse> {
  return request<V3FrictionSessionConfirmResponse>(`/v3/friction-sessions/${sessionId}/confirm`, 'POST', token, payload);
}

export async function closeFrictionSessionV3(
  token: string,
  sessionId: number,
  payload: Record<string, unknown>
): Promise<V3FrictionSessionCloseResponse> {
  return request<V3FrictionSessionCloseResponse>(`/v3/friction-sessions/${sessionId}/close`, 'POST', token, payload);
}

export async function ingestDocument(
  token: string,
  payload: Record<string, unknown>
): Promise<MultimodalIngestionResponse> {
  return request<MultimodalIngestionResponse>('/v2/ingestions/document', 'POST', token, payload);
}

export async function ingestAudio(
  token: string,
  payload: Record<string, unknown>
): Promise<MultimodalIngestionResponse> {
  return request<MultimodalIngestionResponse>('/v2/ingestions/audio', 'POST', token, payload);
}

export async function uploadDocumentFile(token: string, payload: FormData): Promise<MultimodalIngestionResponse> {
  return requestFormData<MultimodalIngestionResponse>('/v2/ingestions/document-file', token, payload);
}

export async function uploadAudioFile(token: string, payload: FormData): Promise<MultimodalIngestionResponse> {
  return requestFormData<MultimodalIngestionResponse>('/v2/ingestions/audio-file', token, payload);
}

export async function getCurrentTrainingPlan(token: string, familyId: number): Promise<TrainingDashboard> {
  return request<TrainingDashboard>(`/training/current/${familyId}`, 'GET', token);
}

export async function generateTrainingPlan(
  token: string,
  payload: Record<string, unknown>
): Promise<TrainingDashboard> {
  return request<TrainingDashboard>('/training/generate', 'POST', token, payload);
}

export async function submitTrainingFeedback(
  token: string,
  payload: Record<string, unknown>
): Promise<TrainingFeedbackResponse> {
  return request<TrainingFeedbackResponse>('/training/feedback', 'POST', token, payload);
}

export async function getTrainingDomainDetail(
  token: string,
  familyId: number,
  areaKey: string
): Promise<TrainingDomainDetail> {
  return request<TrainingDomainDetail>(`/training/domain/${familyId}/${areaKey}`, 'GET', token);
}

export async function scheduleTrainingReminder(
  token: string,
  payload: Record<string, unknown>
): Promise<TrainingReminderResponse> {
  return request<TrainingReminderResponse>('/training/reminder', 'POST', token, payload);
}

export async function startTrainingSessionV3(
  token: string,
  payload: Record<string, unknown>
): Promise<V3TrainingSessionStartResponse> {
  return request<V3TrainingSessionStartResponse>('/v3/training-sessions/start', 'POST', token, payload);
}

export async function addTrainingSessionEventV3(
  token: string,
  sessionId: number,
  payload: Record<string, unknown>
): Promise<V3TrainingSessionEventResponse> {
  return request<V3TrainingSessionEventResponse>(`/v3/training-sessions/${sessionId}/events`, 'POST', token, payload);
}

export async function closeTrainingSessionV3(
  token: string,
  sessionId: number,
  payload: Record<string, unknown>
): Promise<V3TrainingSessionCloseResponse> {
  return request<V3TrainingSessionCloseResponse>(`/v3/training-sessions/${sessionId}/close`, 'POST', token, payload);
}

export async function submitFrictionSupportFeedback(
  token: string,
  payload: Record<string, unknown>
): Promise<FrictionSupportFeedbackResponse> {
  return request<FrictionSupportFeedbackResponse>('/scripts/friction-support/feedback', 'POST', token, payload);
}

export async function submitReview(token: string, payload: Record<string, unknown>) {
  return request('/review', 'POST', token, payload);
}

export async function getWeeklyReport(token: string, familyId: number, weekStart: string): Promise<WeeklyReport> {
  return request<WeeklyReport>(`/report/weekly/${familyId}?week_start=${weekStart}`, 'GET', token);
}

export async function getMonthlyReport(token: string, familyId: number, monthStart: string): Promise<MonthlyReport> {
  return request<MonthlyReport>(`/report/monthly/${familyId}?month_start=${monthStart}`, 'GET', token);
}

export async function submitReportFeedback(
  token: string,
  payload: Record<string, unknown>
): Promise<ReportFeedbackResponse> {
  return request<ReportFeedbackResponse>('/report/feedback', 'POST', token, payload);
}

export async function exportSupportCard(token: string, familyId: number, format: 'pdf' | 'png') {
  return request<{ family_id: number; format: 'pdf' | 'png'; content: Record<string, unknown> }>(
    '/supportcard/export',
    'POST',
    token,
    { family_id: familyId, format }
  );
}
