import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './context/ToastContext';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const Dashboard  = lazy(() => import('./pages/Dashboard'));

const Loader = () => (
  <div className="h-screen w-screen flex items-center justify-center" style={{ background: '#09090b' }}>
    <div className="flex flex-col items-center gap-4">
      <div className="w-10 h-10 rounded-xl flex items-center justify-center"
        style={{ background: 'rgba(99,102,241,0.15)', boxShadow: '0 0 20px rgba(99,102,241,0.3)' }}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"
            stroke="#818cf8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>
      <div className="w-6 h-6 border-2 rounded-full animate-spin"
        style={{ borderColor: 'rgba(99,102,241,0.3)', borderTopColor: '#818cf8' }} />
    </div>
  </div>
);

function PrivateRoute({ children }) {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function AppRoutes() {
  return (
    <Suspense fallback={<Loader />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/dashboard/*" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <ToastProvider>
          <AppRoutes />
        </ToastProvider>
      </AuthProvider>
    </Router>
  );
}
