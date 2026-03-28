import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getTaskState } from '../api/discover'
import { downloadReport } from '../api/reports'

interface SSEData {
  type: 'log' | 'done' | 'error'
  message?: string
  status?: string
  summary?: Record<string, unknown>
  snapshot_id?: string
  report_paths?: Record<string, string>
  error?: string
}

export default function TaskProgressPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const [logs, setLogs] = useState<string[]>([])
  const [status, setStatus] = useState<string>('loading')
  const [taskType, setTaskType] = useState<string>('youtube')
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null)
  const [snapshotId, setSnapshotId] = useState('')
  const [reportPaths, setReportPaths] = useState<Record<string, string>>({})
  const [error, setError] = useState('')
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!taskId) return

    getTaskState(taskId)
      .then((task) => {
        setTaskType(task.task_type)
        if (task.status === 'completed' || task.status === 'failed') {
          setStatus(task.status)
          setLogs(task.logs)
          setSummary(task.result_summary as Record<string, unknown>)
          setSnapshotId((task.result_summary as Record<string, unknown>)?.snapshot_id as string || '')
          setReportPaths(task.report_paths)
          if (task.error) setError(task.error)
          return
        }

        setStatus('running')
        setLogs(task.logs)

        const token = localStorage.getItem('access_token')
        const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
        const url = `${baseUrl}/api/tasks/${taskId}/stream?token=${encodeURIComponent(token || '')}`
        const es = new EventSource(url)

        es.onmessage = (event) => {
          try {
            const data: SSEData = JSON.parse(event.data)
            if (data.type === 'log') {
              setLogs((prev) => [...prev, data.message || ''])
            } else if (data.type === 'done') {
              setStatus(data.status || 'completed')
              if (data.summary) setSummary(data.summary)
              if (data.snapshot_id) setSnapshotId(data.snapshot_id)
              if (data.report_paths) setReportPaths(data.report_paths)
              if (data.error) setError(data.error)
              es.close()
            } else if (data.type === 'error') {
              setError(data.message || '未知错误')
              setStatus('failed')
              es.close()
            }
          } catch { /* ignore parse errors */ }
        }

        es.onerror = () => { es.close() }

        return () => es.close()
      })
      .catch(() => setStatus('not_found'))
  }, [taskId])

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight
    }
  }, [logs])

  if (status === 'loading') {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  if (status === 'not_found') {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
        <p className="text-gray-500">任务不存在或已过期</p>
        <Link to="/discover" className="text-blue-600 hover:underline text-sm mt-2 inline-block">返回搜索</Link>
      </div>
    )
  }

  const xlsxFile = reportPaths?.xlsx?.split('/').pop()
  const csvFile = reportPaths?.csv?.split('/').pop()

  return (
    <>
      <div className="mb-6 flex items-center space-x-3">
        <Link to="/dashboard" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <h2 className="text-2xl font-bold text-gray-900">任务进度</h2>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              taskType === 'youtube' ? 'bg-red-100 text-red-700' : 'bg-pink-100 text-pink-700'
            }`}>
              {taskType === 'youtube' ? 'YouTube' : 'Instagram'}
            </span>
            <span className="inline-flex items-center text-sm">
              {status === 'running' && <><span className="w-2.5 h-2.5 rounded-full mr-2 animate-pulse bg-blue-500" />运行中</>}
              {status === 'completed' && <><span className="w-2.5 h-2.5 rounded-full mr-2 bg-green-500" />已完成</>}
              {status === 'failed' && <><span className="w-2.5 h-2.5 rounded-full mr-2 bg-red-500" />失败</>}
            </span>
          </div>
          {status === 'completed' && (
            <div className="space-x-3">
              {snapshotId && (
                <Link to={`/snapshots/${snapshotId}`} className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition">
                  查看快照
                </Link>
              )}
              {xlsxFile && (
                <button onClick={() => downloadReport(xlsxFile)} className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition">
                  下载 Excel
                </button>
              )}
              {csvFile && (
                <button onClick={() => downloadReport(csvFile)} className="px-4 py-2 border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm rounded-lg transition">
                  下载 CSV
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {status === 'completed' && summary && (
        <div className="space-y-4 mb-6">
          <div className="bg-green-50 border border-green-200 rounded-xl p-5">
            <h4 className="font-semibold text-green-800 mb-2">搜索完成</h4>
            <div className="text-sm text-green-700 space-y-1">
              <p>
                共发现 {String(summary.total || 0)} 个 KOL
                {summary.rule_passed != null && ` (规则筛选 ${summary.rule_passed} → AI 精筛 ${summary.llm_passed ?? summary.total})`}
                {summary.quota_used != null && `，Quota 已用 ${summary.quota_used}`}
                {summary.api_calls != null && `，API 调用 ${summary.api_calls} 次`}
                {summary.cost != null && `，费用 $${summary.cost}`}
              </p>
              {summary.llm_rejected != null && summary.llm_rejected > 0 && (
                <p className="text-green-600">AI 淘汰 {summary.llm_rejected} 个不符合条件的候选人</p>
              )}
            </div>
          </div>
          {summary.llm_summary && (
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-5">
              <div className="flex items-center mb-2">
                <svg className="w-4 h-4 text-blue-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <h4 className="font-semibold text-blue-800 text-sm">AI 分析摘要</h4>
              </div>
              <p className="text-sm text-blue-700">{String(summary.llm_summary)}</p>
            </div>
          )}
        </div>
      )}

      {status === 'failed' && error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-5 mb-6">
          <h4 className="font-semibold text-red-800 mb-2">任务失败</h4>
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900">实时日志</h3>
          <span className="text-xs text-gray-400">{logs.length} 条</span>
        </div>
        <div ref={logRef} className="p-4 font-mono text-sm bg-gray-900 text-gray-300 rounded-b-xl overflow-y-auto" style={{ maxHeight: 500, minHeight: 200 }}>
          {logs.map((line, i) => (
            <div key={i} className="py-0.5">{line}</div>
          ))}
          {status === 'running' && <div className="animate-pulse text-green-400">_</div>}
        </div>
      </div>
    </>
  )
}
