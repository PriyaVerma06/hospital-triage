/**
 * Root application: wraps everything in AuthProvider + LiveProvider
 * and sets up routing.
 *
 * Routes added in Step 10:
 *   /analytics  — all roles
 *   /history    — authorized clinical staff
 *   /alerts     — all roles
  */
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext.jsx';
import { LiveProvider } from './context/LiveContext.jsx';
import Layout from './components/Layout.jsx';
import Login       from './pages/Login.jsx';
import Intake      from './pages/Intake.jsx';
import PatientDetail from './pages/PatientDetail.jsx';
import Dashboard   from './pages/Dashboard.jsx';
import Analytics   from './pages/Analytics.jsx';
import History     from './pages/History.jsx';
import Alerts      from './pages/Alerts.jsx';
import NotFound    from './pages/NotFound.jsx';

function ProtectedRoute({ children, roles }) {
  const { isAuthenticated, loading, hasRole } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-500">
        Checking session…
      </div>
    );
  }

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  if (roles && !hasRole(...roles)) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-4xl font-bold text-red-500 mb-2">403</p>
          <p className="text-gray-600 text-lg">You are not allowed to view this page.</p>
        </div>
      </div>
    );
  }

  return children;
}

/** Smart root redirect based on role */
function RootRedirect() {
  const { user, isAuthenticated, loading } = useAuth();
  if (loading) return null;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  // NURSE lands on /intake; everyone else on /dashboard
  if (user?.role === 'NURSE') return <Navigate to="/intake" replace />;
  return <Navigate to="/dashboard" replace />;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<Login />} />

      {/* Protected — shared layout (mounts AlertToasts, navbar) */}
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<RootRedirect />} />

        <Route path="/intake"
          element={<ProtectedRoute roles={['NURSE']}><Intake /></ProtectedRoute>} />

        <Route path="/patients/:id"
          element={<ProtectedRoute roles={['NURSE', 'DOCTOR']}><PatientDetail /></ProtectedRoute>} />

        <Route path="/dashboard"
          element={<ProtectedRoute roles={['NURSE', 'DOCTOR']}><Dashboard /></ProtectedRoute>} />

        {/* Step 10 routes */}
        <Route path="/analytics"
          element={<ProtectedRoute roles={['NURSE', 'DOCTOR']}><Analytics /></ProtectedRoute>} />

        <Route path="/history"
          element={<ProtectedRoute roles={['NURSE', 'DOCTOR']}><History /></ProtectedRoute>} />

        <Route path="/alerts"
          element={<ProtectedRoute roles={['NURSE', 'DOCTOR']}><Alerts /></ProtectedRoute>} />

      </Route>

      {/* 404 */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <LiveProvider>
          <AppRoutes />
        </LiveProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
