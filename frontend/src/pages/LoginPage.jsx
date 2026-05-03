import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Shield, Mail, Lock, Eye, EyeOff, ArrowRight, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function LoginPage() {
  const { login, loading, error, clearError, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd]   = useState(false);

  useEffect(() => {
    if (isAuthenticated) navigate('/dashboard', { replace: true });
  }, [isAuthenticated, navigate]);

  useEffect(() => { clearError(); }, [email, password]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const result = await login(email, password);
    if (result.ok) navigate('/dashboard', { replace: true });
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-grid"
      style={{ background: '#09090b' }}>

      {/* Glow de fundo */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full opacity-20"
          style={{ background: 'radial-gradient(circle, rgba(99,102,241,0.5) 0%, transparent 70%)' }} />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] rounded-full opacity-10"
          style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.4) 0%, transparent 70%)' }} />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 28, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.5, ease: [0.34, 1.15, 0.64, 1] }}
        className="w-full max-w-sm mx-4 relative z-10"
      >
        {/* Card */}
        <div className="rounded-2xl p-8 relative overflow-hidden"
          style={{
            background: 'rgba(20,20,33,0.85)',
            border: '1px solid rgba(255,255,255,0.10)',
            backdropFilter: 'blur(24px)',
            boxShadow: '0 32px 64px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)',
          }}>

          {/* Linha superior com gradiente */}
          <div className="absolute top-0 left-0 right-0 h-px"
            style={{ background: 'linear-gradient(90deg, transparent, rgba(99,102,241,0.7), transparent)' }} />

          {/* Logo */}
          <motion.div
            initial={{ opacity: 0, scale: 0.75 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15, duration: 0.4, ease: [0.34, 1.2, 0.64, 1] }}
            className="flex flex-col items-center mb-8"
          >
            <div className="w-14 h-14 rounded-2xl flex items-center justify-center mb-4 animate-pulse-glow"
              style={{
                background: 'linear-gradient(135deg, #6366f1 0%, #4338ca 100%)',
                boxShadow: '0 0 28px rgba(99,102,241,0.5)',
              }}>
              <Shield size={26} className="text-white" />
            </div>
            <h1 className="text-xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>
              ORGATEC
            </h1>
            <p className="text-xs mt-1 font-medium" style={{ color: '#475569' }}>
              Sovereign Audit Platform
            </p>
          </motion.div>

          {/* Form */}
          <motion.form
            onSubmit={handleSubmit}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2, duration: 0.35 }}
            className="space-y-4"
          >
            {/* E-mail */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold" style={{ color: '#64748b' }}>
                E-mail
              </label>
              <div className="relative">
                <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: '#475569' }} />
                <input
                  type="email"
                  className="input"
                  style={{ paddingLeft: '36px' }}
                  placeholder="seu@email.com"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  required
                  autoComplete="email"
                />
              </div>
            </div>

            {/* Senha */}
            <div className="space-y-1.5">
              <label className="block text-xs font-semibold" style={{ color: '#64748b' }}>
                Senha
              </label>
              <div className="relative">
                <Lock size={14} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none"
                  style={{ color: '#475569' }} />
                <input
                  type={showPwd ? 'text' : 'password'}
                  className="input"
                  style={{ paddingLeft: '36px', paddingRight: '40px' }}
                  placeholder="••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button type="button"
                  onClick={() => setShowPwd(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 cursor-pointer transition-colors"
                  style={{ color: showPwd ? '#818cf8' : '#475569' }}>
                  {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                </button>
              </div>
            </div>

            {/* Erro */}
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs"
                style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}
              >
                <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: '#ef4444' }} />
                {error}
              </motion.div>
            )}

            <button type="submit" className="btn-primary w-full mt-1" style={{ marginTop: '6px' }} disabled={loading}>
              {loading
                ? <><Loader2 size={15} className="animate-spin" />Entrando...</>
                : <><span>Acessar plataforma</span><ArrowRight size={15} /></>
              }
            </button>
          </motion.form>

          {/* Credenciais de acesso */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.45 }}
            className="mt-6 pt-5 text-center space-y-1"
            style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}
          >
            <p className="text-xs font-mono" style={{ color: '#334155' }}>
              admin@orgatec.com.br
            </p>
            <p className="text-xs font-mono" style={{ color: '#334155' }}>
              Admin@2026!
            </p>
          </motion.div>
        </div>

        <p className="text-center mt-5 text-xs" style={{ color: '#1e293b' }}>
          ORGATEC © 2026 · Auditoria Fiscal Automatizada
        </p>
      </motion.div>
    </div>
  );
}
