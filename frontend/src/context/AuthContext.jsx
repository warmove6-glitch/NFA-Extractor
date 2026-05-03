import React, { createContext, useContext, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(() => {
    try { return JSON.parse(localStorage.getItem('orgatec_user') || 'null'); } catch { return null; }
  });
  const [token, setToken]     = useState(() => localStorage.getItem('orgatec_token') || null);
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState('');

  const login = useCallback(async (email, password) => {
    setLoading(true); setError('');
    try {
      const form = new URLSearchParams({ username: email, password });
      const { data } = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      localStorage.setItem('orgatec_token', data.access_token);
      localStorage.setItem('orgatec_user', JSON.stringify(data.user));
      setToken(data.access_token);
      setUser(data.user);
      return { ok: true };
    } catch (err) {
      const msg = err.response?.data?.detail || 'Falha ao conectar com o servidor.';
      setError(msg);
      return { ok: false, error: msg };
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('orgatec_token');
    localStorage.removeItem('orgatec_user');
    setToken(null);
    setUser(null);
  }, []);

  const clearError = useCallback(() => setError(''), []);

  return (
    <AuthContext.Provider value={{ user, token, loading, error, login, logout, clearError, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth deve ser usado dentro de AuthProvider');
  return ctx;
};
