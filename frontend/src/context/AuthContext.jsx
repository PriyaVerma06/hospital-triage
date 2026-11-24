/**
 * AuthContext — global authentication state.
 * Stores token and user in localStorage for persistence across refreshes.
 * On mount, validates the stored token via /auth/me and clears it if invalid.
 */
import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { login as apiLogin, getMe } from '../lib/api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken]   = useState(() => localStorage.getItem('triage_token'));
  const [user, setUser]     = useState(() => {
    try { return JSON.parse(localStorage.getItem('triage_user')); }
    catch { return null; }
  });
  const [loading, setLoading] = useState(true); // true while validating token on mount

  // On mount: validate the stored token with the backend
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then((me) => {
        setUser(me);
        localStorage.setItem('triage_user', JSON.stringify(me));
      })
      .catch(() => {
        // Token invalid or expired — clear everything
        setToken(null);
        setUser(null);
        localStorage.removeItem('triage_token');
        localStorage.removeItem('triage_user');
      })
      .finally(() => setLoading(false));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  /**
   * Login: call the API, persist token + user to localStorage.
   * @throws on wrong credentials
   */
  const login = useCallback(async (username, password) => {
    const data = await apiLogin(username, password);
    setToken(data.access_token);
    setUser(data.user);
    localStorage.setItem('triage_token', data.access_token);
    localStorage.setItem('triage_user', JSON.stringify(data.user));
    return data.user;
  }, []);

  /** Logout: clear everything and redirect to /login. */
  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    localStorage.removeItem('triage_token');
    localStorage.removeItem('triage_user');
  }, []);

  /**
   * Check if the current user has at least one of the given roles.
   * @param {...string} roles - e.g. hasRole('ADMIN', 'NURSE')
   */
  const hasRole = useCallback((...roles) => {
    if (!user) return false;
    return roles.includes(user.role);
  }, [user]);

  const isAuthenticated = Boolean(token && user);

  return (
    <AuthContext.Provider value={{ token, user, loading, isAuthenticated, login, logout, hasRole }}>
      {children}
    </AuthContext.Provider>
  );
}

/** Hook to access auth context anywhere in the tree. */
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
