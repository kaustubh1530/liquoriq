import { Navigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import ErrorBoundary from './ErrorBoundary'

export default function ProtectedRoute({ children }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  // Every protected page gets a boundary: one page crashing should never blank
  // the whole app (the user just sees a white screen with no way to report it).
  return <ErrorBoundary>{children}</ErrorBoundary>
}
