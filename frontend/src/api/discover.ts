import client from './client'

export interface DashboardStats {
  yt_snapshot_count: number
  ig_snapshot_count: number
  threads_snapshot_count: number
  running_tasks: number
  completed_today: number
  tasks: TaskItem[]
}

export interface TaskItem {
  task_id: string
  task_type: string
  status: string
  logs: string[]
  report_paths: Record<string, string>
  result_summary: Record<string, unknown>
  error: string
  created_at: number
  created_at_display?: string
}

export interface Keywords {
  core: string[]
  extended: string[]
  long_tail: string[]
}

export interface LLMOption {
  id: string
  label: string
}

export interface LLMOptions {
  kol_types: LLMOption[]
  exclude_types: LLMOption[]
  audiences: LLMOption[]
}

export interface LLMCriteria {
  kol_types: string[]
  exclude_types: string[]
  audience: string
  custom_requirements: string
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await client.get<DashboardStats>('/api/dashboard/stats')
  return data
}

export async function getKeywords(): Promise<Keywords> {
  const { data } = await client.get<Keywords>('/api/discover/keywords')
  return data
}

export async function getIGKeywords(): Promise<{ keywords: string[] }> {
  const { data } = await client.get<{ keywords: string[] }>('/api/discover/ig-keywords')
  return data
}

export async function getLLMOptions(): Promise<LLMOptions> {
  const { data } = await client.get<LLMOptions>('/api/discover/llm-options')
  return data
}

export async function submitYoutube(params: {
  selected_keywords: string
  custom_keywords: string
  min_subscribers: number
  max_subscribers: number
  depth: string
  max_inactive_days: number
  llm_criteria: LLMCriteria | null
}): Promise<{ task_id: string }> {
  const { data } = await client.post('/api/discover/youtube', params)
  return data
}

export async function submitInstagram(params: {
  selected_keywords: string
  custom_keywords: string
  min_followers: number
  max_followers: number
  llm_criteria: LLMCriteria | null
}): Promise<{ task_id: string }> {
  const { data } = await client.post('/api/discover/instagram', params)
  return data
}

export async function getThreadsKeywords(): Promise<{ keywords: string[] }> {
  const { data } = await client.get<{ keywords: string[] }>('/api/discover/threads-keywords')
  return data
}

export async function submitThreads(params: {
  selected_keywords: string
  custom_keywords: string
  min_followers: number
  max_followers: number
  llm_criteria: LLMCriteria | null
}): Promise<{ task_id: string }> {
  const { data } = await client.post('/api/discover/threads', params)
  return data
}

export async function getTaskState(taskId: string): Promise<TaskItem> {
  const { data } = await client.get<TaskItem>(`/api/tasks/${taskId}`)
  return data
}

export interface HealthCheckResult {
  youtube: { ok: boolean; status?: number; keys?: number; error?: string }
  tikhub: { ok: boolean; status?: number; error?: string }
  llm: { ok: boolean; status?: number; model?: string; error?: string }
}

export async function runHealthCheck(): Promise<HealthCheckResult> {
  const { data } = await client.get<HealthCheckResult>('/api/discover/health-check')
  return data
}
