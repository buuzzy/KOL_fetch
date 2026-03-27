import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { listSnapshots, diffSnapshots, type DiffResult } from '../api/snapshots'
import { downloadReport } from '../api/reports'

export default function DiffPage() {
  const [platform, setPlatform] = useState<'youtube' | 'instagram'>('youtube')
  const [oldId, setOldId] = useState('')
  const [newId, setNewId] = useState('')
  const [result, setResult] = useState<DiffResult | null>(null)

  const { data: ytSnapshots } = useQuery({ queryKey: ['snapshots', 'youtube'], queryFn: () => listSnapshots('youtube') })
  const { data: igSnapshots } = useQuery({ queryKey: ['snapshots', 'instagram'], queryFn: () => listSnapshots('instagram') })

  const snapshots = platform === 'youtube' ? ytSnapshots : igSnapshots

  const mutation = useMutation({
    mutationFn: () => diffSnapshots(platform, oldId, newId),
    onSuccess: setResult,
  })

  const handleSubmit = () => {
    if (!oldId || !newId) return
    mutation.mutate()
  }

  const reportFile = result?.report_path?.split('/').pop()
  const isYT = platform === 'youtube'

  return (
    <>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">月度轧差</h2>
        <p className="text-gray-500 mt-1">对比两次快照，分析 KOL 变化</p>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6 max-w-2xl">
        <div className="flex space-x-1 bg-gray-100 p-1 rounded-lg mb-6 w-fit">
          {(['youtube', 'instagram'] as const).map((p) => (
            <button key={p} onClick={() => { setPlatform(p); setOldId(''); setNewId(''); setResult(null) }}
              className={`px-5 py-2 rounded-md text-sm font-medium transition ${
                platform === p ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500 hover:text-gray-700'
              }`}>
              {p === 'youtube' ? 'YouTube' : 'Instagram'}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">旧快照（基准）</label>
            <select value={oldId} onChange={(e) => setOldId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
              <option value="">选择快照</option>
              {snapshots?.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">新快照（对比）</label>
            <select value={newId} onChange={(e) => setNewId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none">
              <option value="">选择快照</option>
              {snapshots?.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </div>
        </div>

        <button onClick={handleSubmit} disabled={!oldId || !newId || mutation.isPending}
          className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-medium rounded-lg transition">
          {mutation.isPending ? '对比中...' : '开始对比'}
        </button>
      </div>

      {result && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
              <p className="text-sm text-gray-500">旧快照 KOL</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{result.total_old}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
              <p className="text-sm text-gray-500">新快照 KOL</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{result.total_new}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
              <p className="text-sm text-gray-500">新增</p>
              <p className="text-2xl font-bold text-green-600 mt-1">{result.new_kols.length}</p>
            </div>
            <div className="bg-white rounded-xl shadow-sm p-5 border border-gray-100">
              <p className="text-sm text-gray-500">流失</p>
              <p className="text-2xl font-bold text-red-600 mt-1">{result.lost_kols.length}</p>
            </div>
          </div>

          {reportFile && (
            <div className="mb-6">
              <button onClick={() => downloadReport(reportFile)}
                className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm rounded-lg transition">
                下载轧差报告
              </button>
            </div>
          )}

          {result.new_kols.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 mb-6">
              <div className="px-6 py-4 border-b border-gray-100">
                <h3 className="font-semibold text-green-700">新增 KOL ({result.new_kols.length})</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-6 py-3 text-left">名称</th>
                      <th className="px-6 py-3 text-right">{isYT ? '订阅数' : '粉丝数'}</th>
                      <th className="px-6 py-3 text-left">链接</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {result.new_kols.map((kol, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-6 py-3 text-sm font-medium text-gray-900">{kol.name as string}</td>
                        <td className="px-6 py-3 text-sm text-right">{((isYT ? kol.subscriber_count : kol.follower_count) as number)?.toLocaleString()}</td>
                        <td className="px-6 py-3">
                          <a href={kol.profile_url as string} target="_blank" rel="noopener noreferrer" className="text-sm text-blue-600 hover:text-blue-800">访问</a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {result.grown_kols.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-100">
              <div className="px-6 py-4 border-b border-gray-100">
                <h3 className="font-semibold text-blue-700">粉丝增长 TOP {Math.min(20, result.grown_kols.length)}</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
                    <tr>
                      <th className="px-6 py-3 text-left">名称</th>
                      <th className="px-6 py-3 text-right">原{isYT ? '订阅' : '粉丝'}数</th>
                      <th className="px-6 py-3 text-right">增长</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {result.grown_kols.map((item, i) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-6 py-3 text-sm font-medium text-gray-900">{item.kol.name as string}</td>
                        <td className="px-6 py-3 text-sm text-right text-gray-600">{item.old_count.toLocaleString()}</td>
                        <td className="px-6 py-3 text-sm text-right text-green-600 font-medium">+{item.growth.toLocaleString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}
