import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const NAV_ITEMS = [
  {
    to: '/dashboard',
    label: '工作台',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" />
    ),
  },
  {
    to: '/discover',
    label: '发现博主',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    ),
  },
  {
    to: '/snapshots',
    label: '快照历史',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8" />
    ),
  },
  {
    to: '/contacts',
    label: '联系博主',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    ),
  },
  {
    to: '/diff',
    label: '月度轧差',
    icon: (
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
        d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
    ),
  },
]

export default function Layout() {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen flex bg-gray-50">
      <aside className="w-60 bg-gray-900 text-gray-300 flex flex-col fixed h-full">
        <div className="px-5 py-5 border-b border-gray-800">
          <h1 className="text-lg font-bold text-white">KOL 搜索中台</h1>
          <p className="text-xs text-gray-500 mt-1">港澳财经博主发现</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `flex items-center px-3 py-2 rounded-lg text-sm transition ${
                  isActive
                    ? 'bg-gray-800 text-white'
                    : 'hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <svg className="w-5 h-5 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {item.icon}
              </svg>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-gray-800">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500 truncate">{user?.email}</span>
            <button onClick={logout} className="text-xs text-gray-500 hover:text-white transition">
              登出
            </button>
          </div>
        </div>
      </aside>
      <main className="flex-1 ml-60">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
