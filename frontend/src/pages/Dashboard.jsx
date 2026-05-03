import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard, Users, FileSearch, Bot, LogOut, Shield,
  ChevronRight, Menu, X, Plus, Trash2, Send, Loader2,
  TrendingUp, FileText, AlertTriangle, CheckCircle2, Search,
  Bell, Settings, BarChart3, Activity, Clock, Download, Zap,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import AuditoriaModule from './AuditoriaModule';
import BuscaSemanticaModule from './BuscaSemanticaModule';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

const NAV_GROUPS = [
  {
    label: 'Principal',
    items: [
      { to: '/dashboard',           icon: LayoutDashboard, label: 'Visão Geral' },
      { to: '/dashboard/clientes',  icon: Users,           label: 'Clientes' },
    ],
  },
  {
    label: 'Auditoria',
    items: [
      { to: '/dashboard/auditoria', icon: FileSearch, label: 'Auditoria NFA' },
      { to: '/dashboard/busca',     icon: Search,     label: 'Busca Semântica' },
      { to: '/dashboard/relatorio', icon: FileText,   label: 'Relatórios' },
      { to: '/dashboard/agente',    icon: Bot,        label: 'Agente IA' },
    ],
  },
];

const SIDEBAR_W = 228;
const SIDEBAR_COLLAPSED_W = 56;

export default function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => { logout(); navigate('/login'); };

  return (
    <div className="flex h-screen overflow-hidden" style={{ background: '#09090b' }}>

      {/* ── Sidebar ── */}
      <motion.aside
        animate={{ width: collapsed ? SIDEBAR_COLLAPSED_W : SIDEBAR_W }}
        transition={{ duration: 0.2, ease: 'easeInOut' }}
        className="shrink-0 flex flex-col overflow-hidden"
        style={{
          background: '#0a0a12',
          borderRight: '1px solid rgba(255,255,255,0.05)',
        }}
      >
        {/* Logo */}
        <div className="flex items-center gap-3 px-3 h-14 shrink-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
            style={{ background: 'linear-gradient(135deg, #6366f1, #4338ca)', boxShadow: '0 0 16px rgba(99,102,241,0.3)' }}>
            <Shield size={15} className="text-white" />
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -8 }}
                transition={{ duration: 0.15 }}
                className="min-w-0 flex-1"
              >
                <p className="text-white font-bold text-sm leading-none tracking-tight">ORGATEC</p>
                <p className="text-xs mt-0.5" style={{ color: '#334155' }}>Sovereign Audit</p>
              </motion.div>
            )}
          </AnimatePresence>
          <button
            onClick={() => setCollapsed(v => !v)}
            className="ml-auto shrink-0 cursor-pointer rounded-md p-1 transition-colors"
            style={{ color: '#334155' }}
            onMouseEnter={e => e.currentTarget.style.color = '#94a3b8'}
            onMouseLeave={e => e.currentTarget.style.color = '#334155'}
          >
            {collapsed ? <Menu size={15} /> : <X size={15} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
          {NAV_GROUPS.map(group => (
            <div key={group.label} className="mb-1">
              {!collapsed && (
                <p className="nav-section">{group.label}</p>
              )}
              {group.items.map(item => (
                <NavItem key={item.to} {...item} collapsed={collapsed} />
              ))}
            </div>
          ))}
        </nav>

        {/* User */}
        <div className="px-2 pb-3 shrink-0" style={{ borderTop: '1px solid rgba(255,255,255,0.05)' }}>
          <div className="pt-3">
            {!collapsed && (
              <div className="flex items-center gap-2.5 px-2 py-2 mb-1 rounded-lg"
                style={{ background: 'rgba(255,255,255,0.03)' }}>
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #4338ca)' }}>
                  {(user?.nome || 'U')[0].toUpperCase()}
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-semibold truncate" style={{ color: '#e2e8f0' }}>{user?.nome || 'Usuário'}</p>
                  <p className="text-[10px] truncate" style={{ color: '#475569' }}>{user?.email || ''}</p>
                </div>
              </div>
            )}
            <button
              onClick={handleLogout}
              className="nav-item w-full cursor-pointer"
              style={{ color: '#ef4444', opacity: 0.7 }}
              onMouseEnter={e => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.background = 'rgba(239,68,68,0.10)'; }}
              onMouseLeave={e => { e.currentTarget.style.opacity = '0.7'; e.currentTarget.style.background = 'transparent'; }}
              title={collapsed ? 'Sair' : undefined}
            >
              <LogOut size={15} className="shrink-0" />
              {!collapsed && <span>Sair</span>}
            </button>
          </div>
        </div>
      </motion.aside>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar user={user} />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/"          element={<HomeModule user={user} />} />
            <Route path="/clientes"  element={<ClientesModule />} />
            <Route path="/auditoria" element={<AuditoriaModule />} />
            <Route path="/busca"     element={<BuscaSemanticaModule />} />
            <Route path="/relatorio" element={<RelatorioModule />} />
            <Route path="/agente"    element={<AgenteModule />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function NavItem({ to, icon: Icon, label, collapsed }) {
  const { pathname } = useLocation();
  const active = pathname === to || (to !== '/dashboard' && pathname.startsWith(to));
  return (
    <Link to={to} className={`nav-item ${active ? 'active' : ''}`} title={collapsed ? label : undefined}>
      <Icon size={15} className="shrink-0" />
      <AnimatePresence>
        {!collapsed && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.1 }}
            className="truncate"
          >
            {label}
          </motion.span>
        )}
      </AnimatePresence>
    </Link>
  );
}

