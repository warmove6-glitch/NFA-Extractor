import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload, FileText, CheckCircle, AlertTriangle,
  Loader2, Clock, X, Download, FileSearch, Shield,
  FileCode, ChevronRight, Sparkles, Zap,
} from 'lucide-react';
import api from '../services/api';

const ACCEPT_TYPES = '.pdf,.xml';
const MIME_PDF     = 'application/pdf';
const MIME_XML_1   = 'text/xml';
const MIME_XML_2   = 'application/xml';

const isXML    = f => f.name?.toLowerCase().endsWith('.xml') || f.type === MIME_XML_1 || f.type === MIME_XML_2;
const isPDF    = f => f.name?.toLowerCase().endsWith('.pdf') || f.type === MIME_PDF;
const isAceito = f => isPDF(f) || isXML(f);

// Backoff dinâmico: escalona conforme número de ciclos já executados
const getBackoffMs = (cycles) => {
  if (cycles < 10) return 2000;
  if (cycles < 20) return 4000;
  if (cycles < 35) return 8000;
  return 16000;
};

const SS_TASK  = 'aud_task_id';
const SS_PHASE = 'aud_phase';

function ssGet(key, fallback) {
  try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function ssSet(key, val) {
  try { val == null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, val); } catch {}
}

const PHASE_LABEL = {
  idle: 'Aguardando',
  uploading: 'Enviando',
  processing: 'Processando',
  completed: 'Concluído',
  error: 'Erro',
  timeout: 'Timeout',
};

const STEP_STYLES = {
  done:    { bg: 'rgba(99,102,241,0.15)', border: 'rgba(99,102,241,0.4)', color: '#818cf8' },
  active:  { bg: 'rgba(99,102,241,0.08)', border: 'rgba(99,102,241,0.25)', color: '#6366f1' },
  pending: { bg: 'transparent', border: 'rgba(255,255,255,0.1)', color: '#475569' },
};

