import React, { useState, useEffect, useCallback, useRef } from 'react';
import { Routes, Route, Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Users, FileSearch, Bot, LogOut, Shield,
  ChevronRight, Menu, X, Plus, Trash2, Send, Loader2,
  TrendingUp, FileText, AlertTriangle, CheckCircle2, Search,
  Bell, Settings, BarChart3, Activity, Clock, Download,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import AuditoriaModule from './AuditoriaModule';
import api from '../services/api';

// ── Navegação ─────────────────────────────────────────────────────────────────
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
      { to: '/dashboard/auditoria', icon: FileSearch,  label: 'Auditoria NFA' },
      { to: '/dashboard/relatorio', icon: FileText,    label: 'Relatórios' },
      { to: '/dashboard/agente',    icon: Bot,         label: 'Agente IA' },
    ],
  },
];

// ── Layout principal ──────────────────────────────────────────────────────────
export default function Dashboard() {
  const [collapsed, setCollapsed] = useState(false);
  const user = JSON.parse(localStorage.getItem('orgatec_user') || '{}');
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('orgatec_token');
    localStorage.removeItem('orgatec_user');
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-bg overflow-hidden">

      {/* ── Sidebar navy ── */}
      <aside className={`${collapsed ? 'w-16' : 'w-60'} shrink-0 bg-navy-900 flex flex-col transition-all duration-200 overflow-hidden`}>

        {/* Logo */}
        <div className="flex items-center gap-3 px-4 h-14 border-b border-navy-800">
          <div className="w-8 h-8 bg-accent-600 rounded-lg flex items-center justify-center shrink-0">
            <Shield size={16} className="text-white" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-white font-bold text-sm leading-none" style={{fontFamily:'Poppins,sans-serif'}}>ORGATEC</p>
              <p className="text-navy-500 text-[10px] truncate">Sovereign Audit</p>
            </div>
          )}
          <button onClick={() => setCollapsed(v => !v)}
            className="ml-auto text-navy-500 hover:text-white transition-colors cursor-pointer shrink-0"
            aria-label={collapsed ? 'Expandir menu' : 'Recolher menu'}>
            {collapsed ? <Menu size={16} /> : <X size={16} />}
          </button>
        </div>

        {/* Nav */}
        <nav className="flex-1 overflow-y-auto py-4 px-2 space-y-0.5">
          {NAV_GROUPS.map(group => (
            <div key={group.label}>
              {!collapsed && (
                <p className="nav-section">{group.label}</p>
              )}
              {group.items.map(item => (
                <NavItem key={item.to} {...item} collapsed={collapsed} />
              ))}
            </div>
          ))}
        </nav>

        {/* Usuário */}
        <div className="border-t border-navy-800 p-2">
          {!collapsed && (
            <div className="flex items-center gap-3 px-3 py-2 mb-1">
              <div className="w-7 h-7 rounded-full bg-accent-600 flex items-center justify-center text-white text-xs font-bold shrink-0">
                {(user.nome || 'U')[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <p className="text-white text-xs font-semibold truncate">{user.nome || 'Usuário'}</p>
                <p className="text-navy-500 text-[10px] truncate">{user.email || ''}</p>
              </div>
            </div>
          )}
          <button onClick={handleLogout}
            className="nav-item w-full text-red-400! hover:bg-red-900/30! hover:text-red-300! cursor-pointer">
            <LogOut size={15} className="shrink-0" />
            {!collapsed && <span>Sair</span>}
          </button>
        </div>
      </aside>

      {/* ── Main ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <Topbar user={user} />
        <main className="flex-1 overflow-y-auto p-6 animate-fade-in">
          <Routes>
            <Route path="/"          element={<HomeModule user={user} />} />
            <Route path="/clientes"  element={<ClientesModule />} />
            <Route path="/auditoria" element={<AuditoriaModule />} />
            <Route path="/relatorio" element={<RelatorioModule />} />
            <Route path="/agente"    element={<AgenteModule />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

// ── NavItem ───────────────────────────────────────────────────────────────────
function NavItem({ to, icon: Icon, label, collapsed }) {
  const { pathname } = useLocation();
  const active = pathname === to || (to !== '/dashboard' && pathname.startsWith(to));
  return (
    <Link to={to} className={`nav-item ${active ? 'active' : ''}`}
      title={collapsed ? label : undefined}>
      <Icon size={16} className="shrink-0" />
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );
}

// ── Topbar ────────────────────────────────────────────────────────────────────
function Topbar({ user }) {
  const { pathname } = useLocation();
  const crumbs = pathname.replace('/dashboard', '').split('/').filter(Boolean);
  const LABELS = { clientes:'Clientes', auditoria:'Auditoria NFA', relatorio:'Relatórios', agente:'Agente IA' };

  return (
    <header className="topbar justify-between">
      {/* Breadcrumb */}
      <div className="flex items-center gap-1.5 text-sm min-w-0">
        <span className="text-navy-500 font-medium">Dashboard</span>
        {crumbs.map((c, i) => (
          <React.Fragment key={i}>
            <ChevronRight size={13} className="text-navy-300 shrink-0" />
            <span className={i === crumbs.length - 1
              ? 'font-semibold text-navy-900 truncate'
              : 'text-navy-500 truncate'}>
              {LABELS[c] || c}
            </span>
          </React.Fragment>
        ))}
      </div>

      {/* Ações */}
      <div className="flex items-center gap-2">
        <button className="btn-ghost p-2 relative" aria-label="Notificações">
          <Bell size={16} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-red-500 rounded-full" />
        </button>
        <button className="btn-ghost p-2" aria-label="Configurações">
          <Settings size={16} />
        </button>
        <div className="w-px h-5 bg-border mx-1" />
        <div className="w-8 h-8 rounded-full bg-accent-600 flex items-center justify-center text-white text-xs font-bold cursor-pointer">
          {(user?.nome || 'U')[0].toUpperCase()}
        </div>
      </div>
    </header>
  );
}

