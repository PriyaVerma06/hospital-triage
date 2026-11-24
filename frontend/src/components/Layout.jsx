/**
 * Top navigation bar + page content area.
 * Step 10: added Analytics, History, Alerts, Admin links (role-gated).
 * AlertToasts is mounted here so it appears on every page.
 */
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useState, useCallback } from 'react';
import { Activity, LogOut } from 'lucide-react';
import { useAuth } from '../context/AuthContext.jsx';
import AlertToasts, { AlertBell } from './AlertToasts.jsx';

const navLinkClass = ({ isActive }) =>
  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
    isActive
      ? 'bg-blue-700 text-white'
      : 'text-blue-100 hover:bg-blue-700 hover:text-white'
  }`;

function RoleBadge({ role }) {
  const colours = {
    NURSE:  'bg-teal-100 text-teal-800',
    DOCTOR: 'bg-purple-100 text-purple-800',
    ADMIN:  'bg-red-100 text-red-800',
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${colours[role] ?? 'bg-gray-100 text-gray-700'}`}>
      {role}
    </span>
  );
}

export default function Layout() {
  const { user, logout, hasRole } = useAuth();
  const navigate = useNavigate();

  const [alertCount, setAlertCount] = useState(0);
  const [muted, setMuted] = useState(() => localStorage.getItem('alert_muted') === 'true');

  const handleCountChange = useCallback((delta, absolute = false) => {
    setAlertCount((prev) => {
      const next = absolute ? Math.max(0, delta) : Math.max(0, prev + delta);
      return next;
    });
  }, []);

  function handleMuteToggle() {
    const next = !muted;
    setMuted(next);
    localStorage.setItem('alert_muted', String(next));
  }

  function handleLogout() {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Nav bar */}
      <nav className="bg-blue-800 shadow-md">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14">
            {/* Brand */}
            <div className="flex items-center gap-2">
              <Activity className="text-white w-5 h-5" />
              <span className="text-white font-bold text-lg tracking-tight">TriageOS</span>
            </div>

            {/* Nav links */}
            <div className="flex items-center gap-1 overflow-x-auto">
              {hasRole('NURSE', 'ADMIN') && (
                <NavLink to="/intake" className={navLinkClass}>Intake</NavLink>
              )}
              <NavLink to="/dashboard"  className={navLinkClass}>Dashboard</NavLink>
              <NavLink to="/analytics"  className={navLinkClass}>Analytics</NavLink>
              <NavLink to="/history"    className={navLinkClass}>History</NavLink>
              <NavLink to="/alerts"     className={navLinkClass}>Alerts</NavLink>
              {hasRole('ADMIN') && (
                <NavLink to="/admin" className={navLinkClass}>Admin</NavLink>
              )}
            </div>

            {/* Right: bell + user + logout */}
            <div className="flex items-center gap-2">
              <AlertBell count={alertCount} muted={muted} onMuteToggle={handleMuteToggle} />
              {user && (
                <div className="flex items-center gap-2">
                  <span className="text-blue-100 text-sm hidden sm:block">{user.full_name}</span>
                  <RoleBadge role={user.role} />
                </div>
              )}
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-blue-100 hover:text-white text-sm px-2 py-1 rounded hover:bg-blue-700 transition-colors"
                title="Logout"
              >
                <LogOut className="w-4 h-4" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Global alert toasts */}
      <AlertToasts onCountChange={handleCountChange} />

      {/* Page content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <Outlet />
      </main>
    </div>
  );
}
