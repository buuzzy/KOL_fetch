import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { listTemplates, createTemplate, updateTemplate, deleteTemplate, type EmailTemplate } from '../api/contacts'

export default function TemplatesPage() {
  const queryClient = useQueryClient()
  const { data: templates, isLoading } = useQuery({ queryKey: ['templates'], queryFn: listTemplates })

  const [showForm, setShowForm] = useState(false)
  const [name, setName] = useState('')
  const [subject, setSubject] = useState('')
  const [bodyHtml, setBodyHtml] = useState('')

  const [editing, setEditing] = useState<EmailTemplate | null>(null)

  const createMutation = useMutation({
    mutationFn: () => createTemplate(name, subject, bodyHtml),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] })
      setShowForm(false)
      setName(''); setSubject(''); setBodyHtml('')
    },
  })

  const updateMutation = useMutation({
    mutationFn: (data: { id: string; name: string; subject: string; body_html: string }) =>
      updateTemplate(data.id, { name: data.name, subject: data.subject, body_html: data.body_html }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['templates'] })
      setEditing(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteTemplate,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['templates'] }),
  })

  if (isLoading) return <div className="text-gray-400 text-center py-20">加载中...</div>

  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <Link to="/contacts" className="text-gray-400 hover:text-gray-600">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </Link>
          <h2 className="text-2xl font-bold text-gray-900">邮件模板</h2>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition">
          {showForm ? '取消' : '新建模板'}
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 mb-6 max-w-2xl">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">模板名称</label>
              <input value={name} onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="如：初次联系模板" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">邮件主题</label>
              <input value={subject} onChange={(e) => setSubject(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="支持 {{name}} 变量" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">邮件正文 (HTML)</label>
              <textarea value={bodyHtml} onChange={(e) => setBodyHtml(e.target.value)} rows={8}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none font-mono resize-y"
                placeholder="支持 HTML 和 {{name}} 变量" />
            </div>
            <button onClick={() => createMutation.mutate()} disabled={!name || !subject || createMutation.isPending}
              className="px-5 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm font-medium rounded-lg transition">
              {createMutation.isPending ? '保存中...' : '保存模板'}
            </button>
          </div>
        </div>
      )}

      <div className="space-y-4">
        {templates?.map((tpl) => (
          <div key={tpl.id} className="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
            {editing?.id === tpl.id ? (
              <div className="space-y-3">
                <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                <input value={editing.subject} onChange={(e) => setEditing({ ...editing, subject: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm" />
                <textarea value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })}
                  rows={6} className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono resize-y" />
                <div className="flex gap-2">
                  <button onClick={() => updateMutation.mutate({ id: editing.id, name: editing.name, subject: editing.subject, body_html: editing.body })}
                    className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition">保存</button>
                  <button onClick={() => setEditing(null)}
                    className="px-4 py-1.5 border border-gray-300 text-gray-700 text-sm rounded-lg transition">取消</button>
                </div>
              </div>
            ) : (
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="font-semibold text-gray-900">{tpl.name}</h4>
                  <p className="text-sm text-gray-500 mt-1">主题: {tpl.subject}</p>
                  <p className="text-xs text-gray-400 mt-1">{tpl.created_at}</p>
                </div>
                <div className="flex gap-2">
                  <button onClick={() => setEditing(tpl)} className="text-sm text-blue-600 hover:text-blue-800">编辑</button>
                  <button onClick={() => {
                    if (confirm(`确定删除模板「${tpl.name}」？`)) deleteMutation.mutate(tpl.id)
                  }} className="text-sm text-red-600 hover:text-red-800">删除</button>
                </div>
              </div>
            )}
          </div>
        ))}
        {templates?.length === 0 && (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-12 text-center text-gray-400">
            暂无模板，点击上方"新建模板"创建
          </div>
        )}
      </div>
    </>
  )
}
