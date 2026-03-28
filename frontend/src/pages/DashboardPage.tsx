import { Link, useSearchParams, Navigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDashboardStats } from '../api/discover'

const STATUS_MAP: Record<string, { dot: string; text: string; label: string }> = {
  completed: { dot: 'bg-green-500', text: 'text-green-600', label: '已完成' },
  running: { dot: 'bg-blue-500 animate-pulse', text: 'text-blue-600', label: '运行中' },
  failed: { dot: 'bg-red-500', text: 'text-red-600', label: '失败' },
  pending: { dot: 'bg-gray-400', text: 'text-gray-500', label: '等待中' },
}

export default function DashboardPage() {
  const [searchParams] = useSearchParams()
  const platformParam = searchParams.get('platform')
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: getDashboardStats })

  if (platformParam && ['youtube', 'instagram', 'threads'].includes(platformParam)) {
    return <Navigate to={`/discover?platform=${platformParam}`} replace />
  }

  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  return (
    <>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">工作台</h2>
        <p className="text-gray-500 mt-1">概览与近期任务</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
        {[
          { label: 'YouTube 快照', value: data.yt_snapshot_count, color: 'text-gray-900' },
          { label: 'Instagram 快照', value: data.ig_snapshot_count, color: 'text-gray-900' },
          { label: 'Threads 快照', value: data.threads_snapshot_count, color: 'text-gray-900' },
          { label: '运行中任务', value: data.running_tasks, color: 'text-blue-600' },
          { label: '今日已完成', value: data.completed_today, color: 'text-green-600' },
        ].map((card) => (
          <div key={card.label} className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <p className="text-sm text-gray-500">{card.label}</p>
            <p className={`text-2xl font-bold mt-1 ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Link
          to="/discover?platform=youtube"
          className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 hover:shadow-md transition group"
        >
          <div className="flex items-center">
            <div className="w-12 h-12 bg-red-50 rounded-lg flex items-center justify-center mr-4">
              <svg className="w-6 h-6 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                <path d="M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 group-hover:text-red-600 transition">YouTube 博主发现</h3>
              <p className="text-sm text-gray-500 mt-0.5">搜索港澳财经 YouTube 频道</p>
            </div>
          </div>
        </Link>
        <Link
          to="/discover?platform=instagram"
          className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 hover:shadow-md transition group"
        >
          <div className="flex items-center">
            <div className="w-12 h-12 bg-pink-50 rounded-lg flex items-center justify-center mr-4">
              <svg className="w-6 h-6 text-pink-500" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12s.014 3.668.072 4.948c.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24s3.668-.014 4.948-.072c4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948s-.014-3.667-.072-4.947c-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 group-hover:text-pink-600 transition">Instagram 博主发现</h3>
              <p className="text-sm text-gray-500 mt-0.5">搜索港澳财经 IG 博主</p>
            </div>
          </div>
        </Link>
        <Link
          to="/discover?platform=threads"
          className="bg-white rounded-xl shadow-sm p-6 border border-gray-100 hover:shadow-md transition group"
        >
          <div className="flex items-center">
            <div className="w-12 h-12 bg-gray-100 rounded-lg flex items-center justify-center mr-4">
              <svg className="w-6 h-6 text-gray-900" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-1.104-3.96-3.898-5.984-8.304-6.015-2.91.022-5.11.936-6.54 2.717C4.307 6.504 3.616 8.914 3.59 12c.025 3.083.717 5.5 2.057 7.164 1.43 1.783 3.631 2.698 6.54 2.717 2.623-.02 4.358-.631 5.8-2.045 1.647-1.613 1.618-3.593 1.09-4.798-.31-.71-.873-1.3-1.634-1.75-.192 1.352-.622 2.446-1.278 3.255-.892 1.1-2.14 1.701-3.652 1.761h-.1c-1.268-.05-2.315-.542-3.03-1.424-.612-.756-.94-1.74-.95-2.848-.022-2.376 1.693-4.2 3.99-4.246h.07c.856.012 1.63.228 2.305.643.06-.396.09-.8.09-1.063 0-.163-.004-.39-.01-.59l-.006-.175 2.118-.025.007.238c.013.442.02.89.003 1.387-.018.495-.063 1.122-.188 1.725.65.507 1.2 1.112 1.614 1.806.776 1.291 1.06 2.878.801 4.468-.357 2.187-1.526 3.907-3.381 4.983-1.577.913-3.6 1.417-5.847 1.417zm.08-12.716c-1.2.04-2.032.98-2.015 2.274.008.72.197 1.295.548 1.663.375.393.904.6 1.53.6h.05c.964-.035 1.667-.461 2.148-1.303.376-.66.614-1.547.704-2.634-.536-.323-1.166-.528-1.882-.572-.028-.002-.055-.017-.083-.028z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 group-hover:text-gray-700 transition">Threads 博主发现</h3>
              <p className="text-sm text-gray-500 mt-0.5">搜索港澳财经 Threads 博主</p>
            </div>
          </div>
        </Link>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="px-6 py-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-900">近期任务</h3>
        </div>
        {data.tasks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-6 py-3 text-left">平台</th>
                  <th className="px-6 py-3 text-left">状态</th>
                  <th className="px-6 py-3 text-left">结果</th>
                  <th className="px-6 py-3 text-left">时间</th>
                  <th className="px-6 py-3 text-left">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.tasks.map((task) => {
                  const s = STATUS_MAP[task.status] || STATUS_MAP.pending
                  return (
                    <tr key={task.task_id} className="hover:bg-gray-50">
                      <td className="px-6 py-3">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          task.task_type === 'youtube' ? 'bg-red-100 text-red-700'
                          : task.task_type === 'threads' ? 'bg-gray-200 text-gray-800'
                          : 'bg-pink-100 text-pink-700'
                        }`}>
                          {task.task_type === 'youtube' ? 'YouTube' : task.task_type === 'threads' ? 'Threads' : 'Instagram'}
                        </span>
                      </td>
                      <td className="px-6 py-3">
                        <span className={`inline-flex items-center text-sm ${s.text}`}>
                          <span className={`w-2 h-2 rounded-full mr-1.5 ${s.dot}`} />
                          {s.label}
                        </span>
                      </td>
                      <td className="px-6 py-3 text-sm text-gray-600">
                        {(task.result_summary as Record<string, unknown>)?.total != null
                          ? `${(task.result_summary as Record<string, unknown>).total} 个 KOL`
                          : '-'}
                      </td>
                      <td className="px-6 py-3 text-sm text-gray-500">{task.created_at_display}</td>
                      <td className="px-6 py-3">
                        <Link to={`/tasks/${task.task_id}`} className="text-sm text-blue-600 hover:text-blue-800">
                          查看
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="px-6 py-12 text-center text-gray-400">
            <p>暂无任务记录</p>
            <Link to="/discover" className="text-blue-600 hover:underline text-sm mt-2 inline-block">
              开始搜索博主
            </Link>
          </div>
        )}
      </div>
    </>
  )
}
