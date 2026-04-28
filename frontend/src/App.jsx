import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

const LoginPage = lazy(() => import('./pages/LoginPage'));
const Dashboard = lazy(() => import('./pages/Dashboard'));

const Loader = () => (
  <div className="h-screen w-screen bg-bg flex items-center justify-center">
    <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
  </div>
);

/** Verifica se o token existe e não expirou */
function isTokenValid(token) {
  if (!token) return false;
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    return payload.exp * 1000 > Date.now();
  } catch {
    return false;
  }
}

function PrivateRoute({ children }) {
  const token = localStorage.getItem('orgatec_token');
  const refreshToken = localStorage.getItem('orgatec_refresh_token');

  // Access válido → entra direto
  if (isTokenValid(token)) return children;

  // Access expirado mas tem refresh → deixa o interceptor do api.js renovar
  if (refreshToken && isTokenValid(refreshToken)) return children;

  // Sem tokens válidos → login
  return <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Router>
      <Suspense fallback={<Loader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/dashboard/*"
            element={<PrivateRoute><Dashboard /></PrivateRoute>}
          />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </Suspense>
    </Router>
  );
}
