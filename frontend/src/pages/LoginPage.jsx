import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Shield, CheckCircle, Lock, Mail, Eye, EyeOff, AlertCircle } from 'lucide-react';
import api from '../services/api';

const FEATURES = [
  'Extração automática de Notas Fiscais Agropecuárias',
  'Auditoria multiagente com IA (Squad de 9 agentes)',
  'Relatórios fiscais, contábeis e jurídicos',
  'Conformidade CTN, LC 87/96 e Reforma Tributária EC 132/23',
];

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd]   = useState(false);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState('');

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const form = new URLSearchParams();
      form.append('username', email);
      form.append('password', password);
      const res = await api.post('/auth/login', form, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      localStorage.setItem('orgatec_token', res.data.access_token);
      localStorage.setItem('orgatec_user', JSON.stringify(res.data.user));
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.detail || 'Falha ao conectar com o servidor.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex">

      {/* Painel esquerdo — hero navy */}
      <div className="hidden lg:flex lg:w-[52%] bg-navy-900 flex-col justify-between p-12 relative overflow-hidden">
        <div className="absolute inset-0 opacity-5 pointer-events-none"
          style={{backgroundImage:'radial-gradient(circle at 1px 1px,#fff 1px,transparent 0)',backgroundSize:'32px 32px'}} />
        <div className="absolute -top-32 -right-32 w-96 h-96 bg-accent-600 rounded-full opacity-10 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-72 h-72 bg-accent-400 rounded-full opacity-10 blur-3xl pointer-events-none" />

        {/* Logo */}
        <div className="relative flex items-center gap-3">
          <div className="w-10 h-10 bg-accent-600 rounded-xl flex items-center justify-center shadow-lg">
            <Shield size={20} className="text-white" />
          </div>
          <div>
            <p className="text-white font-bold text-lg leading-none" style={{fontFamily:'Poppins,sans-serif'}}>ORGATEC</p>
            <p className="text-navy-400 text-xs">Sovereign Audit Platform</p>
          </div>
        </div>

        {/* Conteúdo central */}
        <div className="relative space-y-8">
          <div>
            <h1 className="text-white text-4xl font-bold leading-tight mb-4" style={{fontFamily:'Poppins,sans-serif'}}>
              Auditoria Fiscal<br/>com Inteligência<br/>Artificial
            </h1>
            <p className="text-navy-400 text-base leading-relaxed max-w-md">
              Plataforma soberana de extração e análise de NFA com Squad de 9 agentes especializados em direito tributário brasileiro.
            </p>
          </div>
          <ul className="space-y-3">
            {FEATURES.map((f, i) => (
              <li key={i} className="flex items-start gap-3">
                <CheckCircle size={16} className="text-accent-400 mt-0.5 shrink-0" />
                <span className="text-navy-300 text-sm">{f}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Rodapé */}
        <div className="relative flex items-center justify-between">
          <p className="text-navy-500 text-xs">© 2026 ORGATEC · v7.0</p>
          <div className="flex gap-2">
            {['SOC 2','LGPD','ISO 27001'].map(b => (
              <span key={b} className="badge badge-gray text-[10px]">{b}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Painel direito — formulário */}
      <div className="flex-1 flex items-center justify-center bg-navy-50 px-6 py-12">
        <div className="w-full max-w-sm animate-fade-in">

          {/* Header mobile */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 bg-accent-600 rounded-lg flex items-center justify-center">
              <Shield size={16} className="text-white" />
            </div>
            <span className="font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>ORGATEC</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold text-navy-900 mb-1" style={{fontFamily:'Poppins,sans-serif'}}>
              Bem-vindo de volta
            </h2>
            <p className="text-navy-500 text-sm">Acesse sua conta para continuar</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-1.5">
              <label htmlFor="email" className="block text-xs font-semibold text-navy-700 uppercase tracking-wide">
                E-mail
              </label>
              <div className="relative">
                <Mail size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-400 pointer-events-none" />
                <input id="email" type="email" autoComplete="email" required
                  className="input pl-9" placeholder="seu@email.com.br"
                  value={email} onChange={e => setEmail(e.target.value)} />
              </div>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="password" className="block text-xs font-semibold text-navy-700 uppercase tracking-wide">
                Senha
              </label>
              <div className="relative">
                <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-400 pointer-events-none" />
                <input id="password" type={showPwd ? 'text' : 'password'} autoComplete="current-password" required
                  className="input pl-9 pr-10" placeholder="••••••••••••"
                  value={password} onChange={e => setPassword(e.target.value)} />
                <button type="button" tabIndex={-1} aria-label={showPwd ? 'Ocultar senha' : 'Mostrar senha'}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-navy-400 hover:text-navy-600 transition-colors cursor-pointer"
                  onClick={() => setShowPwd(v => !v)}>
                  {showPwd ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {error && (
              <div role="alert" className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2.5 rounded-lg">
                <AlertCircle size={14} className="mt-0.5 shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <button type="submit" className="btn-primary w-full py-3" disabled={loading}>
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Autenticando...
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <Lock size={15} />
                  Entrar com segurança
                </span>
              )}
            </button>
          </form>

          <p className="text-center text-xs text-navy-400 mt-6">
            Admin padrão:{' '}
            <code className="bg-white border border-border px-1.5 py-0.5 rounded text-navy-600">
              admin@orgatec.com.br
            </code>
          </p>
        </div>
      </div>
    </div>
  );
}
