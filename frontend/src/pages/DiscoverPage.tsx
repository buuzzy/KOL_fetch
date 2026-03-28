import { useState, useEffect, useRef, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import {
  getKeywords, getIGKeywords, getThreadsKeywords, getLLMOptions,
  submitYoutube, submitInstagram, submitThreads,
  runHealthCheck,
  type LLMCriteria, type LLMOption, type HealthCheckResult,
} from '../api/discover'

type Platform = 'youtube' | 'instagram' | 'threads'

const DEFAULT_CRITERIA: LLMCriteria = {
  kol_types: [],
  exclude_types: ['media', 'institution', 'insurance', 'realestate'],
  audience: 'hk_macau',
  custom_requirements: '',
}

export default function DiscoverPage() {
  const [searchParams] = useSearchParams()
  const paramPlatform = searchParams.get('platform')
  const [platform, setPlatform] = useState<Platform>(
    paramPlatform === 'instagram' ? 'instagram' : paramPlatform === 'threads' ? 'threads' : 'youtube'
  )

  useEffect(() => {
    if (paramPlatform === 'instagram' || paramPlatform === 'youtube' || paramPlatform === 'threads') {
      setPlatform(paramPlatform)
    }
  }, [paramPlatform])

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">发现博主</h2>
          <p className="text-gray-500 mt-1 text-sm">搜索港澳财经博主，AI 自动精筛</p>
        </div>
        <HealthCheckButton />
      </div>

      <div className="flex space-x-1 bg-gray-100 rounded-lg p-1 max-w-md mb-6">
        {(['youtube', 'instagram', 'threads'] as const).map((p) => {
          const labels: Record<Platform, string> = { youtube: 'YouTube', instagram: 'Instagram', threads: 'Threads' }
          const colors: Record<Platform, string> = { youtube: 'text-red-600', instagram: 'text-pink-600', threads: 'text-gray-900' }
          return (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              className={`flex-1 px-4 py-2 text-sm font-medium rounded-md transition ${
                platform === p ? `bg-white ${colors[p]} shadow-sm` : 'text-gray-500 hover:text-gray-700'
              }`}
            >
              {labels[p]}
            </button>
          )
        })}
      </div>

      {platform === 'youtube' ? <YouTubeForm /> : platform === 'instagram' ? <InstagramForm /> : <ThreadsForm />}
    </>
  )
}


/* ═══════════════════ 接口预检 ═══════════════════ */

