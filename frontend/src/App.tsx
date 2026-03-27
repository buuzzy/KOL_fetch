import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import DiscoverPage from './pages/DiscoverPage'
import TaskProgressPage from './pages/TaskProgressPage'
import SnapshotsPage from './pages/SnapshotsPage'
import SnapshotDetailPage from './pages/SnapshotDetailPage'
import DiffPage from './pages/DiffPage'
import ContactsPage from './pages/ContactsPage'
import TemplatesPage from './pages/TemplatesPage'
import ComposePage from './pages/ComposePage'

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
          </svg>
          <span className="text-sm text-gray-500">加载中...</span>
        </div>
      </div>
    )
  }

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to="/dashboard" /> : <LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/tasks/:taskId" element={<TaskProgressPage />} />
          <Route path="/snapshots" element={<SnapshotsPage />} />
          <Route path="/snapshots/:id" element={<SnapshotDetailPage />} />
          <Route path="/diff" element={<DiffPage />} />
          <Route path="/contacts" element={<ContactsPage />} />
          <Route path="/contacts/templates" element={<TemplatesPage />} />
          <Route path="/contacts/compose" element={<ComposePage />} />
        </Route>
      </Route>
      <Route path="*" element={<Navigate to={user ? '/dashboard' : '/login'} />} />
    </Routes>
  )
}
