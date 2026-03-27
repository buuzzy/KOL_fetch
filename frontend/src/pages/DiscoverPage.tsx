import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { getKeywords, submitYoutube } from '../api/discover'

const DEPTH_OPTIONS = [
  { value: 'fast', label: '快速扫描', desc: '约 2 分钟，适合日常快速检查' },
  { value: 'standard', label: '标准搜索', desc: '约 5 分钟，覆盖面适中', recommended: true },
  { value: 'deep', label: '深度搜索', desc: '约 10 分钟，最全面，消耗更多 API 配额' },
]

const INACTIVE_OPTIONS = [
  { value: 30, label: '最近 1 个月' },
  { value: 90, label: '最近 3 个月', recommended: true },
  { value: 180, label: '最近 6 个月' },
  { value: 365, label: '最近 1 年' },
  { value: 0, label: '不限' },
]

export default function DiscoverPage() {
  const navigate = useNavigate()
  const { data: keywords } = useQuery({ queryKey: ['keywords'], queryFn: getKeywords })

  const [selected, setSelected] = useState<string[]>([])
  const [customKeywords, setCustomKeywords] = useState('')
  const [minSubs, setMinSubs] = useState(1000)
  const [maxSubs, setMaxSubs] = useState(200000)
  const [depth, setDepth] = useState('standard')
  const [inactiveDays, setInactiveDays] = useState(90)
  const [initialized, setInitialized] = useState(false)

  if (keywords && !initialized) {
    setSelected([...keywords.core])
    setInitialized(true)
  }

  const allKeywords = keywords ? [...keywords.core, ...keywords.extended, ...keywords.long_tail] : []

  const mutation = useMutation({
    mutationFn: submitYoutube,
    onSuccess: (data) => navigate(`/tasks/${data.task_id}`),
  })

  const toggle = (kw: string) => {
    setSelected((prev) => prev.includes(kw) ? prev.filter((k) => k !== kw) : [...prev, kw])
  }

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    mutation.mutate({
      selected_keywords: selected.join('\n'),
      custom_keywords: customKeywords,
      min_subscribers: minSubs,
      max_subscribers: maxSubs,
      depth,
      max_inactive_days: inactiveDays,
    })
  }

  const KeywordGroup = ({ title, items }: { title: string; items: string[] }) => (
    <div className="mb-3">
      <p className="text-xs text-gray-400 mb-1.5 font-medium uppercase tracking-wide">{title}</p>
      <div className="flex flex-wrap gap-2">
        {items.map((kw) => (
          <button
            key={kw} type="button" onClick={() => toggle(kw)}
            className={`px-3 py-1.5 rounded-full border text-sm transition cursor-pointer ${
              selected.includes(kw)
                ? 'bg-blue-50 border-blue-400 text-blue-700'
                : 'bg-gray-50 border-gray-200 text-gray-500 hover:border-gray-300'
            }`}
          >
            {kw}
          </button>
        ))}
      </div>
    </div>
  )

  return (
    <>
      <div className="mb-6">
        <h2 className="text-2xl font-bold text-gray-900">发现博主</h2>
        <p className="text-gray-500 mt-1">搜索港澳财经博主</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 max-w-3xl space-y-6">
        <div>
          <h3 className="font-semibold text-gray-900 text-lg">YouTube 博主搜索</h3>
          <p className="text-sm text-gray-500 mt-1">系统会用你选择的关键词在 YouTube 上搜索，找到港澳财经相关的个人博主</p>
        </div>

        {keywords && (
          <div>
            <label className="block text-sm font-medium text-gray-900 mb-1">搜索关键词</label>
            <p className="text-xs text-gray-500 mb-3">选择你感兴趣的搜索词，选得越多，找到的博主越多（但耗时也越长）</p>

            <div className="flex items-center space-x-3 mb-3">
              <button type="button" onClick={() => setSelected([...allKeywords])} className="text-xs text-blue-600 hover:text-blue-800 font-medium">全选</button>
              <span className="text-gray-300">|</span>
              <button type="button" onClick={() => setSelected([...keywords.core])} className="text-xs text-blue-600 hover:text-blue-800 font-medium">只选推荐词</button>
              <span className="text-gray-300">|</span>
              <button type="button" onClick={() => setSelected([])} className="text-xs text-blue-600 hover:text-blue-800 font-medium">清空</button>
              <span className="text-xs text-gray-400 ml-auto">已选 {selected.length} / {allKeywords.length} 个</span>
            </div>

            <KeywordGroup title="推荐" items={keywords.core} />
            <KeywordGroup title="进阶" items={keywords.extended} />
            <KeywordGroup title="长尾 / 细分" items={keywords.long_tail} />

            <details className="mt-3">
              <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">补充自定义关键词（可选）</summary>
              <textarea
                value={customKeywords} onChange={(e) => setCustomKeywords(e.target.value)}
                rows={2}
                className="w-full mt-2 px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-y"
                placeholder="每行一个，会和上面选中的词一起使用"
              />
            </details>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">目标博主规模</label>
          <p className="text-xs text-gray-500 mb-3">筛选粉丝量在此范围内的博主</p>
          <div className="grid grid-cols-2 gap-4 max-w-md">
            <div>
              <label className="block text-xs text-gray-500 mb-1">最少订阅数</label>
              <input type="number" value={minSubs} onChange={(e) => setMinSubs(+e.target.value)} min={0}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">最多订阅数</label>
              <input type="number" value={maxSubs} onChange={(e) => setMaxSubs(+e.target.value)} min={0}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none" />
            </div>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">搜索深度</label>
          <p className="text-xs text-gray-500 mb-3">搜索越深，找到的博主越全面，但耗时和 API 配额消耗也越大</p>
          <div className="space-y-2 max-w-lg">
            {DEPTH_OPTIONS.map((opt) => (
              <label key={opt.value}
                className={`flex items-start p-3 rounded-lg border cursor-pointer transition ${
                  depth === opt.value ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
                }`}>
                <input type="radio" checked={depth === opt.value} onChange={() => setDepth(opt.value)}
                  className="mt-0.5 mr-3 text-blue-600" />
                <div>
                  <span className="text-sm font-medium text-gray-900">{opt.label}</span>
                  {opt.recommended && (
                    <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">推荐</span>
                  )}
                  <p className="text-xs text-gray-500 mt-0.5">{opt.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-900 mb-1">活跃度要求</label>
          <p className="text-xs text-gray-500 mb-3">过滤掉长期不更新的"僵尸"频道</p>
          <div className="flex flex-wrap gap-2 max-w-lg">
            {INACTIVE_OPTIONS.map((opt) => (
              <label key={opt.value}
                className={`flex items-center px-3 py-2 rounded-lg border cursor-pointer transition ${
                  inactiveDays === opt.value ? 'border-blue-400 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
                }`}>
                <input type="radio" checked={inactiveDays === opt.value} onChange={() => setInactiveDays(opt.value)}
                  className="mr-2 text-blue-600" />
                <span className="text-sm">{opt.label}</span>
                {opt.recommended && (
                  <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">推荐</span>
                )}
              </label>
            ))}
          </div>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            disabled={selected.length === 0 || mutation.isPending}
            className={`px-6 py-2.5 text-white font-medium rounded-lg transition text-sm ${
              selected.length === 0 ? 'bg-gray-300 cursor-not-allowed' : 'bg-red-600 hover:bg-red-700'
            }`}
          >
            {mutation.isPending ? '提交中...' : '开始搜索'}
          </button>
          {selected.length === 0 && <span className="text-xs text-gray-400 ml-3">请至少选择一个关键词</span>}
        </div>
      </form>
    </>
  )
}
