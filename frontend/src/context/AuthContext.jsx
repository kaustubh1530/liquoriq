/**
 * context/AuthContext.jsx — Global auth state
 *
 * Token is persisted in sessionStorage so it survives Vite HMR reloads
 * and page refreshes within the same browser tab.
 * Closing the tab clears it (sessionStorage lifecycle).
 */

import { createContext, useContext, useState, useEffect } from 'react'
import { authApi, setAuthToken, getAuthToken, setSelectedStore, getSelectedStore } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken]     = useState(() => getAuthToken())  // read from sessionStorage on init
  const [user, setUser]       = useState(null)
  const [store, setStore]     = useState(null)   // the SELECTED store
  const [stores, setStores]   = useState([])     // Phase 14: all accessible stores
  const [loading, setLoading] = useState(true)  // true while we re-hydrate on refresh

  // Apply /auth/me data: pick the selected store (previously chosen, else default)
  const applyMe = (me) => {
    setUser(me)
    setStores(me.stores ?? [])
    const savedId = getSelectedStore()
    const selected =
      (me.stores ?? []).find((s) => s.id === savedId) ?? me.store ?? null
    setStore(selected)
    setSelectedStore(selected?.id ?? null)
  }

  // On first load: if a token exists in sessionStorage, re-fetch the user profile
  useEffect(() => {
    const saved = getAuthToken()
    if (saved) {
      authApi.me()
        .then(({ data: me }) => applyMe(me))
        .catch(() => {
          // Token expired — clear everything
          setAuthToken(null)
          setToken(null)
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (email, password) => {
    const { data } = await authApi.login(email, password)
    const jwt = data.access_token
    setAuthToken(jwt)        // persist to sessionStorage
    setToken(jwt)            // update React state

    const { data: me } = await authApi.me()
    applyMe(me)
    return me
  }

  const logout = () => {
    setAuthToken(null)
    setSelectedStore(null)
    setToken(null)
    setUser(null)
    setStore(null)
    setStores([])
  }

  const refreshStore = async () => {
    const { data: me } = await authApi.me()
    applyMe(me)
  }

  // Phase 14: owner switches store → reload so every page refetches
  // with the new X-Store-Id (simplest correct approach for now)
  const switchStore = (storeId) => {
    setSelectedStore(storeId)
    window.location.reload()
  }

  // Don't render children until we know if the user is logged in or not
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400 text-sm">
        Loading…
      </div>
    )
  }

  return (
    <AuthContext.Provider value={{ user, store, stores, token, login, logout, loading, refreshStore, switchStore }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
