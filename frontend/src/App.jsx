import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

const LoginPage = lazy(() => import('./pages/LoginPage'));
import Dashboard from './pages/Dashboard';


const Loader = () => (
  <div className="h-screen w-screen bg-sovereign-950 flex items-center justify-center">
    <div className="w-12 h-12 border-4 border-sovereign-cyan border-t-transparent rounded-full animate-spin"></div>
  </div>
);

function App() {
  const isAuthenticated = !!localStorage.getItem('orgatec_token');

  return (
    <Router>
      <Suspense fallback={<Loader />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route 
            path="/dashboard/*" 
            element={isAuthenticated ? <Dashboard /> : <Navigate to="/login" />} 
          />
          <Route path="/" element={<Navigate to="/dashboard" />} />
        </Routes>
      </Suspense>
    </Router>
  );
}


export default App;