function Topbar({ user }) {
  const { pathname } = useLocation();
  const crumbs = pathname.replace('/dashboard', '').split('/').filter(Boolean);
  const LABELS = { clientes: 'Clientes', auditoria: 'Auditoria NFA', relatorio: 'Relatórios', agente: 'Agente IA' };

  return (
    <header className="topbar justify-between">
      <div className="flex items-center gap-1.5 text-sm min-w-0">
        <span className="font-medium" style={{ color: '#334155' }}>Dashboard</span>
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            <ChevronRight size={12} style={{ color: '#1e293b', flexShrink: 0 }} />
            <span className={i === crumbs.length - 1 ? 'font-semibold truncate' : 'truncate'}
              style={{ color: i === crumbs.length - 1 ? '#e2e8f0' : '#334155' }}>
              {LABELS[c] || c}
            </span>
          </React.Fragment>
        ))}
      </div>
      <div className="flex items-center gap-1.5">
        <button className="btn-ghost p-2 relative" aria-label="Notificações">
          <Bell size={15} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full" style={{ background: '#ef4444' }} />
        </button>
        <button className="btn-ghost p-2" aria-label="Configurações">
          <Settings size={15} />
        </button>
        <div className="w-px h-4 mx-1" style={{ background: 'rgba(255,255,255,0.07)' }} />
        <div className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold cursor-pointer"
          style={{ background: 'linear-gradient(135deg, #6366f1, #4338ca)' }}>
          {(user?.nome || 'U')[0].toUpperCase()}
        </div>
      </div>
    </header>
  );
}

