/**
 * context/AuthContext.jsx — Global auth state
 *
 * Token is persisted in sessionStorage so it survives Vite HMR reloads
 * and page refreshes within the same browser tab.
 * Closing the tab clears it (sessionStorage lifecycle).
 */

import { createContext, useContext, useState, useEffect } from 'react'
import { authApi, setAuthToken, getAuthToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken]     = useState(() => getAuthToken())  // read from sessionStorage on init
  const [user, setUser]       = useState(null)
  const [store, setStore]     = useState(null)
  const [loading, setLoading] = useState(true)  // true while we re-hydrate on refresh

  // On first load: if a token exists in sessionStorage, re-fetch the user profile
  useEffect(() => {
    const saved = getAuthToken()
    if (saved) {
      authApi.me()
        .then(({ data: me }) => {
          setUser(me)
          setStore(me.store ?? null)
        })
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
    setUser(me)
    setStore(me.store ?? null)
    return me
  }

  const logout = () => {
    setAuthToken(null)
    setToken(null)
    setUser(null)
    setStore(null)
  }

  const refreshStore = async () => {
    const { data: me } = await authApi.me()
    setStore(me.store ?? null)
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
    <AuthContext.Provider value={{ user, store, token, login, logout, loading, refreshStore }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
