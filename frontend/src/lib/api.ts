import type {
  CheckinResponse,
  CheckinTodayStatus,
  FamilyRead,
  FrictionSupportFeedbackResponse,
  FrictionSupportGenerateResponse,
  MicroRespiteFeedbackResponse,
  MicroRespiteGenerateResponse,
  MonthlyReport,
  OnboardingSetupPayload,
  OnboardingSummary,
  ReportFeedbackResponse,
  ScriptGenerateResponse,
  TrainingDashboard,
  TrainingDomainDetail,
  TrainingFeedbackResponse,
  TrainingReminderResponse,
  WeeklyReport
} from './types';

const API_BASE = import.meta.env?.VITE_API_BASE_URL ?? 'http://localhost:8000/api';
export const FAMILY_MISSING_EVENT = 'care-os:family-missing';

type Method = 'GET' | 'POST';

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

async function request<T>(path: string, method: Method, token?: string, body?: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    },
    body: body ? JSON.stringify(body) : undefined
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

export async function getOnboardingFamily(token: string, familyId: number): Promise<OnboardingSummary> {
  return request<OnboardingSummary>(`/onboarding/family/${familyId}`, 'GET', token);
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

export async function exportWeeklyReport(token: string, familyId: number, weekStart: string) {
  return request('/report/export', 'POST', token, { family_id: familyId, week_start: weekStart });
}

export async function exportSupportCard(token: string, familyId: number, format: 'pdf' | 'png') {
  return request<{ family_id: number; format: 'pdf' | 'png'; content: Record<string, unknown> }>(
    '/supportcard/export',
    'POST',
    token,
    { family_id: familyId, format }
  );
}
