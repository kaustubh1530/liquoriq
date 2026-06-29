import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { authApi, setAuthToken } from '../api/client'
import { storeApi } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(1) // 1 = account, 2 = store
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const [account, setAccount] = useState({ full_name: '', email: '', password: '' })
  const [store, setStoreForm] = useState({ name: '', address: '', city: '', state: '', zip_code: '', phone: '' })

  // Step 1 — Create account
  const handleAccount = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await authApi.register(account)
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  // Step 2 — Create store, then auto-login
  const handleStore = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      // Login to get token first
      await login(account.email, account.password)
      // Create store
      await storeApi.create(store)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail ?? 'Failed to create store.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="bg-white w-full max-w-md rounded-2xl shadow-sm border border-gray-100 p-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">🥃 LiquorIQ</h1>
        <p className="text-gray-500 text-sm mb-2">
          {step === 1 ? 'Create your account' : 'Set up your store'}
        </p>

        {/* Step indicator */}
        <div className="flex gap-2 mb-8">
          {[1, 2].map((s) => (
            <div
              key={s}
              className={`h-1.5 flex-1 rounded-full ${s <= step ? 'bg-brand-500' : 'bg-gray-100'}`}
            />
          ))}
        </div>

        {error && (
          <div className="mb-4 p-3 rounded-xl bg-red-50 text-red-600 text-sm">{error}</div>
        )}

        {step === 1 ? (
          <form onSubmit={handleAccount} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
              <input
                required
                value={account.full_name}
                onChange={(e) => setAccount({ ...account, full_name: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="John Smith"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                required
                value={account.email}
                onChange={(e) => setAccount({ ...account, email: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                required
                value={account.password}
                onChange={(e) => setAccount({ ...account, password: e.target.value })}
                className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                placeholder="Min 8 chars, include a number"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white font-semibold py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
            >
              {loading ? 'Creating account…' : 'Continue →'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleStore} className="space-y-4">
            {[
              { key: 'name',     label: 'Store name',  placeholder: "Uncle's Liquor Store" },
              { key: 'address',  label: 'Address',      placeholder: '123 Main St' },
              { key: 'city',     label: 'City',         placeholder: 'Washington' },
              { key: 'state',    label: 'State',        placeholder: 'DC' },
              { key: 'zip_code', label: 'ZIP code',     placeholder: '20001' },
              { key: 'phone',    label: 'Phone',        placeholder: '(202) 555-0100' },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input
                  required={key === 'name'}
                  value={store[key]}
                  onChange={(e) => setStoreForm({ ...store, [key]: e.target.value })}
                  className="w-full border border-gray-200 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
                  placeholder={placeholder}
                />
              </div>
            ))}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand-500 hover:bg-brand-600 text-white font-semibold py-2.5 rounded-xl text-sm transition-colors disabled:opacity-60"
            >
              {loading ? 'Setting up…' : 'Launch my store 🚀'}
            </button>
          </form>
        )}

        <p className="text-center text-sm text-gray-500 mt-6">
          Already have an account?{' '}
          <Link to="/login" className="text-brand-500 font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