function HealthCheckButton() {
  const [result, setResult] = useState<HealthCheckResult | null>(null)
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const mutation = useMutation({
    mutationFn: runHealthCheck,
    onSuccess: (data) => { setResult(data); setOpen(true) },
  })

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const Dot = ({ ok }: { ok: boolean }) => (
    <span className={`inline-block w-2 h-2 rounded-full mr-2 ${ok ? 'bg-green-500' : 'bg-red-500'}`} />
  )

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className="px-3 py-2 text-xs font-medium text-gray-600 bg-gray-100 hover:bg-gray-200 rounded-lg transition flex items-center"
      >
        {mutation.isPending ? (
          <svg className="animate-spin w-3.5 h-3.5 mr-1.5" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" className="opacity-25" />
            <path d="M4 12a8 8 0 018-8" stroke="currentColor" strokeWidth="4" className="opacity-75" strokeLinecap="round" />
          </svg>
        ) : (
          <svg className="w-3.5 h-3.5 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        )}
        接口预检
      </button>

      {open && result && (
        <div className="absolute right-0 top-full mt-2 w-72 bg-white rounded-xl shadow-lg border border-gray-200 p-4 z-50">
          <p className="text-xs font-semibold text-gray-900 mb-3">接口连通性</p>
          {([
            { key: 'youtube' as const, label: 'YouTube API', detail: result.youtube.ok ? `${result.youtube.keys} 个 Key` : result.youtube.error },
            { key: 'tikhub' as const, label: 'TikHub (IG/Threads)', detail: result.tikhub.ok ? '正常' : result.tikhub.error },
            { key: 'llm' as const, label: 'LLM 精筛', detail: result.llm.ok ? result.llm.model : result.llm.error },
          ]).map((item) => (
            <div key={item.key} className="flex items-start py-1.5">
              <Dot ok={result[item.key].ok} />
              <div className="min-w-0">
                <span className="text-sm font-medium text-gray-800">{item.label}</span>
                <p className="text-xs text-gray-500 truncate">{item.detail}</p>
              </div>
            </div>
          ))}
          <button onClick={() => setOpen(false)} className="mt-2 text-xs text-gray-400 hover:text-gray-600 w-full text-center">关闭</button>
        </div>
      )}
    </div>
  )
}


/* ═══════════════════ 下拉多选组件 ═══════════════════ */

function MultiSelect({ label, items, selected, onChange, allLabel = '全选', noneLabel = '清空' }: {
  label: string
  items: string[]
  selected: string[]
  onChange: (v: string[]) => void
  allLabel?: string
  noneLabel?: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const summary = selected.length === 0
    ? '未选择'
    : selected.length === items.length
      ? '全部'
      : `${selected.length} / ${items.length} 个`

  const toggle = (item: string) => {
    onChange(selected.includes(item) ? selected.filter((x) => x !== item) : [...selected, item])
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white hover:border-gray-400 transition"
      >
        <span className="text-gray-700">{label}: <span className="font-medium">{summary}</span></span>
        <svg className={`w-4 h-4 text-gray-400 transition ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-64 overflow-y-auto">
          <div className="flex items-center justify-between px-3 py-2 border-b border-gray-100">
            <button type="button" onClick={() => onChange([...items])} className="text-xs text-blue-600 hover:text-blue-800">{allLabel}</button>
            <button type="button" onClick={() => onChange([])} className="text-xs text-gray-500 hover:text-gray-700">{noneLabel}</button>
          </div>
          {items.map((item) => (
            <label key={item} className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer">
              <input
                type="checkbox"
                checked={selected.includes(item)}
                onChange={() => toggle(item)}
                className="mr-2.5 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-700">{item}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}

function LLMMultiSelect({ label, items, selected, onChange, accentClass = 'text-blue-600' }: {
  label: string
  items: LLMOption[]
  selected: string[]
  onChange: (v: string[]) => void
  accentClass?: string
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const selectedLabels = items.filter((i) => selected.includes(i.id)).map((i) => i.label)
  const summary = selectedLabels.length === 0 ? '未设置' : selectedLabels.join('、')

  const toggle = (id: string) => {
    onChange(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id])
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white hover:border-gray-400 transition text-left"
      >
        <span className="text-gray-700 truncate">{label}: <span className="font-medium">{summary}</span></span>
        <svg className={`w-4 h-4 text-gray-400 transition shrink-0 ml-2 ${open ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 right-0 top-full mt-1 bg-white rounded-lg shadow-lg border border-gray-200 z-50 max-h-56 overflow-y-auto">
          <div className="px-3 py-1.5 border-b border-gray-100">
            <button type="button" onClick={() => onChange([])} className="text-xs text-gray-500 hover:text-gray-700">清空选择</button>
          </div>
          {items.map((opt) => (
            <label key={opt.id} className="flex items-center px-3 py-2 hover:bg-gray-50 cursor-pointer">
              <input
                type="checkbox"
                checked={selected.includes(opt.id)}
                onChange={() => toggle(opt.id)}
                className={`mr-2.5 rounded border-gray-300 ${accentClass} focus:ring-blue-500`}
              />
              <span className="text-sm text-gray-700">{opt.label}</span>
            </label>
          ))}
        </div>
      )}
    </div>
  )
}


/* ═══════════════════ AI 精筛面板（共享） ═══════════════════ */

function LLMPanel({ enabled, onToggle, criteria, onChange, showAdvanced, onToggleAdvanced, accentClass, ringClass }: {
  enabled: boolean
  onToggle: (v: boolean) => void
  criteria: LLMCriteria
  onChange: (c: LLMCriteria) => void
  showAdvanced: boolean
  onToggleAdvanced: () => void
  accentClass: string
  ringClass: string
}) {
  const { data: llmOptions } = useQuery({ queryKey: ['llm-options'], queryFn: getLLMOptions })

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2.5 bg-gray-50">
        <label className="flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
            className={`mr-2.5 rounded border-gray-300 ${accentClass}`}
          />
          <span className="text-sm font-medium text-gray-700">AI 精筛</span>
          <span className="text-xs text-gray-400 ml-2">搜索后由 AI 自动过滤不合适的候选人</span>
        </label>
        {enabled && (
          <button type="button" onClick={onToggleAdvanced} className="text-xs text-gray-500 hover:text-gray-700">
            {showAdvanced ? '收起' : '自定义条件'}
          </button>
        )}
      </div>
      {enabled && showAdvanced && llmOptions && (
        <div className="px-4 py-3 space-y-3 bg-white border-t border-gray-100">
          <LLMMultiSelect
            label="博主类型偏好"
            items={llmOptions.kol_types}
            selected={criteria.kol_types}
            onChange={(v) => onChange({ ...criteria, kol_types: v })}
            accentClass={accentClass}
          />
          <LLMMultiSelect
            label="排除类型"
            items={llmOptions.exclude_types}
            selected={criteria.exclude_types}
            onChange={(v) => onChange({ ...criteria, exclude_types: v })}
            accentClass="text-red-600"
          />
          <div>
            <label className="block text-xs text-gray-500 mb-1">目标受众</label>
            <select
              value={criteria.audience}
              onChange={(e) => onChange({ ...criteria, audience: e.target.value })}
              className={`w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white ${ringClass} outline-none`}
            >
              {llmOptions.audiences.map((a) => (
                <option key={a.id} value={a.id}>{a.label}</option>
              ))}
            </select>
          </div>
          <textarea
            value={criteria.custom_requirements}
            onChange={(e) => onChange({ ...criteria, custom_requirements: e.target.value })}
            rows={2}
            className={`w-full px-3 py-2 border border-gray-300 rounded-lg text-sm ${ringClass} outline-none resize-y`}
            placeholder="补充要求（可选）"
          />
        </div>
      )}
    </div>
  )
}


/* ═══════════════════ YouTube 表单 ═══════════════════ */

function YouTubeForm() {
  const navigate = useNavigate()
  const { data: keywords } = useQuery({ queryKey: ['keywords'], queryFn: getKeywords })

  const [selected, setSelected] = useState<string[]>([])
  const [customKeywords, setCustomKeywords] = useState('')
  const [minSubs, setMinSubs] = useState(1000)
  const [maxSubs, setMaxSubs] = useState(200000)
  const [depth, setDepth] = useState('standard')
  const [inactiveDays, setInactiveDays] = useState(90)
  const [initialized, setInitialized] = useState(false)
  const [criteria, setCriteria] = useState<LLMCriteria>({ ...DEFAULT_CRITERIA })
  const [llmEnabled, setLlmEnabled] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const allKeywords = keywords ? [...keywords.core, ...keywords.extended, ...keywords.long_tail] : []

  if (keywords && !initialized) {
    setSelected([...keywords.core])
    setInitialized(true)
  }

  const mutation = useMutation({
    mutationFn: submitYoutube,
    onSuccess: (data) => navigate(`/tasks/${data.task_id}`),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      selected_keywords: selected.join('\n'),
      custom_keywords: customKeywords,
      min_subscribers: minSubs,
      max_subscribers: maxSubs,
      depth,
      max_inactive_days: inactiveDays,
      llm_criteria: llmEnabled ? criteria : null,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl space-y-4">
      <h3 className="font-semibold text-gray-900">YouTube 博主搜索</h3>

      {/* 关键词 */}
      <MultiSelect
        label="搜索关键词"
        items={allKeywords}
        selected={selected}
        onChange={setSelected}
      />

      {/* 自定义关键词 */}
      <details>
        <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">补充自定义关键词</summary>
        <textarea
          value={customKeywords} onChange={(e) => setCustomKeywords(e.target.value)}
          rows={2}
          className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
          placeholder="每行一个"
        />
      </details>

      {/* 粉丝范围 + 深度 + 活跃度 — 一行三列 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">最少订阅</label>
          <input type="number" value={minSubs} onChange={(e) => setMinSubs(+e.target.value)} min={0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">最多订阅</label>
          <input type="number" value={maxSubs} onChange={(e) => setMaxSubs(+e.target.value)} min={0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">搜索深度</label>
          <select value={depth} onChange={(e) => setDepth(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white">
            <option value="fast">快速</option>
            <option value="standard">标准（推荐）</option>
            <option value="deep">深度</option>
          </select>
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">活跃度</label>
          <select value={inactiveDays} onChange={(e) => setInactiveDays(+e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none bg-white">
            <option value={30}>1 个月内</option>
            <option value={90}>3 个月内（推荐）</option>
            <option value={180}>6 个月内</option>
            <option value={365}>1 年内</option>
            <option value={0}>不限</option>
          </select>
        </div>
      </div>

      {/* AI 精筛 */}
      <LLMPanel
        enabled={llmEnabled}
        onToggle={setLlmEnabled}
        criteria={criteria}
        onChange={setCriteria}
        showAdvanced={showAdvanced}
        onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
        accentClass="text-blue-600"
        ringClass="focus:ring-blue-500"
      />

      {/* 提交 */}
      <button
        type="submit"
        disabled={selected.length === 0 || mutation.isPending}
        className={`w-full py-2.5 text-white font-medium rounded-lg transition text-sm ${
          selected.length === 0 ? 'bg-gray-300 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'
        }`}
      >
        {mutation.isPending ? '提交中...' : `开始搜索（${selected.length} 个关键词）`}
      </button>
    </form>
  )
}


/* ═══════════════════ Instagram 表单 ═══════════════════ */

function InstagramForm() {
  const navigate = useNavigate()
  const { data: igData } = useQuery({ queryKey: ['ig-keywords'], queryFn: getIGKeywords })

  const [selected, setSelected] = useState<string[]>([])
  const [customKeywords, setCustomKeywords] = useState('')
  const [minFollowers, setMinFollowers] = useState(1000)
  const [maxFollowers, setMaxFollowers] = useState(200000)
  const [initialized, setInitialized] = useState(false)
  const [criteria, setCriteria] = useState<LLMCriteria>({ ...DEFAULT_CRITERIA })
  const [llmEnabled, setLlmEnabled] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const keywords = igData?.keywords || []

  if (keywords.length > 0 && !initialized) {
    setSelected([...keywords])
    setInitialized(true)
  }

  const mutation = useMutation({
    mutationFn: submitInstagram,
    onSuccess: (data) => navigate(`/tasks/${data.task_id}`),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      selected_keywords: selected.join('\n'),
      custom_keywords: customKeywords,
      min_followers: minFollowers,
      max_followers: maxFollowers,
      llm_criteria: llmEnabled ? criteria : null,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl space-y-4">
      <div>
        <h3 className="font-semibold text-gray-900">Instagram 博主搜索</h3>
        <p className="text-xs text-gray-500 mt-1">通过 TikHub API 搜索，每个关键词约 $0.002</p>
      </div>

      {/* 关键词 */}
      <MultiSelect
        label="搜索关键词"
        items={keywords}
        selected={selected}
        onChange={setSelected}
      />

      <details>
        <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">补充自定义关键词</summary>
        <textarea
          value={customKeywords} onChange={(e) => setCustomKeywords(e.target.value)}
          rows={2}
          className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-pink-500 focus:border-pink-500 outline-none resize-y"
          placeholder="每行一个"
        />
      </details>

      {/* 粉丝范围 */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">最少粉丝</label>
          <input type="number" value={minFollowers} onChange={(e) => setMinFollowers(+e.target.value)} min={0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-pink-500 outline-none" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">最多粉丝</label>
          <input type="number" value={maxFollowers} onChange={(e) => setMaxFollowers(+e.target.value)} min={0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-pink-500 outline-none" />
        </div>
      </div>

      {/* AI 精筛 */}
      <LLMPanel
        enabled={llmEnabled}
        onToggle={setLlmEnabled}
        criteria={criteria}
        onChange={setCriteria}
        showAdvanced={showAdvanced}
        onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
        accentClass="text-pink-600"
        ringClass="focus:ring-pink-500"
      />

      {/* 提交 */}
      <button
        type="submit"
        disabled={selected.length === 0 || mutation.isPending}
        className={`w-full py-2.5 text-white font-medium rounded-lg transition text-sm ${
          selected.length === 0 ? 'bg-gray-300 cursor-not-allowed' : 'bg-pink-600 hover:bg-pink-700'
        }`}
      >
        {mutation.isPending ? '提交中...' : `开始搜索（${selected.length} 个关键词）`}
      </button>
    </form>
  )
}


/* ═══════════════════ Threads 表单 ═══════════════════ */

function ThreadsForm() {
  const navigate = useNavigate()
  const { data: threadsData } = useQuery({ queryKey: ['threads-keywords'], queryFn: getThreadsKeywords })

  const [selected, setSelected] = useState<string[]>([])
  const [customKeywords, setCustomKeywords] = useState('')
  const [minFollowers, setMinFollowers] = useState(500)
  const [maxFollowers, setMaxFollowers] = useState(500000)
  const [initialized, setInitialized] = useState(false)
  const [criteria, setCriteria] = useState<LLMCriteria>({ ...DEFAULT_CRITERIA })
  const [llmEnabled, setLlmEnabled] = useState(true)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const keywords = threadsData?.keywords || []

  if (keywords.length > 0 && !initialized) {
    setSelected([...keywords])
    setInitialized(true)
  }

  const mutation = useMutation({
    mutationFn: submitThreads,
    onSuccess: (data) => navigate(`/tasks/${data.task_id}`),
  })

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      selected_keywords: selected.join('\n'),
      custom_keywords: customKeywords,
      min_followers: minFollowers,
      max_followers: maxFollowers,
      llm_criteria: llmEnabled ? criteria : null,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-2xl space-y-4">
      <div>
        <h3 className="font-semibold text-gray-900">Threads 博主搜索</h3>
        <p className="text-xs text-gray-500 mt-1">通过 TikHub API 搜索内容并提取博主，每个关键词约 $0.004（top + recent）</p>
      </div>

      {/* 关键词 */}
      <MultiSelect
        label="搜索关键词"
        items={keywords}
        selected={selected}
        onChange={setSelected}
      />

      <details>
        <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">补充自定义关键词</summary>
        <textarea
          value={customKeywords} onChange={(e) => setCustomKeywords(e.target.value)}
          rows={2}
          className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-gray-500 focus:border-gray-500 outline-none resize-y"
          placeholder="每行一个（建议用短词，如「港股」「恒指」）"
        />
      </details>

      {/* 粉丝范围 */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs text-gray-500 mb-1">最少粉丝</label>
          <input type="number" value={minFollowers} onChange={(e) => setMinFollowers(+e.target.value)} min={0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-gray-500 outline-none" />
        </div>
        <div>
          <label className="block text-xs text-gray-500 mb-1">最多粉丝</label>
          <input type="number" value={maxFollowers} onChange={(e) => setMaxFollowers(+e.target.value)} min={0}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-gray-500 outline-none" />
        </div>
      </div>

      {/* AI 精筛 */}
      <LLMPanel
        enabled={llmEnabled}
        onToggle={setLlmEnabled}
        criteria={criteria}
        onChange={setCriteria}
        showAdvanced={showAdvanced}
        onToggleAdvanced={() => setShowAdvanced(!showAdvanced)}
        accentClass="text-gray-800"
        ringClass="focus:ring-gray-500"
      />

      {/* 提交 */}
      <button
        type="submit"
        disabled={selected.length === 0 || mutation.isPending}
        className={`w-full py-2.5 text-white font-medium rounded-lg transition text-sm ${
          selected.length === 0 ? 'bg-gray-300 cursor-not-allowed' : 'bg-gray-900 hover:bg-gray-800'
        }`}
      >
        {mutation.isPending ? '提交中...' : `开始搜索（${selected.length} 个关键词）`}
      </button>
    </form>
  )
}
