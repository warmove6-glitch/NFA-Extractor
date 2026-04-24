import React, { useState, useEffect } from 'react';
import { Routes, Route, Link, useNavigate } from 'react-router-dom';
import { LayoutDashboard, Users, Search, Brain, LogOut, Shield, Send, Loader2 } from 'lucide-react';
import AuditoriaModule from './AuditoriaModule';
import MatrixBackground from '../components/MatrixBackground';

import api from '../services/api';

const SuspenseLoader = () => (
  <div className="flex items-center justify-center p-12">
    <Loader2 className="animate-spin text-sovereign-cyan" size={40} />
  </div>
);


const Dashboard = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('orgatec_token');
    window.location.href = '/login';
  };

  return (
    <div className="flex h-screen overflow-hidden bg-sovereign-950 relative">
      <MatrixBackground />
      
      {/* Sidebar */}
      <aside className="w-64 bg-sovereign-950/80 backdrop-blur-md border-r border-sovereign-800 flex flex-col p-6 z-20">
        <div className="flex items-center gap-3 mb-12">
          <Shield className="text-sovereign-cyan" size={28} />
          <h2 className="text-xl font-black tracking-tighter">ORGATEC</h2>
        </div>

        <nav className="flex-1 space-y-2">
          <NavItem icon={<LayoutDashboard size={18} />} label="Comando" to="/dashboard" />
          <NavItem icon={<Users size={18} />} label="Clientes" to="/dashboard/clientes" />
          <NavItem icon={<Search size={18} />} label="Auditoria" to="/dashboard/auditoria" />
          <NavItem icon={<Brain size={18} />} label="Agente" to="/dashboard/agente" />
        </nav>

        <button 
          onClick={handleLogout}
          className="flex items-center gap-3 text-sovereign-700 hover:text-red-400 transition-colors p-3 mt-auto"
        >
          <LogOut size={18} />
          <span className="font-bold text-xs uppercase tracking-widest">Sair</span>
        </button>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto p-12 z-10">
        <React.Suspense fallback={<SuspenseLoader />}>
          <Routes>
            <Route path="/" element={<HomeModule />} />
            <Route path="/clientes" element={<ClientesModule />} />
            <Route path="/auditoria" element={<AuditoriaModule />} />
            <Route path="/agente" element={<AgenteModule />} />
          </Routes>
        </React.Suspense>

      </main>
    </div>
  );
};

const NavItem = ({ icon, label, to }) => (
  <Link 
    to={to}
    className="flex items-center gap-3 p-3 rounded-xl transition-all text-sovereign-400 hover:bg-sovereign-cyan/10 hover:text-white"
  >
    {icon}
    <span className="font-bold text-sm">{label}</span>
  </Link>
);

const HomeModule = () => (
  <div className="max-w-4xl">
    <h1 className="text-4xl font-black mb-8 tracking-tight">Centro de Comando</h1>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
      <div className="sovereign-card p-8 bg-sovereign-900/20 backdrop-blur-md border-sovereign-800/50">
        <h3 className="text-sovereign-cyan text-lg font-bold mb-4 uppercase tracking-widest">Missão da Squad</h3>
        <p className="text-sovereign-400 leading-relaxed text-sm">
          Auditando fluxos bio-contábeis com inteligência soberana e detecção de fraudes em tempo real.
        </p>
      </div>
      <div className="sovereign-card p-8 flex flex-col items-center justify-center bg-sovereign-900/20">
        <span className="text-sovereign-700 font-bold mb-2 tracking-widest text-[10px]">SISTEMA SOBERANO</span>
        <h2 className="text-5xl font-black text-sovereign-cyan animate-pulse">ATIVO</h2>
      </div>
    </div>
  </div>
);

const ClientesModule = () => {
  const [clientes, setClientes] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/clientes/').then(res => {
      setClientes(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1 className="text-3xl font-black mb-6">Gestão de Clientes</h1>
      {loading ? <Loader2 className="animate-spin text-sovereign-cyan" /> : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {clientes.map(c => (
            <div key={c.id} className="sovereign-card p-6 bg-sovereign-900/30">
              <h3 className="font-bold text-lg">{c.nome}</h3>
              <p className="text-sovereign-500 text-sm">{c.cpf_cnpj}</p>
            </div>
          ))}
          {clientes.length === 0 && <p className="text-sovereign-600">Nenhum cliente sincronizado na malha.</p>}
        </div>
      )}
    </div>
  );
};

const AgenteModule = () => {
  const [messages, setMessages] = useState([{ role: 'assistant', content: 'Protocolo ORGATEC iniciado. Como posso auxiliar na investigação?' }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input || loading) return;
    const userMsg = { role: 'user', content: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await api.post('/agente/chat', { pergunta: input });
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }]);
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Erro de conexão com o Núcleo de Inteligência.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col max-w-3xl mx-auto">
      <h1 className="text-3xl font-black mb-6">Agente ORGATEC</h1>
      <div className="flex-1 overflow-y-auto space-y-4 mb-6 pr-4">
        {messages.map((m, i) => (
          <div key={i} className={`p-4 rounded-2xl max-w-[80%] ${m.role === 'user' ? 'ml-auto bg-sovereign-cyan/20 border border-sovereign-cyan/30' : 'bg-sovereign-900/50 border border-sovereign-800'}`}>
            <p className="text-sm leading-relaxed">{m.content}</p>
          </div>
        ))}
        {loading && <Loader2 className="animate-spin text-sovereign-cyan mx-auto" />}
      </div>
      <div className="relative">
        <input 
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyPress={e => e.key === 'Enter' && sendMessage()}
          placeholder="Digite sua dúvida tática..."
          className="w-full bg-sovereign-900 border border-sovereign-800 rounded-xl py-4 pl-6 pr-14 outline-none focus:border-sovereign-cyan transition-all"
        />
        <button onClick={sendMessage} className="absolute right-4 top-3.5 text-sovereign-cyan hover:text-white transition-colors">
          <Send size={24} />
        </button>
      </div>
    </div>
  );
};

export default Dashboard;
