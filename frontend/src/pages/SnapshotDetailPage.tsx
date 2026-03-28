import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { getSnapshot } from '../api/snapshots'

export default function SnapshotDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data, isLoading, error } = useQuery({
    queryKey: ['snapshot', id],
    queryFn: () => getSnapshot(id!),
    enabled: !!id,
  })

  if (isLoading) return <div className="text-gray-400 text-center py-20">加载中...</div>
  if (error || !data) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center">
        <p className="text-gray-500">快照不存在</p>
        <Link to="/snapshots" className="text-blue-600 hover:underline text-sm mt-2 inline-block">返回列表</Link>
      </div>
    )
  }

  const platform = data.platform
  const platformLabel = platform === 'youtube' ? 'YouTube' : platform === 'threads' ? 'Threads' : 'Instagram'
  const platformStyle = platform === 'youtube' ? 'bg-red-100 text-red-700'
    : platform === 'threads' ? 'bg-gray-200 text-gray-800'
    : 'bg-pink-100 text-pink-700'

  return (
    <>
      <div className="mb-6 flex items-center space-x-3">
        <Link to="/snapshots" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <h2 className="text-2xl font-bold text-gray-900">快照详情</h2>
        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${platformStyle}`}>
          {platformLabel}
        </span>
        <span className="text-sm text-gray-500">共 {data.total} 个 KOL</span>
      </div>

      {data.search_params && Object.keys(data.search_params).length > 0 && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-6">
          <h3 className="font-semibold text-gray-900 mb-3">搜索参数</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(data.search_params).map(([key, val]) => (
              <div key={key}>
                <p className="text-xs text-gray-500">{key}</p>
                <p className="text-sm font-medium text-gray-900 mt-0.5">
                  {Array.isArray(val) ? val.join(', ') : String(val)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-6 py-3 text-left">名称</th>
                <th className="px-6 py-3 text-right">{platform === 'youtube' ? '订阅数' : '粉丝数'}</th>
                <th className="px-6 py-3 text-right">HK 分</th>
                <th className="px-6 py-3 text-left">内容方向</th>
                <th className="px-6 py-3 text-left">链接</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {data.kols.map((kol, i) => {
                const name = (kol.name as string) || ''
                const count = platform === 'youtube' ? (kol.subscriber_count as number) : (kol.follower_count as number)
                const hk = (kol.hk_relevance_score as number) || 0
                const focus = (kol.content_focus as string[]) || []
                const url = (kol.profile_url as string) || ''
                return (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="px-6 py-3 text-sm font-medium text-gray-900">{name}</td>
                    <td className="px-6 py-3 text-sm text-right text-gray-700">{count?.toLocaleString()}</td>
                    <td className="px-6 py-3 text-sm text-right text-gray-700">{hk}</td>
                    <td className="px-6 py-3">
                      <div className="flex flex-wrap gap-1">
                        {focus.slice(0, 3).map((f) => (
                          <span key={f} className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-600">{f}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-6 py-3">
                      {url && (
                        <a href={url} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:text-blue-800">
                          访问
                        </a>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