// ── HomeModule (Visão Geral) ───────────────────────────────────────────────────
function HomeModule({ user }) {
  const [clientes, setClientes] = useState([]);

  useEffect(() => {
    api.get('/clientes/').then(r => setClientes(r.data)).catch(() => {});
  }, []);

  const kpis = [
    {
      label: 'Clientes Ativos',
      value: clientes.length,
      icon: Users,
      color: 'bg-accent-50 text-accent-600',
      trend: '+2 este mês',
      trendUp: true,
    },
    {
      label: 'Auditorias Realizadas',
      value: '—',
      icon: FileSearch,
      color: 'bg-emerald-50 text-emerald-600',
      trend: 'Este exercício',
      trendUp: true,
    },
    {
      label: 'Status do Sistema',
      value: 'Online',
      icon: Activity,
      color: 'bg-green-50 text-green-600',
      trend: '99.9% uptime',
      trendUp: true,
    },
    {
      label: 'Versão da API',
      value: 'v7.0',
      icon: Shield,
      color: 'bg-navy-100 text-navy-600',
      trend: 'Estável',
      trendUp: true,
    },
  ];

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>
          Visão Geral
        </h1>
        <p className="text-navy-500 text-sm mt-0.5">
          Bem-vindo, <span className="font-semibold text-navy-700">{user.nome || 'usuário'}</span>. Aqui está o resumo do sistema.
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        {kpis.map((k, i) => (
          <div key={i} className="kpi-card">
            <div className="flex items-start justify-between">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${k.color}`}>
                <k.icon size={18} />
              </div>
              <span className={`badge text-[10px] ${k.trendUp ? 'badge-green' : 'badge-red'}`}>
                <TrendingUp size={10} />
                {k.trend}
              </span>
            </div>
            <div>
              <p className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>{k.value}</p>
              <p className="text-xs text-navy-500 font-medium">{k.label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Grid: tabela + acesso rápido */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">

        {/* Clientes recentes */}
        <div className="xl:col-span-2 card overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-border">
            <h2 className="font-semibold text-navy-900 text-sm" style={{fontFamily:'Poppins,sans-serif'}}>Clientes Recentes</h2>
            <Link to="/dashboard/clientes" className="text-xs text-accent-600 hover:text-accent-700 font-medium">
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
              {clientes.length === 0 ? (
                <tr><td colSpan={4} className="table-td text-center text-navy-400 py-8">Nenhum cliente cadastrado</td></tr>
              ) : clientes.slice(0, 5).map(c => (
                <tr key={c.id} className="table-row">
                  <td className="table-td font-semibold text-navy-900">{c.nome}</td>
                  <td className="table-td font-mono text-xs text-navy-500">{c.cpf_cnpj}</td>
                  <td className="table-td hidden sm:table-cell text-navy-400 text-xs">
                    {new Date(c.data_cadastro).toLocaleDateString('pt-BR')}
                  </td>
                  <td className="table-td"><span className="badge badge-green">Ativo</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Acesso rápido */}
        <div className="card p-5 space-y-3">
          <h2 className="font-semibold text-navy-900 text-sm mb-4" style={{fontFamily:'Poppins,sans-serif'}}>Acesso Rápido</h2>
          {[
            { to: '/dashboard/clientes',  label: 'Gerenciar Clientes',   icon: Users,       desc: 'Cadastros e histórico' },
            { to: '/dashboard/auditoria', label: 'Nova Auditoria NFA',   icon: FileSearch,  desc: 'Upload e análise de notas' },
            { to: '/dashboard/relatorio', label: 'Ver Relatórios',       icon: FileText,    desc: 'Laudos e exportações' },
            { to: '/dashboard/agente',    label: 'Consultar Agente IA',  icon: Bot,         desc: 'Chat tributário' },
          ].map(item => (
            <Link key={item.to} to={item.to}
              className="flex items-center gap-3 p-3 rounded-lg border border-border hover:border-accent-200 hover:bg-accent-50 transition-all duration-150 group">
              <div className="w-8 h-8 rounded-lg bg-navy-50 group-hover:bg-accent-100 flex items-center justify-center transition-colors shrink-0">
                <item.icon size={15} className="text-navy-500 group-hover:text-accent-600 transition-colors" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-semibold text-navy-800 truncate">{item.label}</p>
                <p className="text-xs text-navy-400 truncate">{item.desc}</p>
              </div>
              <ChevronRight size={14} className="text-navy-300 ml-auto shrink-0 group-hover:text-accent-500 transition-colors" />
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── ClientesModule ────────────────────────────────────────────────────────────
function ClientesModule() {
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch]     = useState('');
  const [form, setForm]         = useState({ nome: '', cpf_cnpj: '' });
  const [saving, setSaving]     = useState(false);
  const [error, setError]       = useState('');

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
    } catch (err) {
      setError(err.response?.data?.detail || 'Erro ao cadastrar.');
    } finally { setSaving(false); }
  };

  const handleDelete = async (id) => {
    if (!confirm('Remover este cliente?')) return;
    await api.delete(`/clientes/${id}`); load();
  };

  const filtered = clientes.filter(c =>
    c.nome.toLowerCase().includes(search.toLowerCase()) ||
    c.cpf_cnpj.includes(search)
  );

  return (
    <div className="max-w-5xl space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>Clientes</h1>
          <p className="text-navy-500 text-sm mt-0.5">{clientes.length} cliente(s) cadastrado(s)</p>
        </div>
        <button className="btn-primary" onClick={() => setShowForm(v => !v)}>
          <Plus size={15} /> Novo Cliente
        </button>
      </div>

      {showForm && (
        <div className="card p-5 animate-fade-in">
          <h2 className="font-semibold text-navy-900 mb-4 text-sm" style={{fontFamily:'Poppins,sans-serif'}}>Cadastrar Cliente</h2>
          <form onSubmit={handleAdd} className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-navy-600 uppercase tracking-wide">Nome / Razão Social</label>
              <input className="input" placeholder="Nome completo" value={form.nome}
                onChange={e => setForm(f => ({ ...f, nome: e.target.value }))} required />
            </div>
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-navy-600 uppercase tracking-wide">CPF / CNPJ</label>
              <input className="input" placeholder="Somente dígitos" value={form.cpf_cnpj}
                onChange={e => setForm(f => ({ ...f, cpf_cnpj: e.target.value }))} required />
            </div>
            {error && (
              <div className="col-span-2 flex gap-2 items-center bg-red-50 border border-red-200 text-red-700 text-xs px-3 py-2.5 rounded-lg">
                <AlertTriangle size={14} className="shrink-0" />{error}
              </div>
            )}
            <div className="col-span-2 flex gap-2 justify-end pt-1">
              <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>Cancelar</button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? <><Loader2 size={14} className="animate-spin" />Salvando...</> : <><CheckCircle2 size={14} />Cadastrar</>}
              </button>
            </div>
          </form>
        </div>
      )}

      <div className="card overflow-hidden">
        {/* Barra de busca */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-navy-50">
          <div className="relative flex-1 max-w-xs">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-navy-400 pointer-events-none" />
            <input className="input-search" placeholder="Buscar cliente..." value={search}
              onChange={e => setSearch(e.target.value)} />
          </div>
          <span className="text-xs text-navy-400 ml-auto">{filtered.length} resultado(s)</span>
        </div>

        <table className="w-full">
          <thead>
            <tr>
              <th className="table-th">Nome / Razão Social</th>
              <th className="table-th">CPF / CNPJ</th>
              <th className="table-th hidden md:table-cell">Cadastrado em</th>
              <th className="table-th">Status</th>
              <th className="table-th w-12" />
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={5} className="table-td text-center py-12">
                <Loader2 className="animate-spin mx-auto text-accent-600" />
              </td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={5} className="table-td text-center text-navy-400 py-12">
                {search ? 'Nenhum cliente encontrado.' : 'Nenhum cliente cadastrado.'}
              </td></tr>
            ) : filtered.map(c => (
              <tr key={c.id} className="table-row">
                <td className="table-td font-semibold text-navy-900">{c.nome}</td>
                <td className="table-td font-mono text-xs text-navy-500">{c.cpf_cnpj}</td>
                <td className="table-td hidden md:table-cell text-navy-400 text-xs">
                  <span className="flex items-center gap-1">
                    <Clock size={11} />{new Date(c.data_cadastro).toLocaleDateString('pt-BR')}
                  </span>
                </td>
                <td className="table-td"><span className="badge badge-green">Ativo</span></td>
                <td className="table-td">
                  <button onClick={() => handleDelete(c.id)}
                    className="p-1.5 rounded-lg text-navy-300 hover:text-red-500 hover:bg-red-50 transition-all cursor-pointer"
                    aria-label="Remover cliente">
                    <Trash2 size={14} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── RelatorioModule ────────────────────────────────────────────────────────────
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
    <div className="max-w-5xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>Relatórios</h1>
        <p className="text-navy-500 text-sm mt-0.5">Laudos consolidados gerados pela Squad de Auditoria.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Laudos Gerados', value: loading ? '…' : laudos.length, icon: FileText, color: 'bg-accent-50 text-accent-600' },
          { label: 'Pendentes',      value: '0',                            icon: Clock,        color: 'bg-amber-50 text-amber-600' },
          { label: 'Com Alerta',     value: loading ? '…' : comAlerta,      icon: AlertTriangle, color: 'bg-red-50 text-red-600' },
        ].map((k, i) => (
          <div key={i} className="kpi-card">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${k.color}`}>
              <k.icon size={18} />
            </div>
            <div>
              <p className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>{k.value}</p>
              <p className="text-xs text-navy-500 font-medium">{k.label}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="card overflow-hidden">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <h2 className="font-semibold text-navy-900 text-sm" style={{fontFamily:'Poppins,sans-serif'}}>Histórico de Laudos</h2>
          <button className="btn-secondary text-xs py-1.5 px-3 gap-1.5">
            <Download size={13} /> Exportar CSV
          </button>
        </div>
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="w-6 h-6 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : laudos.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-navy-400">
            <BarChart3 size={40} className="mb-3 opacity-30" />
            <p className="text-sm font-medium">Nenhum relatório gerado ainda</p>
            <p className="text-xs mt-1">Realize uma auditoria para gerar o primeiro laudo.</p>
            <Link to="/dashboard/auditoria" className="btn-primary mt-4 text-sm">
              <FileSearch size={14} /> Iniciar Auditoria
            </Link>
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-bg text-navy-500 text-xs uppercase">
              <tr>
                <th className="px-5 py-3 text-left">#</th>
                <th className="px-5 py-3 text-left">Data</th>
                <th className="px-5 py-3 text-right">Notas</th>
                <th className="px-5 py-3 text-right">Valor Total</th>
                <th className="px-5 py-3 text-center">Anomalias</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {laudos.map(l => (
                <tr key={l.id} className="hover:bg-bg transition-colors">
                  <td className="px-5 py-3 font-mono text-navy-600">#{l.id}</td>
                  <td className="px-5 py-3 text-navy-700">{l.data_auditoria ? new Date(l.data_auditoria).toLocaleString('pt-BR') : '—'}</td>
                  <td className="px-5 py-3 text-right text-navy-700">{l.qtd_notas}</td>
                  <td className="px-5 py-3 text-right text-navy-700">R$ {(l.valor_total || 0).toLocaleString('pt-BR', {minimumFractionDigits:2})}</td>
                  <td className="px-5 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${l.qtd_anomalias > 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                      {l.qtd_anomalias > 0 ? `${l.qtd_anomalias} alerta(s)` : 'OK'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── AgenteModule ──────────────────────────────────────────────────────────────
function AgenteModule() {
  const [msgs, setMsgs]     = useState([{ role: 'assistant', content: 'Olá! Sou o agente de auditoria ORGATEC. Faça uma pergunta sobre NFA, CTN, ICMS, reforma tributária ou qualquer assunto fiscal.' }]);
  const [input, setInput]   = useState('');
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

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
    } finally { setLoading(false); }
  };

  return (
    <div className="max-w-3xl flex flex-col" style={{height:'calc(100vh - 8rem)'}}>
      <div className="mb-4">
        <h1 className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>Agente IA</h1>
        <p className="text-navy-500 text-sm mt-0.5">Consulte o agente especializado em direito tributário brasileiro.</p>
      </div>

      <div className="card flex-1 flex flex-col overflow-hidden">
        {/* Cabeçalho */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border bg-navy-50">
          <div className="w-8 h-8 bg-accent-600 rounded-full flex items-center justify-center">
            <Bot size={15} className="text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-navy-900">ORGATEC Audit Agent</p>
            <p className="text-xs text-navy-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 inline-block" />
              Online · CTN · LC 87/96 · EC 132/23
            </p>
          </div>
        </div>

        {/* Mensagens */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {msgs.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'} animate-fade-in`}>
              {m.role === 'assistant' && (
                <div className="w-6 h-6 bg-accent-600 rounded-full flex items-center justify-center mr-2 mt-1 shrink-0">
                  <Bot size={12} className="text-white" />
                </div>
              )}
              <div className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed
                ${m.role === 'user'
                  ? 'bg-accent-600 text-white rounded-br-sm'
                  : 'bg-navy-50 text-navy-800 rounded-bl-sm border border-border'}`}>
                {m.role === 'assistant' ? (
                  <ReactMarkdown
                    components={{
                      h3: ({children}) => <p className="font-bold text-navy-900 mb-1">{children}</p>,
                      strong: ({children}) => <strong className="font-semibold text-navy-900">{children}</strong>,
                      em: ({children}) => <em className="italic">{children}</em>,
                      p: ({children}) => <p className="mb-1 last:mb-0">{children}</p>,
                      ul: ({children}) => <ul className="list-disc list-inside space-y-0.5 mb-1">{children}</ul>,
                      ol: ({children}) => <ol className="list-decimal list-inside space-y-0.5 mb-1">{children}</ol>,
                      li: ({children}) => <li className="text-navy-700">{children}</li>,
                      hr: () => <hr className="my-2 border-border" />,
                      table: ({children}) => <table className="text-xs border-collapse w-full my-1">{children}</table>,
                      th: ({children}) => <th className="border border-border px-2 py-0.5 bg-navy-100 font-semibold text-left">{children}</th>,
                      td: ({children}) => <td className="border border-border px-2 py-0.5">{children}</td>,
                      code: ({children}) => <code className="bg-navy-100 px-1 rounded text-xs font-mono">{children}</code>,
                    }}
                  >
                    {m.content}
                  </ReactMarkdown>
                ) : m.content}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start animate-fade-in">
              <div className="w-6 h-6 bg-accent-600 rounded-full flex items-center justify-center mr-2 mt-1 shrink-0">
                <Bot size={12} className="text-white" />
              </div>
              <div className="bg-navy-50 border border-border px-4 py-3 rounded-2xl rounded-bl-sm">
                <span className="flex gap-1">
                  {[0,1,2].map(i => (
                    <span key={i} className="w-1.5 h-1.5 bg-navy-400 rounded-full animate-bounce"
                      style={{animationDelay:`${i*0.15}s`}} />
                  ))}
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-border p-3 flex gap-2">
          <input
            className="input flex-1"
            placeholder="Pergunte sobre NFA, ICMS, FUNRURAL, reforma tributária..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          />
          <button className="btn-primary px-3" onClick={send} disabled={loading || !input.trim()}
            aria-label="Enviar mensagem">
            <Send size={15} />
          </button>
        </div>
      </div>
    </div>
  );
}
