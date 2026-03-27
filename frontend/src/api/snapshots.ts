import client from './client'

export interface SnapshotSummary {
  id: string
  platform: string
  search_params: Record<string, unknown>
  total_kols: number
  created_by: string
  created_at: string
  label: string
  keywords_summary: string[]
  keywords_total: number
}

export interface SnapshotDetail {
  snapshot_id: string
  platform: string
  kols: Record<string, unknown>[]
  total: number
  search_params: Record<string, string | string[]>
}

export interface DiffResult {
  platform: string
  total_old: number
  total_new: number
  new_kols: Record<string, unknown>[]
  lost_kols: Record<string, unknown>[]
  grown_kols: { kol: Record<string, unknown>; old_count: number; growth: number }[]
  report_path: string
}

export async function listSnapshots(platform?: string): Promise<SnapshotSummary[]> {
  const params = platform ? { platform } : {}
  const { data } = await client.get<SnapshotSummary[]>('/api/snapshots', { params })
  return data
}

export async function getSnapshot(id: string): Promise<SnapshotDetail> {
  const { data } = await client.get<SnapshotDetail>(`/api/snapshots/${id}`)
  return data
}

export async function deleteSnapshot(id: string): Promise<void> {
  await client.delete(`/api/snapshots/${id}`)
}

export async function diffSnapshots(platform: string, oldId: string, newId: string): Promise<DiffResult> {
  const { data } = await client.post<DiffResult>('/api/snapshots/diff', {
    platform,
    old_id: oldId,
    new_id: newId,
  })
  return data
}
