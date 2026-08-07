import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
// Drill-downs: the dashboard stays scannable, the detail lives here.
import InventoryIntelligence from './pages/InventoryIntelligence'
import CategoryIntelligence from './pages/CategoryIntelligence'
import BusinessIntelligence from './pages/BusinessIntelligence'
import AIAdvisor from './pages/AIAdvisor'
import CampaignWorkspace from './pages/CampaignWorkspace'
import Uploads from './pages/Uploads'
import AIStrategy from './pages/AIStrategy'
import Creative from './pages/Creative'
import LabelStudio from './pages/LabelStudio'
import Transfers from './pages/Transfers'
import Customers from './pages/Customers'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected */}
          <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/campaign/:strategyId" element={<ProtectedRoute><CampaignWorkspace /></ProtectedRoute>} />
          <Route path="/advisor"     element={<ProtectedRoute><AIAdvisor /></ProtectedRoute>} />
          <Route path="/intelligence" element={<ProtectedRoute><BusinessIntelligence /></ProtectedRoute>} />
          <Route path="/inventory"  element={<ProtectedRoute><InventoryIntelligence /></ProtectedRoute>} />
          <Route path="/categories" element={<ProtectedRoute><CategoryIntelligence /></ProtectedRoute>} />
          <Route path="/uploads"   element={<ProtectedRoute><Uploads /></ProtectedRoute>} />
          <Route path="/ai"        element={<ProtectedRoute><AIStrategy /></ProtectedRoute>} />
          <Route path="/creative"  element={<ProtectedRoute><Creative /></ProtectedRoute>} />
          <Route path="/labels"    element={<ProtectedRoute><LabelStudio /></ProtectedRoute>} />
          <Route path="/transfers" element={<ProtectedRoute><Transfers /></ProtectedRoute>} />
          <Route path="/customers" element={<ProtectedRoute><Customers /></ProtectedRoute>} />

          {/* Default */}
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
