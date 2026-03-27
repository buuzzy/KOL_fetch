import client from './client'

export interface DashboardStats {
  yt_snapshot_count: number
  ig_snapshot_count: number
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

export async function getDashboardStats(): Promise<DashboardStats> {
  const { data } = await client.get<DashboardStats>('/api/dashboard/stats')
  return data
}

export async function getKeywords(): Promise<Keywords> {
  const { data } = await client.get<Keywords>('/api/discover/keywords')
  return data
}

export async function submitYoutube(params: {
  selected_keywords: string
  custom_keywords: string
  min_subscribers: number
  max_subscribers: number
  depth: string
  max_inactive_days: number
}): Promise<{ task_id: string }> {
  const { data } = await client.post('/api/discover/youtube', params)
  return data
}

export async function submitInstagram(params: {
  selected_keywords: string
  custom_keywords: string
  min_followers: number
  max_followers: number
}): Promise<{ task_id: string }> {
  const { data } = await client.post('/api/discover/instagram', params)
  return data
}

export async function getTaskState(taskId: string): Promise<TaskItem> {
  const { data } = await client.get<TaskItem>(`/api/tasks/${taskId}`)
  return data
}