export default function AuditoriaModule() {
  const [clientes,   setClientes]   = useState([]);
  const [clienteId,  setClienteId]  = useState('');
  const [files,      setFiles]      = useState([]);
  const [taskId,     setTaskId]     = useState(() => ssGet(SS_TASK, null));
  const [phase,      setPhase]      = useState(() => {
    const p = ssGet(SS_PHASE, 'idle');
    return p === 'processing' ? 'processing' : 'idle';
  });
  const [progress,   setProgress]   = useState({ pct: 0, label: '', resultado: '' });
  const [apiError,   setApiError]   = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const dropRef    = useRef(null);
  const cyclesRef  = useRef(0);
  const timerRef   = useRef(null);

  const setTaskIdSS = (id) => { setTaskId(id); ssSet(SS_TASK, id); };
  const setPhaseSS  = (p)  => { setPhase(p);   ssSet(SS_PHASE, p); };

  useEffect(() => {
    api.get('/clientes/').then(r => setClientes(r.data)).catch(() => {});
  }, []);

  // Drag & drop com feedback visual
  useEffect(() => {
    const zone = dropRef.current;
    if (!zone) return;
    const prevent = e => e.preventDefault();
    const onDragOver = e => { e.preventDefault(); setIsDragging(true); };
    const onDragLeave = () => setIsDragging(false);
    const onDrop = e => {
      e.preventDefault();
      setIsDragging(false);
      const dropped = Array.from(e.dataTransfer.files).filter(isAceito);
      setFiles(prev => [...prev, ...dropped]);
    };
    zone.addEventListener('dragover', onDragOver);
    zone.addEventListener('dragleave', onDragLeave);
    zone.addEventListener('drop', onDrop);
    zone.addEventListener('dragenter', prevent);
    return () => {
      zone.removeEventListener('dragover', onDragOver);
      zone.removeEventListener('dragleave', onDragLeave);
      zone.removeEventListener('drop', onDrop);
      zone.removeEventListener('dragenter', prevent);
    };
  }, []);

  // Polling com backoff dinâmico (setTimeout recursivo em vez de setInterval)
  const startPolling = useCallback((id) => {
    cyclesRef.current = 0;

    const poll = async () => {
      const cycle = ++cyclesRef.current;
      if (cycle > 450) { setPhaseSS('timeout'); return; }

      try {
        const { data } = await api.get(`/auditoria/status/${id}`);
        setProgress({
          pct: data.progress ?? 0,
          label: (data.status ?? '').replace(/_/g, ' '),
          resultado: data.resultado ?? '',
        });
        if (data.status === 'concluido') { setPhaseSS('completed'); return; }
        if (data.status === 'erro')      { setPhaseSS('error'); setApiError(data.erro ?? 'Erro desconhecido.'); return; }
      } catch (err) {
        if (err.response?.status === 404) {
          setPhaseSS('error');
          setApiError('Tarefa não encontrada — o servidor pode ter sido reiniciado. Inicie uma nova auditoria.');
          return;
        }
      }

      timerRef.current = setTimeout(poll, getBackoffMs(cycle));
    };

    timerRef.current = setTimeout(poll, getBackoffMs(0));
  }, []);

  useEffect(() => {
    if (taskId && phase === 'processing') startPolling(taskId);
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, [taskId, phase, startPolling]);

  const handleDownload = async () => {
    if (!taskId) return;
    try {
      const res = await api.get(`/auditoria/download/${taskId}`, { responseType: 'blob' });
      const url  = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Laudo_${taskId.slice(0, 8)}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setApiError('Erro ao baixar relatório: ' + (err.response?.data?.detail || err.message));
    }
  };

  const handleUpload = async () => {
    if (!files.length || !clienteId) return;
    setPhaseSS('uploading'); setApiError('');
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));
    try {
      const res = await api.post(`/auditoria/upload/${clienteId}`, formData);
      setTaskIdSS(res.data.task_id);
      setPhaseSS('processing');
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Erro ao iniciar auditoria.');
      setPhaseSS('error');
    }
  };

  const reset = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    setFiles([]); setTaskIdSS(null); setPhaseSS('idle');
    setProgress({ pct: 0, label: '', resultado: '' }); setApiError('');
  };

  // Steps derivados do estado
  const steps = [
    { n: 1, label: 'Cliente',    done: !!clienteId,        active: !clienteId },
    { n: 2, label: 'Arquivos',   done: files.length > 0,   active: !!clienteId && !files.length },
    { n: 3, label: 'Processar',  done: phase === 'completed', active: files.length > 0 && phase === 'idle' },
  ];

  const phaseColor = {
    completed: '#10b981',
    error:     '#ef4444',
    timeout:   '#f59e0b',
    processing:'#6366f1',
    uploading: '#6366f1',
    idle:      '#475569',
  }[phase] ?? '#475569';

  return (
    <div className="max-w-5xl space-y-6">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.025em' }}>
          Auditoria NFA
        </h1>
        <p className="text-sm mt-1" style={{ color: '#64748b' }}>
          Envie Notas Fiscais Agropecuárias em PDF ou XML para análise multiagente automatizada.
        </p>
      </div>

      {/* Steps */}
      <div className="flex items-center gap-2">
        {steps.map((s, i) => {
          const style = s.done ? STEP_STYLES.done : s.active ? STEP_STYLES.active : STEP_STYLES.pending;
          return (
            <React.Fragment key={i}>
              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all"
                style={{ background: style.bg, border: `1px solid ${style.border}`, color: style.color }}>
                {s.done
                  ? <CheckCircle size={11} />
                  : <span className="w-3.5 h-3.5 rounded-full border border-current flex items-center justify-center text-[9px] font-bold">{s.n}</span>}
                {s.label}
              </div>
              {i < 2 && <ChevronRight size={12} style={{ color: '#1e293b' }} />}
            </React.Fragment>
          );
        })}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

        {/* ── Painel Esquerdo ── */}
        <div className="lg:col-span-2 space-y-4">

          {/* Seleção de cliente */}
          <div className="rounded-xl p-4 space-y-3"
            style={{ background: 'rgba(20,20,33,0.7)', border: '1px solid rgba(255,255,255,0.08)' }}>
            <label className="block text-[11px] font-semibold uppercase tracking-widest" style={{ color: '#475569' }}>
              Cliente / Contribuinte
            </label>
            <select className="input" value={clienteId} onChange={e => setClienteId(e.target.value)}>
              <option value="">Selecione...</option>
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
            {clientes.length === 0 && (
              <p className="text-xs" style={{ color: '#475569' }}>
                Nenhum cliente cadastrado.{' '}
                <a href="/dashboard/clientes" style={{ color: '#6366f1' }} className="hover:underline">
                  Cadastrar →
                </a>
              </p>
            )}
          </div>

          {/* Drop zone */}
          <div ref={dropRef}
            onClick={() => document.getElementById('file-input-aud').click()}
            className="rounded-xl p-6 cursor-pointer transition-all duration-200"
            style={{
              background: isDragging ? 'rgba(99,102,241,0.12)' : 'rgba(20,20,33,0.7)',
              border: `2px dashed ${isDragging ? 'rgba(99,102,241,0.6)' : 'rgba(255,255,255,0.1)'}`,
              boxShadow: isDragging ? '0 0 24px rgba(99,102,241,0.15)' : 'none',
            }}>
            <div className="flex flex-col items-center text-center gap-3">
              <motion.div
                animate={{ scale: isDragging ? 1.1 : 1 }}
                transition={{ duration: 0.2 }}
                className="w-12 h-12 rounded-xl flex items-center justify-center"
                style={{ background: isDragging ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.05)' }}>
                <Upload size={20} style={{ color: isDragging ? '#818cf8' : '#475569' }} />
              </motion.div>
              <div>
                <p className="text-sm font-semibold" style={{ color: isDragging ? '#c7d2fe' : '#94a3b8' }}>
                  {isDragging ? 'Solte os arquivos aqui' : 'Arraste ou clique para enviar'}
                </p>
                <p className="text-xs mt-0.5" style={{ color: '#334155' }}>NFSe · NF-e · NFA Agropecuária</p>
              </div>
              <div className="flex gap-1.5">
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold"
                  style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.25)' }}>
                  PDF
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-semibold"
                  style={{ background: 'rgba(16,185,129,0.12)', color: '#34d399', border: '1px solid rgba(16,185,129,0.25)' }}>
                  XML
                </span>
              </div>
            </div>
            <input id="file-input-aud" type="file" multiple accept={ACCEPT_TYPES} className="hidden"
              onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files).filter(isAceito)])} />
          </div>

          {/* Lista de arquivos */}
          <AnimatePresence>
            {files.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: -8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                className="rounded-xl overflow-hidden"
                style={{ border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="flex items-center justify-between px-4 py-2.5"
                  style={{ background: 'rgba(255,255,255,0.03)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
                  <span className="text-xs font-semibold" style={{ color: '#64748b' }}>
                    {files.length} arquivo(s) ·{' '}
                    <span style={{ color: '#818cf8' }}>{files.filter(isPDF).length} PDF</span>{' '}·{' '}
                    <span style={{ color: '#34d399' }}>{files.filter(isXML).length} XML</span>
                  </span>
                  <button onClick={() => setFiles([])}
                    className="text-xs transition-colors cursor-pointer"
                    style={{ color: '#ef4444' }}>
                    Limpar
                  </button>
                </div>
                <div className="divide-y max-h-44 overflow-y-auto"
                  style={{ background: 'rgba(20,20,33,0.85)', borderColor: 'rgba(255,255,255,0.05)' }}>
                  {files.map((f, i) => (
                    <div key={i} className="flex items-center gap-2.5 px-4 py-2">
                      {isXML(f)
                        ? <FileCode size={13} style={{ color: '#34d399', flexShrink: 0 }} />
                        : <FileText size={13} style={{ color: '#818cf8', flexShrink: 0 }} />}
                      <span className="text-xs truncate flex-1" style={{ color: '#94a3b8' }}>{f.name}</span>
                      <span className="text-[10px] font-medium shrink-0"
                        style={{ color: isXML(f) ? '#34d399' : '#6366f1' }}>
                        {isXML(f) ? 'XML' : 'PDF'}
                      </span>
                      <span className="text-[10px] shrink-0" style={{ color: '#334155' }}>
                        {(f.size / 1024).toFixed(0)} KB
                      </span>
                      <button onClick={() => setFiles(fs => fs.filter((_, j) => j !== i))}
                        className="transition-colors cursor-pointer shrink-0"
                        style={{ color: '#334155' }}
                        onMouseEnter={e => e.currentTarget.style.color = '#ef4444'}
                        onMouseLeave={e => e.currentTarget.style.color = '#334155'}>
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Botão iniciar */}
          <button className="btn-primary w-full py-3" onClick={handleUpload}
            disabled={!files.length || !clienteId || phase === 'processing' || phase === 'uploading'}
            style={{ opacity: (!files.length || !clienteId) ? 0.5 : 1 }}>
            {phase === 'uploading'
              ? <><Loader2 size={14} className="animate-spin" /> Enviando...</>
              : <><Zap size={14} /> Iniciar Auditoria</>}
          </button>
        </div>

        {/* ── Painel Direito — Status ── */}
        <div className="lg:col-span-3">
          <div className="rounded-xl overflow-hidden h-full min-h-72 flex flex-col"
            style={{ background: 'rgba(20,20,33,0.85)', border: '1px solid rgba(255,255,255,0.08)' }}>

            {/* Header do painel */}
            <div className="flex items-center gap-2.5 px-5 py-3.5"
              style={{ borderBottom: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.02)' }}>
              <Shield size={14} style={{ color: '#6366f1' }} />
              <span className="text-sm font-semibold" style={{ color: '#94a3b8' }}>Painel de Processamento</span>
              <AnimatePresence mode="wait">
                {phase !== 'idle' && (
                  <motion.span
                    key={phase}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    className="ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full"
                    style={{
                      background: `${phaseColor}18`,
                      border: `1px solid ${phaseColor}40`,
                      color: phaseColor,
                    }}>
                    {PHASE_LABEL[phase]}
                  </motion.span>
                )}
              </AnimatePresence>
            </div>

            {/* Conteúdo animado por fase */}
            <AnimatePresence mode="wait">

              {/* Idle */}
              {phase === 'idle' && (
                <motion.div key="idle"
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
                  <div className="w-16 h-16 rounded-2xl flex items-center justify-center"
                    style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)' }}>
                    <FileSearch size={26} style={{ color: '#334155' }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: '#475569' }}>Aguardando envio</p>
                    <p className="text-xs mt-1 max-w-xs" style={{ color: '#334155' }}>
                      Selecione um cliente e os arquivos para iniciar a auditoria automatizada.
                    </p>
                  </div>
                </motion.div>
              )}

              {/* Processando / Enviando */}
              {(phase === 'uploading' || phase === 'processing') && (
                <motion.div key="processing"
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-5">
                  {/* Spinner animado */}
                  <div className="relative w-20 h-20">
                    <div className="absolute inset-0 rounded-full border-[3px]"
                      style={{ borderColor: 'rgba(99,102,241,0.15)' }} />
                    <div className="absolute inset-0 rounded-full border-[3px] border-t-indigo-500 animate-spin"
                      style={{ borderColor: 'transparent', borderTopColor: '#6366f1' }} />
                    <div className="absolute inset-3 rounded-full flex items-center justify-center"
                      style={{ background: 'rgba(99,102,241,0.08)' }}>
                      <Sparkles size={18} style={{ color: '#6366f1' }} />
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: '#e2e8f0' }}>
                      {phase === 'uploading' ? 'Enviando arquivos...' : 'Squad processando'}
                    </p>
                    <p className="text-xs mt-1 capitalize" style={{ color: '#64748b' }}>
                      {progress.label || (phase === 'uploading' ? 'Preparando upload...' : 'Aguardando início...')}
                    </p>
                  </div>
                  {phase === 'processing' && (
                    <div className="w-full max-w-xs space-y-2">
                      <div className="flex justify-between text-[10px]" style={{ color: '#475569' }}>
                        <span>Progresso</span>
                        <span className="font-bold" style={{ color: '#818cf8' }}>{progress.pct}%</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full overflow-hidden"
                        style={{ background: 'rgba(255,255,255,0.06)' }}>
                        <motion.div className="h-full rounded-full"
                          style={{ background: 'linear-gradient(90deg, #6366f1, #8b5cf6)' }}
                          animate={{ width: `${progress.pct}%` }}
                          transition={{ duration: 0.6, ease: 'easeOut' }} />
                      </div>
                    </div>
                  )}
                </motion.div>
              )}

              {/* Concluído */}
              {phase === 'completed' && (
                <motion.div key="completed"
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col p-5 gap-4">
                  <div className="flex items-center gap-3 p-4 rounded-xl"
                    style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)' }}>
                    <div className="w-9 h-9 rounded-full flex items-center justify-center shrink-0"
                      style={{ background: 'rgba(16,185,129,0.15)' }}>
                      <CheckCircle size={17} style={{ color: '#10b981' }} />
                    </div>
                    <div>
                      <p className="text-sm font-semibold" style={{ color: '#34d399' }}>Auditoria concluída</p>
                      <p className="text-xs" style={{ color: '#065f46' }}>Laudo disponível para download.</p>
                    </div>
                  </div>
                  {progress.resultado && (
                    <div className="flex-1 rounded-xl p-4 overflow-y-auto min-h-24 font-mono"
                      style={{
                        background: 'rgba(0,0,0,0.3)',
                        border: '1px solid rgba(255,255,255,0.06)',
                        color: '#64748b',
                        fontSize: '11px',
                        lineHeight: '1.6',
                        whiteSpace: 'pre-wrap',
                      }}>
                      {progress.resultado}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button onClick={handleDownload} className="btn-primary flex-1 justify-center">
                      <Download size={13} /> Baixar Laudo
                    </button>
                    <button onClick={reset} className="btn-secondary">Nova auditoria</button>
                  </div>
                </motion.div>
              )}

              {/* Erro */}
              {phase === 'error' && (
                <motion.div key="error"
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
                  <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                    style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.2)' }}>
                    <AlertTriangle size={22} style={{ color: '#ef4444' }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: '#f87171' }}>Erro na auditoria</p>
                    <p className="text-xs mt-1 max-w-xs" style={{ color: '#64748b' }}>{apiError}</p>
                  </div>
                  <button onClick={reset} className="btn-secondary">Tentar novamente</button>
                </motion.div>
              )}

              {/* Timeout */}
              {phase === 'timeout' && (
                <motion.div key="timeout"
                  initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
                  <div className="w-14 h-14 rounded-2xl flex items-center justify-center"
                    style={{ background: 'rgba(245,158,11,0.1)', border: '1px solid rgba(245,158,11,0.2)' }}>
                    <Clock size={22} style={{ color: '#f59e0b' }} />
                  </div>
                  <div>
                    <p className="text-sm font-semibold" style={{ color: '#fbbf24' }}>Tempo limite excedido</p>
                    <p className="text-xs mt-1 max-w-xs" style={{ color: '#64748b' }}>
                      O processo pode ainda estar em execução no servidor. Verifique o histórico de laudos.
                    </p>
                  </div>
                  <button onClick={reset} className="btn-secondary">Nova auditoria</button>
                </motion.div>
              )}

            </AnimatePresence>
          </div>
        </div>
      </div>
    </div>
  );
}
