import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getDashboardStats } from '../api/discover'

const STATUS_MAP: Record<string, { dot: string; text: string; label: string }> = {
  completed: { dot: 'bg-green-500', text: 'text-green-600', label: '已完成' },
  running: { dot: 'bg-blue-500 animate-pulse', text: 'text-blue-600', label: '运行中' },
  failed: { dot: 'bg-red-500', text: 'text-red-600', label: '失败' },
  pending: { dot: 'bg-gray-400', text: 'text-gray-500', label: '等待中' },
}

export default function DashboardPage() {
  const { data, isLoading } = useQuery({ queryKey: ['dashboard'], queryFn: getDashboardStats })

  if (isLoading || !data) {
    return <div className="text-gray-400 text-center py-20">加载中...</div>
  }

  return (
    <>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">工作台</h2>
        <p className="text-gray-500 mt-1">概览与近期任务</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'YouTube 快照', value: data.yt_snapshot_count, color: 'text-gray-900' },
          { label: 'Instagram 快照', value: data.ig_snapshot_count, color: 'text-gray-900' },
          { label: '运行中任务', value: data.running_tasks, color: 'text-blue-600' },
          { label: '今日已完成', value: data.completed_today, color: 'text-green-600' },
        ].map((card) => (
          <div key={card.label} className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
            <p className="text-sm text-gray-500">{card.label}</p>
            <p className={`text-2xl font-bold mt-1 ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
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
                <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069z" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900 group-hover:text-pink-600 transition">Instagram 博主发现</h3>
              <p className="text-sm text-gray-500 mt-0.5">搜索港澳财经 IG 博主</p>
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
                          task.task_type === 'youtube' ? 'bg-red-100 text-red-700' : 'bg-pink-100 text-pink-700'
                        }`}>
                          {task.task_type === 'youtube' ? 'YouTube' : 'Instagram'}
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
