import React, { useState, useEffect, useCallback } from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, FileSearch, Bot, LogOut,
  Shield, ChevronRight, Menu, X, Plus, Trash2,
  Send, Loader2, BarChart3,
} from 'lucide-react';
import AuditoriaModule from './AuditoriaModule';
import api from '../services/api';

// ── Layout shell ──────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const user = JSON.parse(localStorage.getItem('orgatec_user') || '{}');
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('orgatec_token');
    localStorage.removeItem('orgatec_user');
    navigate('/login');
  };

  const nav = [
    { to: '/dashboard',          icon: <LayoutDashboard size={16} />, label: 'Visão Geral' },
    { to: '/dashboard/clientes', icon: <Users size={16} />,           label: 'Clientes' },
    { to: '/dashboard/auditoria',icon: <FileSearch size={16} />,      label: 'Auditoria' },
    { to: '/dashboard/agente',   icon: <Bot size={16} />,             label: 'Agente IA' },
  ];

  return (
    <div className="flex h-screen bg-bg overflow-hidden">

      {/* Sidebar */}
      <aside className={`${sidebarOpen ? 'w-56' : 'w-14'} transition-all duration-200 flex-shrink-0
                         bg-surface border-r border-border flex flex-col py-4 overflow-hidden`}>

        {/* Logo + toggle */}
        <div className="flex items-center justify-between px-4 mb-6">
          {sidebarOpen && (
            <div className="flex items-center gap-2">
              <Shield size={18} className="text-brand-600 flex-shrink-0" />
              <span className="font-bold text-sm text-slate-900 whitespace-nowrap">ORGATEC</span>
            </div>
          )}
          <button onClick={() => setSidebarOpen(!sidebarOpen)}
                  className="text-slate-400 hover:text-slate-600 transition-colors ml-auto">
            {sidebarOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 space-y-0.5">
          {nav.map(item => <NavItem key={item.to} {...item} collapsed={!sidebarOpen} />)}
        </nav>

        {/* User */}
        <div className="px-2 mt-4 border-t border-border pt-4">
          {sidebarOpen ? (
            <div className="px-3 py-2">
              <p className="text-xs font-semibold text-slate-800 truncate">{user.nome || 'Usuário'}</p>
              <p className="text-xs text-slate-400 truncate">{user.email || ''}</p>
            </div>
          ) : null}
          <button onClick={handleLogout}
                  className="nav-item w-full text-red-500 hover:text-red-600 hover:bg-red-50 mt-1">
            <LogOut size={16} className="flex-shrink-0" />
            {sidebarOpen && <span>Sair</span>}
          </button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/"          element={<HomeModule user={user} />} />
            <Route path="/clientes"  element={<ClientesModule />} />
            <Route path="/auditoria" element={<AuditoriaModule />} />
            <Route path="/agente"    element={<AgenteModule />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

// ── Componentes de layout ─────────────────────────────────────────────────────
function NavItem({ to, icon, label, collapsed }) {
  const { pathname } = useLocation();
  const active = pathname === to || (to !== '/dashboard' && pathname.startsWith(to));
  return (
    <Link to={to} className={`nav-item ${active ? 'active' : ''}`}>
      <span className="flex-shrink-0">{icon}</span>
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
}

function Topbar() {
  const { pathname } = useLocation();
  const parts = pathname.replace('/dashboard', '').split('/').filter(Boolean);
  return (
    <header className="bg-surface border-b border-border px-6 py-3 flex items-center gap-2 text-sm text-slate-500">
      <span className="font-medium text-slate-700">Dashboard</span>
      {parts.map((p, i) => (
        <React.Fragment key={i}>
          <ChevronRight size={14} />
          <span className={i === parts.length - 1 ? 'font-semibold text-slate-900 capitalize' : 'capitalize'}>
            {p}
          </span>
        </React.Fragment>
      ))}
    </header>
  );
}

// ── Módulo: Home ──────────────────────────────────────────────────────────────
function HomeModule({ user }) {
  const [stats, setStats] = useState({ clientes: '—', laudos: '—' });

  useEffect(() => {
    api.get('/clientes/').then(r => setStats(s => ({ ...s, clientes: r.data.length }))).catch(() => {});
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Visão Geral</h1>
        <p className="text-sm text-slate-500 mt-0.5">Bem-vindo, {user.nome || 'usuário'}.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Clientes ativos" value={stats.clientes} icon={<Users size={18} />} color="blue" />
        <StatCard label="Status do sistema" value="Online" icon={<BarChart3 size={18} />} color="green" />
        <StatCard label="Versão da API" value="v7.0" icon={<Shield size={18} />} color="slate" />
      </div>

      <div className="card p-5">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">Acesso rápido</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[
            { to: '/dashboard/clientes',  label: 'Gerenciar clientes', icon: <Users size={15} /> },
            { to: '/dashboard/auditoria', label: 'Nova auditoria',     icon: <FileSearch size={15} /> },
            { to: '/dashboard/agente',    label: 'Consultar agente',   icon: <Bot size={15} /> },
          ].map(item => (
            <Link key={item.to} to={item.to}
                  className="flex items-center gap-2 p-3 rounded-lg border border-border
                             hover:border-brand-300 hover:bg-brand-50 transition-colors text-sm text-slate-700 font-medium">
              <span className="text-brand-600">{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, color }) {
  const colors = {
    blue:  'bg-brand-50 text-brand-600',
    green: 'bg-emerald-50 text-emerald-600',
    slate: 'bg-slate-100 text-slate-500',
  };
  return (
    <div className="card p-4 flex items-center gap-4">
      <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 ${colors[color]}`}>
        {icon}
      </div>
      <div>
        <p className="text-xs text-slate-500 font-medium">{label}</p>
        <p className="text-lg font-bold text-slate-900">{value}</p>
      </div>
    </div>
  );
}

// ── Módulo: Clientes ──────────────────────────────────────────────────────────
function ClientesModule() {
  const [clientes, setClientes]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [showForm, setShowForm]   = useState(false);
  const [form, setForm]           = useState({ nome: '', cpf_cnpj: '' });
  const [saving, setSaving]       = useState(false);
  const [error, setError]         = useState('');

  const load = useCallback(() => {
    setLoading(true);
    api.get('/clientes/').then(r => setClientes(r.data)).finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleAdd = async (e) => {
    e.preventDefault();
    setSaving(true); setError('');
    try {
      await api.post('/clientes/', form);
      setForm({ nome: '', cpf_cnpj: '' });
      setShowForm(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao cadastrar cliente.');
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm('Remover este cliente? Todos os laudos serão excluídos.')) return;
    await api.delete(`/clientes/${id}`);
    load();
  };

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-900">Clientes</h1>
          <p className="text-sm text-slate-500 mt-0.5">{clientes.length} cadastrado(s)</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(!showForm)}>
          <Plus size={15} /> Novo cliente
        </button>
      </div>

      {showForm && (
        <div className="card p-5">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Cadastrar cliente</h2>
          <form onSubmit={handleAdd} className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1 uppercase tracking-wide">Nome</label>
              <input className="input" placeholder="Nome completo" value={form.nome}
                     onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} required />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-500 mb-1 uppercase tracking-wide">CPF / CNPJ</label>
              <input className="input" placeholder="Somente dígitos" value={form.cpf_cnpj}
                     onChange={e => setForm(f => ({ ...f, cpf_cnpj: e.target.value }))} required />
            </div>
            {error && <p className="col-span-2 text-xs text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>}
            <div className="col-span-2 flex gap-2 justify-end">
              <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? 'Salvando...' : 'Cadastrar'}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card divide-y divide-border overflow-hidden">
        {loading ? (
          <div className="p-8 flex justify-center"><Loader2 className="animate-spin text-brand-600" /></div>
        ) : clientes.length === 0 ? (
          <div className="p-8 text-center text-sm text-slate-400">Nenhum cliente cadastrado.</div>
        ) : clientes.map(c => (
          <div key={c.id} className="flex items-center justify-between px-5 py-3 hover:bg-subtle transition-colors">
            <div>
              <p className="text-sm font-semibold text-slate-800">{c.nome}</p>
              <p className="text-xs text-slate-400">{c.cpf_cnpj}</p>
            </div>
            <button onClick={() => handleDelete(c.id)}
                    className="text-slate-300 hover:text-red-500 transition-colors p-1 rounded">
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Módulo: Agente IA ─────────────────────────────────────────────────────────
function AgenteModule() {
  const [msgs, setMsgs]   = useState([{ role: 'assistant', content: 'Olá! Sou o agente de auditoria ORGATEC. Como posso ajudar?' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = React.useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setMsgs(m => [...m, { role: 'user', content: text }]);
    setInput('');
    setLoading(true);
    try {
      const res = await api.post('/agente/chat', { pergunta: text });
      setMsgs(m => [...m, { role: 'assistant', content: res.data.response }]);
    } catch {
      setMsgs(m => [...m, { role: 'assistant', content: 'Erro ao conectar com o agente.' }]);
    } finally { setLoading(false); }
  };

  return (
    <div className="max-w-2xl flex flex-col h-[calc(100vh-10rem)]">
      <div className="mb-4">
        <h1 className="text-xl font-bold text-slate-900">Agente IA</h1>
        <p className="text-sm text-slate-500 mt-0.5">Consulte dúvidas sobre auditoria fiscal.</p>
      </div>

      <div className="card flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed
                ${m.role === 'user'
                  ? 'bg-brand-600 text-white rounded-br-sm'
                  : 'bg-subtle text-slate-800 rounded-bl-sm border border-border'}`}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-subtle border border-border px-4 py-2.5 rounded-2xl rounded-bl-sm">
                <Loader2 size={14} className="animate-spin text-slate-400" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <div className="border-t border-border p-3 flex gap-2">
          <input
            className="input flex-1"
            placeholder="Digite sua pergunta..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          />
          <button className="btn-primary px-3" onClick={send} disabled={loading || !input.trim()}>
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
