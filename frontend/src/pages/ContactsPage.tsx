import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import toast from 'react-hot-toast'
import {
  listContacts, importFromSnapshot, deleteContact, updateContactStatus,
  batchDeleteContacts, updateEmail, type Contact,
} from '../api/contacts'
import ConfirmDialog from '../components/ConfirmDialog'

const CHANNEL_LABELS: Record<string, { icon: string; color: string }> = {
  email: { icon: '📧', color: 'bg-blue-50 text-blue-700' },
  phone: { icon: '📱', color: 'bg-green-50 text-green-700' },
  whatsapp: { icon: '💬', color: 'bg-emerald-50 text-emerald-700' },
  link: { icon: '🔗', color: 'bg-gray-50 text-gray-600' },
}

function ChannelBadges({ channels }: { channels: Record<string, string[] | boolean> | undefined }) {
  if (!channels || Object.keys(channels).length === 0) return <span className="text-xs text-gray-300">-</span>

  return (
    <div className="flex flex-wrap gap-1">
      {Object.entries(channels).map(([key, val]) => {
        const cfg = CHANNEL_LABELS[key] || { icon: '•', color: 'bg-gray-100 text-gray-500' }
        let label = key
        if (val === true) {
          label = key === 'whatsapp' ? 'WhatsApp' : key
        } else if (Array.isArray(val) && val.length > 0) {
          label = val.length === 1 ? val[0] : `${val[0]} +${val.length - 1}`
        }
        return (
          <span key={key} title={Array.isArray(val) ? val.join('\n') : key}
            className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs ${cfg.color}`}>
            <span>{cfg.icon}</span>
            <span className="max-w-[120px] truncate">{label}</span>
          </span>
        )
      })}
    </div>
  )
}

const STATUS_OPTIONS = [
  { value: 'pending', label: '待联系', color: 'bg-gray-100 text-gray-700' },
  { value: 'contacted', label: '已联系', color: 'bg-blue-100 text-blue-700' },
  { value: 'replied', label: '已回复', color: 'bg-green-100 text-green-700' },
  { value: 'cooperating', label: '合作中', color: 'bg-purple-100 text-purple-700' },
]

export default function ContactsPage() {
  const queryClient = useQueryClient()
  const { data, isLoading } = useQuery({ queryKey: ['contacts'], queryFn: listContacts })
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [importSnapshotId, setImportSnapshotId] = useState('')
  const [editingEmail, setEditingEmail] = useState<{ id: string; email: string } | null>(null)
  const [deletingSingle, setDeletingSingle] = useState<{ id: string; name: string } | null>(null)
  const [deletingBatch, setDeletingBatch] = useState(false)

  const importMutation = useMutation({
    mutationFn: (sid: string) => importFromSnapshot(sid),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      setImportSnapshotId('')
      toast.success('导入完成')
    },
    onError: () => toast.error('导入失败'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteContact,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      toast.success('联系人已删除')
      setDeletingSingle(null)
    },
    onError: () => toast.error('删除失败'),
  })

  const batchDeleteMutation = useMutation({
    mutationFn: batchDeleteContacts,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      setSelectedIds(new Set())
      toast.success(`已删除 ${selectedIds.size} 个联系人`)
      setDeletingBatch(false)
    },
    onError: () => toast.error('批量删除失败'),
  })

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateContactStatus(id, status),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['contacts'] }),
  })

  const emailMutation = useMutation({
    mutationFn: ({ id, email }: { id: string; email: string }) => updateEmail(id, email),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['contacts'] })
      setEditingEmail(null)
      toast.success('邮箱已更新')
    },
  })

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  const toggleAll = (contacts: Contact[]) => {
    if (selectedIds.size === contacts.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(contacts.map((c) => c.id)))
    }
  }

  if (isLoading || !data) return <div className="text-gray-400 text-center py-20">加载中...</div>

  const { contacts, snapshots, total, with_email, with_contact } = data

  return (
    <>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">联系博主</h2>
          <p className="text-gray-500 mt-1">
            共 {total} 人 · 有邮箱 {with_email} · 有联系方式 {with_contact}
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Link to="/contacts/templates" className="px-4 py-2 border border-gray-300 hover:bg-gray-50 text-gray-700 text-sm rounded-lg transition">
            邮件模板
          </Link>
          <Link to="/contacts/compose" className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition">
            撰写邮件
          </Link>
        </div>
      </div>

      {/* Import */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-5 mb-6">
        <h3 className="font-semibold text-gray-900 mb-3">从快照导入</h3>
        <div className="flex items-end gap-3">
          <div className="flex-1 max-w-md">
            <select value={importSnapshotId} onChange={(e) => setImportSnapshotId(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none">
              <option value="">选择快照</option>
              {snapshots.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.platform.toUpperCase()} · {s.total_kols} KOL · {s.created_at}
                </option>
              ))}
            </select>
          </div>
          <button onClick={() => importSnapshotId && importMutation.mutate(importSnapshotId)}
            disabled={!importSnapshotId || importMutation.isPending}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white text-sm rounded-lg transition">
            {importMutation.isPending ? '导入中...' : '导入'}
          </button>
        </div>
      </div>

      {/* Batch actions */}
      {selectedIds.size > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-4 flex items-center justify-between">
          <span className="text-sm text-blue-700">已选 {selectedIds.size} 人</span>
          <div className="space-x-3">
            <Link to={`/contacts/compose?ids=${Array.from(selectedIds).join(',')}`}
              className="px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded-lg transition">
              发送邮件
            </Link>
            <button onClick={() => setDeletingBatch(true)}
              className="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs rounded-lg transition">
              批量删除
            </button>
          </div>
        </div>
      )}

      {/* Contacts Table */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-100">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 text-xs text-gray-500 uppercase">
              <tr>
                <th className="px-4 py-3">
                  <input type="checkbox" checked={selectedIds.size === contacts.length && contacts.length > 0}
                    onChange={() => toggleAll(contacts)} className="rounded" />
                </th>
                <th className="px-4 py-3 text-left">博主</th>
                <th className="px-4 py-3 text-right">粉丝</th>
                <th className="px-4 py-3 text-left">邮箱</th>
                <th className="px-4 py-3 text-left">联系渠道</th>
                <th className="px-4 py-3 text-left">状态</th>
                <th className="px-4 py-3 text-left">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {contacts.map((c) => {
                const statusOpt = STATUS_OPTIONS.find((s) => s.value === c.contact_status) || STATUS_OPTIONS[0]
                return (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <input type="checkbox" checked={selectedIds.has(c.id)}
                        onChange={() => toggleSelect(c.id)} className="rounded" />
                    </td>
                    <td className="px-4 py-3">
                      <div className="text-sm font-medium text-gray-900">{c.name}</div>
                      <a href={c.profile_url} target="_blank" rel="noopener noreferrer"
                        className="text-xs text-blue-600 hover:underline">{c.platform}</a>
                    </td>
                    <td className="px-4 py-3 text-sm text-right text-gray-700">{c.follower_count?.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {editingEmail?.id === c.id ? (
                        <form onSubmit={(e) => { e.preventDefault(); emailMutation.mutate({ id: c.id, email: editingEmail.email }) }}
                          className="flex gap-1">
                          <input value={editingEmail.email} onChange={(e) => setEditingEmail({ ...editingEmail, email: e.target.value })}
                            className="px-2 py-1 border rounded text-xs w-40" autoFocus />
                          <button type="submit" className="text-xs text-blue-600">保存</button>
                          <button type="button" onClick={() => setEditingEmail(null)} className="text-xs text-gray-400">取消</button>
                        </form>
                      ) : (
                        <span onClick={() => setEditingEmail({ id: c.id, email: c.email || '' })}
                          className="text-sm text-gray-600 cursor-pointer hover:text-blue-600">
                          {c.email || <span className="text-gray-300">点击添加</span>}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <ChannelBadges channels={c._channels} />
                    </td>
                    <td className="px-4 py-3">
                      <select value={c.contact_status || 'pending'}
                        onChange={(e) => statusMutation.mutate({ id: c.id, status: e.target.value })}
                        className={`px-2 py-1 rounded-full text-xs font-medium border-0 ${statusOpt.color}`}>
                        {STATUS_OPTIONS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => setDeletingSingle({ id: c.id, name: c.name })}
                        className="text-xs text-red-600 hover:text-red-800">删除</button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        {contacts.length === 0 && (
          <div className="p-12 text-center text-gray-400">暂无联系人，请先从快照导入</div>
        )}
      </div>

      <ConfirmDialog
        open={!!deletingSingle}
        title="删除联系人"
        message={`确定删除联系人「${deletingSingle?.name}」？`}
        confirmLabel="删除"
        onConfirm={() => deletingSingle && deleteMutation.mutate(deletingSingle.id)}
        onCancel={() => setDeletingSingle(null)}
      />

      <ConfirmDialog
        open={deletingBatch}
        title="批量删除"
        message={`确定删除选中的 ${selectedIds.size} 个联系人？删除后不可恢复。`}
        confirmLabel={`删除 ${selectedIds.size} 人`}
        onConfirm={() => batchDeleteMutation.mutate(Array.from(selectedIds))}
        onCancel={() => setDeletingBatch(false)}
      />
    </>
  )
}
