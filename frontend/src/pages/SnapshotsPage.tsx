import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import { listSnapshots, deleteSnapshot } from '../api/snapshots'
import ConfirmDialog from '../components/ConfirmDialog'

export default function SnapshotsPage() {
  const queryClient = useQueryClient()
  const { data: snapshots, isLoading } = useQuery({ queryKey: ['snapshots'], queryFn: () => listSnapshots() })
  const [deleting, setDeleting] = useState<{ id: string; label: string } | null>(null)

  const deleteMutation = useMutation({
    mutationFn: deleteSnapshot,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['snapshots'] })
      toast.success('快照已删除')
      setDeleting(null)
    },
    onError: () => toast.error('删除失败，请重试'),
  })

  if (isLoading) return <div className="text-gray-400 text-center py-20">加载中...</div>

  return (
    <>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">快照历史</h2>
        <p className="text-gray-500 mt-1">管理所有搜索快照</p>
      </div>

      {snapshots && snapshots.length > 0 ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                <tr>
                  <th className="px-6 py-3 text-left">平台</th>
                  <th className="px-6 py-3 text-left">KOL 数量</th>
                  <th className="px-6 py-3 text-left">关键词</th>
                  <th className="px-6 py-3 text-left">创建时间</th>
                  <th className="px-6 py-3 text-left">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {snapshots.map((s) => (
                  <tr key={s.id} className="hover:bg-gray-50">
                    <td className="px-6 py-3">
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        s.platform === 'youtube' ? 'bg-red-100 text-red-700'
                        : s.platform === 'threads' ? 'bg-gray-200 text-gray-800'
                        : 'bg-pink-100 text-pink-700'
                      }`}>
                        {s.platform === 'youtube' ? 'YouTube' : s.platform === 'threads' ? 'Threads' : 'Instagram'}
                      </span>
                    </td>
                    <td className="px-6 py-3 text-sm font-medium text-gray-900">{s.total_kols}</td>
                    <td className="px-6 py-3">
                      <div className="flex flex-wrap gap-1">
                        {s.keywords_summary.slice(0, 4).map((kw) => (
                          <span key={kw} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{kw}</span>
                        ))}
                        {s.keywords_total > 4 && (
                          <span className="text-xs text-gray-400">+{s.keywords_total - 4}</span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-3 text-sm text-gray-500">{s.created_at}</td>
                    <td className="px-6 py-3 space-x-3">
                      <Link to={`/snapshots/${s.id}`} className="text-sm text-blue-600 hover:text-blue-800">详情</Link>
                      <button onClick={() => setDeleting({ id: s.id, label: s.label })} className="text-sm text-red-600 hover:text-red-800">删除</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
          <p>暂无快照</p>
          <Link to="/discover" className="text-blue-600 hover:underline text-sm mt-2 inline-block">开始搜索博主</Link>
        </div>
      )}

      <ConfirmDialog
        open={!!deleting}
        title="删除快照"
        message={`确定删除快照「${deleting?.label}」？删除后不可恢复。`}
        confirmLabel="删除"
        loading={deleteMutation.isPending}
        onConfirm={() => deleting && deleteMutation.mutate(deleting.id)}
        onCancel={() => setDeleting(null)}
      />
    </>
  )
}
