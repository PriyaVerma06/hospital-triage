/**
 * Login page.
 * Handles OAuth2 form login, loading state, error display,
 * and a "Demo accounts" quick-fill panel for testing.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';
import { Activity } from 'lucide-react';

/** Demo accounts for quick fill during development */
const DEMO_ACCOUNTS = [
  { label: 'Nurse',  username: 'nurse1', password: 'demo123' },
  { label: 'Doctor', username: 'dr1',    password: 'demo123' },
  { label: 'Admin',  username: 'admin',  password: 'demo123' },
];

export default function Login() {
  const { login, user, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  // If already logged in, redirect immediately
  if (isAuthenticated) {
    const dest = user?.role === 'NURSE' ? '/intake' : '/dashboard';
    navigate(dest, { replace: true });
    return null;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const loggedUser = await login(username, password);
      const dest = loggedUser.role === 'NURSE' ? '/intake' : '/dashboard';
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err.message === 'HTTP 401' || err.status === 401
        ? 'Incorrect username or password.'
        : err.message ?? 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(account) {
    setUsername(account.username);
    setPassword(account.password);
    setError('');
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-700 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Brand header */}
        <div className="text-center mb-6">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Activity className="text-white w-8 h-8" />
            <span className="text-white text-3xl font-bold tracking-tight">TriageOS</span>
          </div>
          <p className="text-blue-200 text-sm">Emergency Department Triage System</p>
        </div>

        {/* Login card */}
        <div className="bg-white rounded-2xl shadow-2xl p-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-6">Sign in</h2>

          <form onSubmit={handleSubmit} noValidate>
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="username">
                Username
              </label>
              <input
                id="username"
                type="text"
                autoFocus
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="e.g. nurse1"
                disabled={loading}
              />
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-1" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="••••••••"
                disabled={loading}
              />
            </div>

            {/* Inline error */}
            {error && (
              <p className="text-red-600 text-sm mb-4 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full bg-blue-700 hover:bg-blue-800 disabled:bg-blue-300 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          {/* Demo accounts quick-fill */}
          <div className="mt-6 pt-5 border-t border-gray-100">
            <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">
              Demo accounts (password: demo123)
            </p>
            <div className="flex gap-2 flex-wrap">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.username}
                  onClick={() => fillDemo(acc)}
                  type="button"
                  className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 hover:bg-gray-50 text-gray-600 transition-colors"
                >
                  {acc.label} ({acc.username})
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
