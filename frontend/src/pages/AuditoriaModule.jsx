import React, { useState, useEffect, useRef } from 'react';
import { Upload, FileText, CheckCircle, AlertTriangle, Loader2, Clock, X, Download } from 'lucide-react';
import api from '../services/api';

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_CYCLES  = 450; // 15 min

export default function AuditoriaModule() {
  const [clientes, setClientes]     = useState([]);
  const [clienteId, setClienteId]   = useState('');
  const [files, setFiles]           = useState([]);
  const [taskId, setTaskId]         = useState(null);
  const [phase, setPhase]           = useState('idle'); // idle | uploading | processing | completed | error | timeout
  const [progress, setProgress]     = useState({ pct: 0, label: '', resultado: '' });
  const [apiError, setApiError]     = useState('');
  const dropRef = useRef(null);

  // Carrega lista de clientes
  useEffect(() => {
    api.get('/clientes/').then(r => setClientes(r.data)).catch(() => {});
  }, []);

  // Drag & drop
  useEffect(() => {
    const zone = dropRef.current;
    if (!zone) return;
    const prevent = e => e.preventDefault();
    const drop = e => {
      e.preventDefault();
      const dropped = Array.from(e.dataTransfer.files).filter(f => f.type === 'application/pdf');
      setFiles(prev => [...prev, ...dropped]);
    };
    zone.addEventListener('dragover', prevent);
    zone.addEventListener('drop', drop);
    return () => { zone.removeEventListener('dragover', prevent); zone.removeEventListener('drop', drop); };
  }, []);

  // Polling de status
  useEffect(() => {
    if (!taskId || phase !== 'processing') return;
    let cycles = 0;
    const interval = setInterval(async () => {
      if (++cycles > POLL_MAX_CYCLES) {
        clearInterval(interval);
        setPhase('timeout');
        return;
      }
      try {
        const { data } = await api.get(`/auditoria/status/${taskId}`);
        setProgress({
          pct:       data.progress ?? 0,
          label:     (data.status ?? '').replace(/_/g, ' '),
          resultado: data.resultado ?? '',
        });
        if (data.status === 'concluido') { clearInterval(interval); setPhase('completed'); }
        if (data.status === 'erro')      { clearInterval(interval); setPhase('error'); setApiError(data.erro ?? 'Erro desconhecido.'); }
      } catch { /* ignora erros transientes */ }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [taskId, phase]);

  const handleUpload = async () => {
    if (!files.length || !clienteId) return;
    setPhase('uploading');
    setApiError('');
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    try {
      const res = await api.post(`/auditoria/upload/${clienteId}`, formData);
      setTaskId(res.data.task_id);
      setPhase('processing');
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Erro ao iniciar auditoria.');
      setPhase('error');
    }
  };

  const reset = () => { setFiles([]); setTaskId(null); setPhase('idle'); setProgress({ pct: 0, label: '', resultado: '' }); setApiError(''); };

  const removeFile = (idx) => setFiles(f => f.filter((_, i) => i !== idx));

  return (
    <div className="max-w-4xl space-y-4">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Auditoria Fiscal</h1>
        <p className="text-sm text-slate-500 mt-0.5">Envie NFAs em PDF para análise automatizada.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">

        {/* Painel esquerdo: upload */}
        <div className="lg:col-span-2 space-y-3">

          {/* Seleção de cliente */}
          <div className="card p-4">
            <label className="block text-xs font-semibold text-slate-500 mb-1.5 uppercase tracking-wide">
              Cliente
            </label>
            <select className="input" value={clienteId} onChange={e => setClienteId(e.target.value)}>
              <option value="">Selecione um cliente...</option>
              {clientes.map(c => (
                <option key={c.id} value={c.id}>{c.nome}</option>
              ))}
            </select>
            {clientes.length === 0 && (
              <p className="text-xs text-slate-400 mt-1.5">
                Nenhum cliente. <a href="/dashboard/clientes" className="text-brand-600 hover:underline">Cadastre um →</a>
              </p>
            )}
          </div>

          {/* Drop zone */}
          <div
            ref={dropRef}
            className="card p-6 border-2 border-dashed border-border hover:border-brand-300 transition-colors cursor-pointer"
            onClick={() => document.getElementById('file-input').click()}
          >
            <div className="flex flex-col items-center text-center">
              <Upload size={28} className="text-slate-300 mb-2" />
              <p className="text-sm font-semibold text-slate-600">Arraste PDFs aqui</p>
              <p className="text-xs text-slate-400 mt-0.5">ou clique para selecionar</p>
            </div>
            <input id="file-input" type="file" multiple accept=".pdf" className="hidden"
                   onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files)])} />
          </div>

          {/* Lista de arquivos */}
          {files.length > 0 && (
            <div className="card divide-y divide-border overflow-hidden">
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 px-4 py-2.5">
                  <FileText size={14} className="text-brand-500 flex-shrink-0" />
                  <span className="text-xs text-slate-700 truncate flex-1">{f.name}</span>
                  <button onClick={() => removeFile(i)} className="text-slate-300 hover:text-red-400 transition-colors">
                    <X size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}

          <button
            className="btn-primary w-full py-2.5"
            onClick={handleUpload}
            disabled={!files.length || !clienteId || phase === 'processing' || phase === 'uploading'}
          >
            {phase === 'uploading' ? (
              <><Loader2 size={15} className="animate-spin" /> Enviando...</>
            ) : 'Iniciar Auditoria'}
          </button>
        </div>

        {/* Painel direito: status */}
        <div className="lg:col-span-3">
          <div className="card h-full min-h-64 flex flex-col">

            {phase === 'idle' && (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-8">
                <div className="w-12 h-12 rounded-full bg-subtle flex items-center justify-center mb-3">
                  <FileText size={20} className="text-slate-300" />
                </div>
                <p className="text-sm font-semibold text-slate-400">Aguardando envio</p>
                <p className="text-xs text-slate-300 mt-1">Selecione um cliente e os arquivos PDF para começar.</p>
              </div>
            )}

            {(phase === 'uploading' || phase === 'processing') && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <Loader2 size={36} className="text-brand-600 animate-spin mb-4" />
                <p className="text-sm font-semibold text-slate-700">
                  {phase === 'uploading' ? 'Enviando arquivos...' : 'Processando auditoria'}
                </p>
                <p className="text-xs text-slate-400 mt-1 capitalize">{progress.label}</p>

                {phase === 'processing' && (
                  <div className="w-full max-w-xs mt-6">
                    <div className="flex justify-between text-xs text-slate-400 mb-1">
                      <span>Progresso</span>
                      <span>{progress.pct}%</span>
                    </div>
                    <div className="w-full bg-subtle rounded-full h-1.5 overflow-hidden">
                      <div
                        className="h-full bg-brand-600 rounded-full transition-all duration-500"
                        style={{ width: `${progress.pct}%` }}
                      />
                    </div>
                  </div>
                )}
              </div>
            )}

            {phase === 'completed' && (
              <div className="flex-1 flex flex-col p-6">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-9 h-9 rounded-full bg-emerald-50 flex items-center justify-center flex-shrink-0">
                    <CheckCircle size={18} className="text-emerald-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-slate-800">Auditoria concluída</p>
                    <p className="text-xs text-slate-400">Laudo disponível para download.</p>
                  </div>
                </div>

                {progress.resultado && (
                  <div className="flex-1 bg-subtle rounded-lg border border-border p-4 mb-4 overflow-y-auto">
                    <p className="text-xs text-slate-600 leading-relaxed whitespace-pre-wrap">{progress.resultado}</p>
                  </div>
                )}

                <div className="flex gap-2">
                  <a
                    href={`${api.defaults.baseURL}/auditoria/download/${taskId}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="btn-primary flex-1 text-center"
                  >
                    <Download size={15} /> Baixar Laudo PDF
                  </a>
                  <button className="btn-secondary" onClick={reset}>Nova auditoria</button>
                </div>
              </div>
            )}

            {phase === 'error' && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <div className="w-10 h-10 rounded-full bg-red-50 flex items-center justify-center mb-3">
                  <AlertTriangle size={18} className="text-red-500" />
                </div>
                <p className="text-sm font-semibold text-red-600 mb-1">Erro na auditoria</p>
                <p className="text-xs text-slate-400 max-w-xs">{apiError}</p>
                <button className="btn-secondary mt-4" onClick={reset}>Tentar novamente</button>
              </div>
            )}

            {phase === 'timeout' && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
                <div className="w-10 h-10 rounded-full bg-amber-50 flex items-center justify-center mb-3">
                  <Clock size={18} className="text-amber-500" />
                </div>
                <p className="text-sm font-semibold text-amber-600 mb-1">Tempo limite excedido</p>
                <p className="text-xs text-slate-400 max-w-xs">O processo pode ainda estar rodando no servidor.</p>
                <button className="btn-secondary mt-4" onClick={reset}>Nova auditoria</button>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
