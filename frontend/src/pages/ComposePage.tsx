import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getComposeData, sendEmails } from '../api/contacts'

export default function ComposePage() {
  const [searchParams] = useSearchParams()
  const preselectedIds = searchParams.get('ids')?.split(',').filter(Boolean) || []

  const { data, isLoading } = useQuery({ queryKey: ['compose-data'], queryFn: getComposeData })

  const [templateId, setTemplateId] = useState('')
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set(preselectedIds))
  const [fromName, setFromName] = useState('')
  const [result, setResult] = useState<{ success_count: number; fail_count: number; total: number } | null>(null)

  useEffect(() => {
    if (preselectedIds.length > 0) {
      setSelectedIds(new Set(preselectedIds))
    }
  }, [])

  const sendMutation = useMutation({
    mutationFn: () => sendEmails(templateId, Array.from(selectedIds), fromName),
    onSuccess: (data) => setResult(data),
  })

  const toggleContact = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  if (isLoading || !data) return <div className="text-gray-400 text-center py-20">加载中...</div>

  const selectedTemplate = data.templates.find((t) => t.id === templateId)

  return (
    <>
      <div className="mb-6 flex items-center space-x-3">
        <Link to="/contacts" className="text-gray-400 hover:text-gray-600">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <h2 className="text-2xl font-bold text-gray-900">撰写邮件</h2>
      </div>

      {result ? (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-8 max-w-lg">
          <div className="text-center">
            <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">发送完成</h3>
            <p className="text-sm text-gray-600">
              成功 {result.success_count} 封 / 失败 {result.fail_count} 封 / 共 {result.total} 封
            </p>
            <Link to="/contacts" className="inline-block mt-4 text-sm text-blue-600 hover:text-blue-800">
              返回联系人列表
            </Link>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            {/* Template selection */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3">选择模板</h3>
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
                <option value="">请选择邮件模板</option>
                {data.templates.map((t) => <option key={t.id} value={t.id}>{t.name} — {t.subject}</option>)}
              </select>
              {selectedTemplate && (
                <div className="mt-3 p-3 bg-gray-50 rounded-lg">
                  <p className="text-xs text-gray-500 mb-1">主题: {selectedTemplate.subject}</p>
                  <div className="text-xs text-gray-400 max-h-32 overflow-y-auto" dangerouslySetInnerHTML={{ __html: selectedTemplate.body }} />
                </div>
              )}
            </div>

            {/* From name */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
              <h3 className="font-semibold text-gray-900 mb-3">发件人名称（可选）</h3>
              <input value={fromName} onChange={(e) => setFromName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="留空则使用默认名称" />
            </div>

            {/* Send button */}
            <button onClick={() => sendMutation.mutate()}
              disabled={!templateId || selectedIds.size === 0 || sendMutation.isPending}
              className="w-full px-5 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-medium rounded-lg transition">
              {sendMutation.isPending ? '发送中...' : `发送给 ${selectedIds.size} 人`}
            </button>
          </div>

          {/* Contact selection */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-100">
            <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">选择收件人</h3>
              <span className="text-xs text-gray-400">已选 {selectedIds.size} / {data.contacts.length}</span>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {data.contacts.map((c) => (
                <label key={c.id}
                  className={`flex items-center px-5 py-3 border-b border-gray-50 cursor-pointer hover:bg-gray-50 transition ${
                    selectedIds.has(c.id) ? 'bg-blue-50' : ''
                  }`}>
                  <input type="checkbox" checked={selectedIds.has(c.id)} onChange={() => toggleContact(c.id)}
                    className="rounded mr-3" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium text-gray-900 truncate">{c.name}</div>
                    <div className="text-xs text-gray-500 truncate">{c.email}</div>
                  </div>
                  <span className="text-xs text-gray-400">{c.follower_count?.toLocaleString()}</span>
                </label>
              ))}
              {data.contacts.length === 0 && (
                <div className="p-8 text-center text-gray-400 text-sm">没有可发送邮件的联系人</div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}
