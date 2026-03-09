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
  PlanGenerateResponse,
  ReportFeedbackResponse,
  ScriptGenerateResponse,
  TrainingFeedbackResponse,
  TrainingPlan,
  WeeklyReport
} from './types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api';

type Method = 'GET' | 'POST';

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
    const text = await resp.text();
    throw new Error(`${resp.status} ${resp.statusText}: ${text}`);
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

export async function generatePlan(token: string, payload: Record<string, unknown>): Promise<PlanGenerateResponse> {
  return request<PlanGenerateResponse>('/plan48h/generate', 'POST', token, payload);
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

export async function getCurrentTrainingPlan(token: string, familyId: number): Promise<TrainingPlan> {
  return request<TrainingPlan>(`/training/current/${familyId}`, 'GET', token);
}

export async function generateTrainingPlan(
  token: string,
  payload: Record<string, unknown>
): Promise<TrainingPlan> {
  return request<TrainingPlan>('/training/generate', 'POST', token, payload);
}

export async function submitTrainingFeedback(
  token: string,
  payload: Record<string, unknown>
): Promise<TrainingFeedbackResponse> {
  return request<TrainingFeedbackResponse>('/training/feedback', 'POST', token, payload);
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