// ── HomeModule ──────────────────────────────────────────────────────────────
function HomeModule({ user }) {
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/clientes/')
      .then(r => setClientes(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const kpis = [
    { label: 'Clientes Ativos',    value: loading ? '…' : clientes.length, icon: Users,        color: '#6366f1', glow: 'rgba(99,102,241,0.2)'  },
    { label: 'Auditorias',         value: '—',                               icon: FileSearch,   color: '#22c55e', glow: 'rgba(34,197,94,0.2)'   },
    { label: 'Status',             value: 'Online',                          icon: Activity,     color: '#3b82f6', glow: 'rgba(59,130,246,0.2)'  },
    { label: 'Versão da API',      value: 'v7.0',                            icon: Shield,       color: '#f59e0b', glow: 'rgba(245,158,11,0.2)'  },
  ];

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="max-w-6xl space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>
          Visão Geral
        </h1>
        <p className="text-sm mt-1" style={{ color: '#475569' }}>
          Bem-vindo, <span style={{ color: '#94a3b8', fontWeight: 600 }}>{user?.nome || 'usuário'}</span>.
        </p>
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {kpis.map((k, i) => (
          <motion.div key={i} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.07 }} className="kpi-card">
            <div className="flex items-center justify-between">
              <div className="w-9 h-9 rounded-lg flex items-center justify-center"
                style={{ background: `rgba(${k.color === '#6366f1' ? '99,102,241' : k.color === '#22c55e' ? '34,197,94' : k.color === '#3b82f6' ? '59,130,246' : '245,158,11'},0.12)` }}>
                <k.icon size={16} style={{ color: k.color }} />
              </div>
              <span className="badge badge-green text-[10px]">
                <TrendingUp size={9} /> ativo
              </span>
            </div>
            <div>
              <p className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>
                {k.value}
              </p>
              <p className="text-xs font-medium mt-0.5" style={{ color: '#475569' }}>{k.label}</p>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-5">
        {/* Tabela clientes recentes */}
        <div className="xl:col-span-2 card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4"
            style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            <h2 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Clientes Recentes</h2>
            <Link to="/dashboard/clientes" className="text-xs font-medium transition-colors"
              style={{ color: '#6366f1' }}
              onMouseEnter={e => e.currentTarget.style.color = '#818cf8'}
              onMouseLeave={e => e.currentTarget.style.color = '#6366f1'}>
              Ver todos →
            </Link>
          </div>
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-th">Nome</th>
                <th className="table-th">CPF/CNPJ</th>
                <th className="table-th hidden sm:table-cell">Cadastro</th>
                <th className="table-th">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={4} className="table-td text-center py-10">
                  <Loader2 size={18} className="animate-spin mx-auto" style={{ color: '#6366f1' }} />
                </td></tr>
              ) : clientes.length === 0 ? (
                <tr><td colSpan={4} className="table-td text-center py-10 text-sm" style={{ color: '#334155' }}>
                  Nenhum cliente cadastrado
                </td></tr>
              ) : clientes.slice(0, 6).map(c => (
                <tr key={c.id} className="table-row">
                  <td className="table-td font-semibold" style={{ color: '#f1f5f9' }}>{c.nome}</td>
                  <td className="table-td font-mono text-xs" style={{ color: '#64748b' }}>{c.cpf_cnpj}</td>
                  <td className="table-td hidden sm:table-cell text-xs" style={{ color: '#475569' }}>
                    {new Date(c.data_cadastro).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="table-td"><span className="badge badge-green">Ativo</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Acesso rápido */}
        <div className="card p-5 space-y-2">
          <h2 className="text-sm font-semibold mb-4" style={{ color: '#e2e8f0' }}>Acesso Rápido</h2>
          {[
            { to: '/dashboard/clientes',  label: 'Gerenciar Clientes',  icon: Users,      desc: 'Cadastros e histórico' },
            { to: '/dashboard/auditoria', label: 'Nova Auditoria NFA',  icon: FileSearch, desc: 'Upload e análise de notas' },
            { to: '/dashboard/relatorio', label: 'Ver Relatórios',      icon: FileText,   desc: 'Laudos e exportações' },
            { to: '/dashboard/agente',    label: 'Consultar Agente IA', icon: Bot,        desc: 'Chat tributário' },
          ].map(item => (
            <Link key={item.to} to={item.to}
              className="flex items-center gap-3 p-3 rounded-xl transition-all duration-150 group cursor-pointer"
              style={{ border: '1px solid rgba(255,255,255,0.06)' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(99,102,241,0.35)'; e.currentTarget.style.background = 'rgba(99,102,241,0.06)'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,255,255,0.06)'; e.currentTarget.style.background = 'transparent'; }}
            >
              <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 transition-all"
                style={{ background: 'rgba(255,255,255,0.04)' }}>
                <item.icon size={14} style={{ color: '#64748b' }} />
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold truncate" style={{ color: '#cbd5e1' }}>{item.label}</p>
                <p className="text-[11px] truncate" style={{ color: '#475569' }}>{item.desc}</p>
              </div>
              <ChevronRight size={13} style={{ color: '#334155', marginLeft: 'auto', flexShrink: 0 }} />
            </Link>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

// ── ClientesModule ──────────────────────────────────────────────────────────
function ClientesModule() {
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch]     = useState('');
  const [form, setForm]         = useState({ nome: '', cpf_cnpj: '' });
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState('');
  const toast = useToast();

  const load = useCallback(() => {
    setLoading(true);
    api.get('/clientes/').then(r => setClientes(r.data)).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const handleAdd = async (e) => {
    e.preventDefault(); setSaving(true); setError('');
    try {
      await api.post('/clientes/', form);
      setForm({ nome: '', cpf_cnpj: '' }); setShowForm(false); load();
      toast.success('Cliente cadastrado com sucesso!');
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erro ao cadastrar.';
      setError(msg);
    } finally { setSaving(false); }
  };

  const handleDelete = async (id, nome) => {
    if (!confirm(`Remover "${nome}"?`)) return;
    try {
      await api.delete(`/clientes/${id}`);
      load();
      toast.success('Cliente removido.');
    } catch {
      toast.error('Erro ao remover cliente.');
    }
  };

  const filtered = clientes.filter(c =>
    c.nome.toLowerCase().includes(search.toLowerCase()) || c.cpf_cnpj.includes(search)
  );

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="max-w-5xl space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>
            Clientes
          </h1>
          <p className="text-sm mt-1" style={{ color: '#475569' }}>{clientes.length} cliente(s) cadastrado(s)</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          <Plus size={14} /> Novo Cliente
        </button>
      </div>

      <AnimatePresence>
        {showForm && (
          <motion.div
            initial={{ opacity: 0, y: -8, height: 0 }}
            animate={{ opacity: 1, y: 0, height: 'auto' }}
            exit={{ opacity: 0, y: -8, height: 0 }}
            transition={{ duration: 0.2 }}
            className="card p-5 overflow-hidden"
          >
            <h2 className="text-sm font-semibold mb-4" style={{ color: '#e2e8f0' }}>Cadastrar Cliente</h2>
            <form onSubmit={handleAdd} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wide" style={{ color: '#475569' }}>
                  Nome / Razão Social
                </label>
                <input className="input" placeholder="Nome completo" value={form.nome}
                  onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} required />
              </div>
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold uppercase tracking-wide" style={{ color: '#475569' }}>
                  CPF / CNPJ
                </label>
                <input className="input" placeholder="Somente dígitos" value={form.cpf_cnpj}
                  onChange={e => setForm(f => ({ ...f, cpf_cnpj: e.target.value }))} required />
              </div>
              {error && (
                <div className="col-span-2 flex gap-2 items-center text-xs px-3 py-2.5 rounded-lg"
                  style={{ background: 'rgba(239,68,68,0.10)', border: '1px solid rgba(239,68,68,0.25)', color: '#f87171' }}>
                  <AlertTriangle size={13} className="shrink-0" />{error}
                </div>
              )}
              <div className="col-span-2 flex gap-2 justify-end">
                <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={saving}>
                  {saving ? <><Loader2 size={13} className="animate-spin" />Salvando...</> : <><CheckCircle2 size={13} />Cadastrar</>}
                </button>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="card overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}>
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" style={{ color: '#475569' }} />
            <input className="input-search" placeholder="Buscar cliente..." value={search}
              onChange={e => setSearch(e.target.value)} />
          </div>
          <span className="text-xs ml-auto" style={{ color: '#334155' }}>{filtered.length} resultado(s)</span>
        </div>
        <table className="w-full">
          <thead>
            <tr>
              <th className="table-th">Nome / Razão Social</th>
              <th className="table-th">CPF / CNPJ</th>
              <th className="table-th hidden md:table-cell">Cadastrado em</th>
              <th className="table-th">Status</th>
              <th className="table-th w-10" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="table-td text-center py-12">
                <Loader2 className="animate-spin mx-auto" size={18} style={{ color: '#6366f1' }} />
              </td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={5} className="table-td text-center py-12 text-sm" style={{ color: '#334155' }}>
                {search ? 'Nenhum cliente encontrado.' : 'Nenhum cliente cadastrado.'}
              </td></tr>
            ) : filtered.map(c => (
              <tr key={c.id} className="table-row">
                <td className="table-td font-semibold" style={{ color: '#f1f5f9' }}>{c.nome}</td>
                <td className="table-td font-mono text-xs" style={{ color: '#64748b' }}>{c.cpf_cnpj}</td>
                <td className="table-td hidden md:table-cell text-xs" style={{ color: '#475569' }}>
                  <span className="flex items-center gap-1">
                    <Clock size={11} />{new Date(c.data_cadastro).toLocaleDateString('pt-BR')}
                  </span>
                </td>
                <td className="table-td"><span className="badge badge-green">Ativo</span></td>
                <td className="table-td">
                  <button onClick={() => handleDelete(c.id, c.nome)}
                    className="p-1.5 rounded-lg transition-all cursor-pointer"
                    style={{ color: '#475569' }}
                    onMouseEnter={e => { e.currentTarget.style.color = '#f87171'; e.currentTarget.style.background = 'rgba(239,68,68,0.10)'; }}
                    onMouseLeave={e => { e.currentTarget.style.color = '#475569'; e.currentTarget.style.background = 'transparent'; }}>
                    <Trash2 size={13} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </motion.div>
  );
}

// ── RelatorioModule ─────────────────────────────────────────────────────────
function RelatorioModule() {
  const [laudos, setLaudos]   = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/auditoria/laudos')
      .then(r => setLaudos(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const comAlerta = laudos.filter(l => l.qtd_anomalias > 0).length;

  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="max-w-5xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>
          Relatórios
        </h1>
        <p className="text-sm mt-1" style={{ color: '#475569' }}>Laudos consolidados gerados pela Squad de Auditoria.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Laudos Gerados', value: loading ? '…' : laudos.length, icon: FileText,     color: '#6366f1' },
          { label: 'Pendentes',      value: '0',                             icon: Clock,         color: '#f59e0b' },
          { label: 'Com Alerta',     value: loading ? '…' : comAlerta,       icon: AlertTriangle, color: '#ef4444' },
        ].map((k, i) => (
          <div key={i} className="kpi-card">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center"
              style={{ background: `${k.color}20` }}>
              <k.icon size={16} style={{ color: k.color }} />
            </div>
            <div>
              <p className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>{k.value}</p>
              <p className="text-xs font-medium mt-0.5" style={{ color: '#475569' }}>{k.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
          <h2 className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>Histórico de Laudos</h2>
          <button className="btn-secondary text-xs py-1.5 px-3 gap-1.5">
            <Download size={12} /> Exportar CSV
          </button>
        </div>
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="animate-spin" size={20} style={{ color: '#6366f1' }} />
          </div>
        ) : laudos.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 gap-3">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(255,255,255,0.04)' }}>
              <BarChart3 size={22} style={{ color: '#334155' }} />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium" style={{ color: '#64748b' }}>Nenhum relatório gerado ainda</p>
              <p className="text-xs mt-1" style={{ color: '#334155' }}>Realize uma auditoria para gerar o primeiro laudo.</p>
            </div>
            <Link to="/dashboard/auditoria" className="btn-primary mt-2 text-sm">
              <FileSearch size={13} /> Iniciar Auditoria
            </Link>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr>
                <th className="table-th">#</th>
                <th className="table-th">Data</th>
                <th className="table-th text-right">Notas</th>
                <th className="table-th text-right">Valor Total</th>
                <th className="table-th text-center">Anomalias</th>
              </tr>
            </thead>
            <tbody>
              {laudos.map(l => (
                <tr key={l.id} className="table-row">
                  <td className="table-td font-mono text-xs" style={{ color: '#6366f1' }}>#{l.id}</td>
                  <td className="table-td text-xs" style={{ color: '#94a3b8' }}>
                    {l.data_auditoria ? new Date(l.data_auditoria).toLocaleString('pt-BR') : '—'}
                  </td>
                  <td className="table-td text-right font-mono" style={{ color: '#cbd5e1' }}>{l.qtd_notas}</td>
                  <td className="table-td text-right font-mono" style={{ color: '#cbd5e1' }}>
                    R$ {(l.valor_total || 0).toLocaleString('pt-BR', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="table-td text-center">
                    <span className={`badge ${l.qtd_anomalias > 0 ? 'badge-red' : 'badge-green'}`}>
                      {l.qtd_anomalias > 0 ? `${l.qtd_anomalias} alerta(s)` : 'OK'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </motion.div>
  );
}

// ── AgenteModule ────────────────────────────────────────────────────────────
function AgenteModule() {
  const [msgs, setMsgs]       = useState([{
    role: 'assistant',
    content: 'Olá! Sou o agente de auditoria ORGATEC. Faça uma pergunta sobre NFA, CTN, ICMS, reforma tributária ou qualquer assunto fiscal.',
  }]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);
  const toast = useToast();

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [msgs]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setMsgs(m => [...m, { role: 'user', content: text }]);
    setInput(''); setLoading(true);
    try {
      const res = await api.post('/agente/chat', { pergunta: text });
      setMsgs(m => [...m, { role: 'assistant', content: res.data.response }]);
    } catch (err) {
      const detail = err.response?.data?.detail || err.message || 'Erro desconhecido';
      setMsgs(m => [...m, { role: 'assistant', content: `Erro: ${detail}` }]);
      toast.error('Falha ao contatar o agente.');
    } finally { setLoading(false); }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className="max-w-3xl flex flex-col"
      style={{ height: 'calc(100vh - 8rem)' }}
    >
      <div className="mb-4">
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.03em' }}>
          Agente IA
        </h1>
        <p className="text-sm mt-1" style={{ color: '#475569' }}>
          Consulte o agente especializado em direito tributário brasileiro.
        </p>
      </div>

      <div className="card flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 shrink-0"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}>
          <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0"
            style={{ background: 'linear-gradient(135deg, #6366f1, #4338ca)' }}>
            <Bot size={14} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>ORGATEC Audit Agent</p>
            <p className="text-xs flex items-center gap-1.5" style={{ color: '#475569' }}>
              <span className="w-1.5 h-1.5 rounded-full inline-block" style={{ background: '#22c55e' }} />
              Online · CTN · LC 87/96 · EC 132/23
            </p>
          </div>
          <div className="ml-auto">
            <span className="badge badge-blue">
              <Zap size={9} /> IA Tributária
            </span>
          </div>
        </div>

        {/* Mensagens */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {msgs.map((m, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {m.role === 'assistant' && (
                <div className="w-6 h-6 rounded-full flex items-center justify-center mr-2 mt-1 shrink-0"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #4338ca)' }}>
                  <Bot size={11} className="text-white" />
                </div>
              )}
              <div className="max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed"
                style={m.role === 'user'
                  ? { background: '#6366f1', color: 'white', borderBottomRightRadius: 4 }
                  : { background: 'rgba(255,255,255,0.05)', color: '#cbd5e1', border: '1px solid rgba(255,255,255,0.08)', borderBottomLeftRadius: 4 }
                }>
                {m.role === 'assistant' ? (
                  <ReactMarkdown
                    components={{
                      h3: ({children}) => <p className="font-bold mb-1" style={{ color: '#f1f5f9' }}>{children}</p>,
                      strong: ({children}) => <strong className="font-semibold" style={{ color: '#e2e8f0' }}>{children}</strong>,
                      p: ({children}) => <p className="mb-1 last:mb-0">{children}</p>,
                      ul: ({children}) => <ul className="list-disc list-inside space-y-0.5 mb-1">{children}</ul>,
                      li: ({children}) => <li style={{ color: '#94a3b8' }}>{children}</li>,
                      code: ({children}) => <code className="px-1.5 py-0.5 rounded text-xs font-mono" style={{ background: 'rgba(255,255,255,0.08)', color: '#a5b4fc' }}>{children}</code>,
                    }}
                  >
                    {m.content}
                  </ReactMarkdown>
                ) : m.content}
              </div>
            </motion.div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="w-6 h-6 rounded-full flex items-center justify-center mr-2 mt-1 shrink-0"
                style={{ background: 'linear-gradient(135deg, #6366f1, #4338ca)' }}>
                <Bot size={11} className="text-white" />
              </div>
              <div className="px-4 py-3 rounded-2xl rounded-bl-sm"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <span className="flex gap-1">
                  {[0, 1, 2].map(j => (
                    <span key={j} className="w-1.5 h-1.5 rounded-full animate-bounce"
                      style={{ background: '#6366f1', animationDelay: `${j * 0.15}s` }} />
                  ))}
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="shrink-0 p-3 flex gap-2"
          style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
          <input
            className="input flex-1"
            placeholder="Pergunte sobre NFA, ICMS, FUNRURAL, reforma tributária..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          />
          <button className="btn-primary px-3" onClick={send} disabled={loading || !input.trim()}>
            <Send size={14} />
          </button>
        </div>
      </div>
    </motion.div>
  );
}
