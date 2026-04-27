import React, { useState, useEffect, useRef } from 'react';
import {
  Upload, FileText, CheckCircle, AlertTriangle,
  Loader2, Clock, X, Download, FileSearch, Shield, FileCode,
} from 'lucide-react';
import api from '../services/api';

// Tipos aceitos
const ACCEPT_TYPES  = '.pdf,.xml';
const MIME_PDF      = 'application/pdf';
const MIME_XML_1    = 'text/xml';
const MIME_XML_2    = 'application/xml';

const isXML = f => f.name?.toLowerCase().endsWith('.xml') || f.type === MIME_XML_1 || f.type === MIME_XML_2;
const isPDF = f => f.name?.toLowerCase().endsWith('.pdf') || f.type === MIME_PDF;
const isAceito = f => isPDF(f) || isXML(f);

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_CYCLES  = 450; // 15 min

// ── Persistência leve via sessionStorage (sobrevive a crashes do React/Translate) ──
const SS_TASK = 'aud_task_id';
const SS_PHASE = 'aud_phase';

function ssGet(key, fallback) {
  try { return sessionStorage.getItem(key) ?? fallback; } catch { return fallback; }
}
function ssSet(key, val) {
  try { val == null ? sessionStorage.removeItem(key) : sessionStorage.setItem(key, val); } catch {}
}

export default function AuditoriaModule() {
  const [clientes, setClientes]   = useState([]);
  const [clienteId, setClienteId] = useState('');
  const [files, setFiles]         = useState([]);
  const [taskId, setTaskId]       = useState(() => ssGet(SS_TASK, null));
  const [phase, setPhase]         = useState(() => {
    const p = ssGet(SS_PHASE, 'idle');
    // Só retoma se estava em processamento — outros estados requerem interação
    return (p === 'processing') ? 'processing' : 'idle';
  });
  const [progress, setProgress]   = useState({ pct: 0, label: '', resultado: '' });
  const [apiError, setApiError]   = useState('');
  const dropRef = useRef(null);

  // Wrappers que sincronizam com sessionStorage
  const setTaskIdSS = (id) => { setTaskId(id); ssSet(SS_TASK, id); };
  const setPhaseSS  = (p)  => { setPhase(p);   ssSet(SS_PHASE, p); };

  useEffect(() => {
    api.get('/clientes/').then(r => setClientes(r.data)).catch(() => {});
  }, []);

  useEffect(() => {
    const zone = dropRef.current;
    if (!zone) return;
    const prevent = e => e.preventDefault();
    const drop = e => {
      e.preventDefault();
      const dropped = Array.from(e.dataTransfer.files).filter(isAceito);
      setFiles(prev => [...prev, ...dropped]);
    };
    zone.addEventListener('dragover', prevent);
    zone.addEventListener('drop', drop);
    return () => { zone.removeEventListener('dragover', prevent); zone.removeEventListener('drop', drop); };
  }, []);

  useEffect(() => {
    if (!taskId || phase !== 'processing') return;
    let cycles = 0;
    const interval = setInterval(async () => {
      if (++cycles > POLL_MAX_CYCLES) { clearInterval(interval); setPhaseSS('timeout'); return; }
      try {
        const { data } = await api.get(`/auditoria/status/${taskId}`);
        setProgress({ pct: data.progress ?? 0, label: (data.status ?? '').replace(/_/g, ' '), resultado: data.resultado ?? '' });
        if (data.status === 'concluido') { clearInterval(interval); setPhaseSS('completed'); }
        if (data.status === 'erro')      { clearInterval(interval); setPhaseSS('error'); setApiError(data.erro ?? 'Erro desconhecido.'); }
      } catch (err) {
        // 404 = task não existe mais no backend (servidor reiniciado) → aborta
        if (err.response?.status === 404) {
          clearInterval(interval);
          setPhaseSS('error');
          setApiError('Tarefa não encontrada — o servidor pode ter sido reiniciado. Inicie uma nova auditoria.');
        }
        // Outros erros transientes: ignora e continua polling
      }
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [taskId, phase]);

  const handleDownload = async () => {
    if (!taskId) return;
    try {
      const response = await api.get(`/auditoria/download/${taskId}`, {
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
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
      setTaskIdSS(res.data.task_id); setPhaseSS('processing');
    } catch (err) {
      setApiError(err.response?.data?.detail || 'Erro ao iniciar auditoria.'); setPhaseSS('error');
    }
  };

  const reset = () => {
    setFiles([]); setTaskIdSS(null); setPhaseSS('idle');
    setProgress({ pct: 0, label: '', resultado: '' }); setApiError('');
  };

  return (
    <div className="max-w-5xl space-y-5">
      <div>
        <h1 className="text-2xl font-bold text-navy-900" style={{fontFamily:'Poppins,sans-serif'}}>Auditoria NFA</h1>
        <p className="text-navy-500 text-sm mt-0.5">Envie Notas Fiscais Agropecuárias em PDF para análise automatizada pela Squad.</p>
      </div>

      {/* Steps indicator */}
      <div className="flex items-center gap-2 text-xs font-medium">
        {[
          { n: 1, label: 'Selecionar cliente', done: !!clienteId },
          { n: 2, label: 'Enviar PDFs',        done: files.length > 0 },
          { n: 3, label: 'Processar',          done: phase === 'completed' },
        ].map((s, i) => (
          <React.Fragment key={i}>
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border ${
              s.done ? 'bg-accent-50 border-accent-200 text-accent-700' : 'border-border text-navy-400'
            }`}>
              {s.done
                ? <CheckCircle size={12} />
                : <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[10px]">{s.n}</span>}
              {s.label}
            </div>
            {i < 2 && <div className="h-px flex-1 bg-border max-w-8" />}
          </React.Fragment>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">

        {/* Painel esquerdo */}
        <div className="lg:col-span-2 space-y-4">

          {/* Cliente */}
          <div className="card p-4 space-y-2">
            <label className="block text-xs font-semibold text-navy-600 uppercase tracking-wide">
              Cliente / Contribuinte
            </label>
            <select className="input" value={clienteId} onChange={e => setClienteId(e.target.value)}>
              <option value="">Selecione...</option>
              {clientes.map(c => <option key={c.id} value={c.id}>{c.nome}</option>)}
            </select>
            {clientes.length === 0 && (
              <p className="text-xs text-navy-400">
                Nenhum cliente. <a href="/dashboard/clientes" className="text-accent-600 hover:underline">Cadastre um →</a>
              </p>
            )}
          </div>

          {/* Drop zone */}
          <div ref={dropRef}
            className="card p-6 border-2 border-dashed border-border hover:border-accent-400 hover:bg-accent-50/30 transition-all duration-200 cursor-pointer"
            onClick={() => document.getElementById('file-input').click()}>
            <div className="flex flex-col items-center text-center gap-2">
              <div className="w-12 h-12 rounded-xl bg-navy-50 flex items-center justify-center">
                <Upload size={22} className="text-navy-400" />
              </div>
              <div>
                <p className="text-sm font-semibold text-navy-700">Arraste os arquivos aqui</p>
                <p className="text-xs text-navy-400 mt-0.5">ou clique para selecionar</p>
              </div>
              <div className="flex gap-1.5">
                <span className="badge badge-blue">PDF</span>
                <span className="badge badge-green">XML</span>
              </div>
              <p className="text-[10px] text-navy-400">NFSe · NF-e · NFA Agropecuária</p>
            </div>
            <input id="file-input" type="file" multiple accept={ACCEPT_TYPES} className="hidden"
              onChange={e => setFiles(prev => [...prev, ...Array.from(e.target.files).filter(isAceito)])} />
          </div>

          {/* Lista de arquivos */}
          {files.length > 0 && (
            <div className="card overflow-hidden">
              <div className="px-4 py-2.5 border-b border-border bg-navy-50 flex items-center justify-between">
                <span className="text-xs font-semibold text-navy-600">
                  {files.length} arquivo(s)
                  {' · '}
                  <span className="text-accent-600">{files.filter(isPDF).length} PDF</span>
                  {' · '}
                  <span className="text-emerald-600">{files.filter(isXML).length} XML</span>
                </span>
                <button onClick={() => setFiles([])} className="text-xs text-red-400 hover:text-red-600 transition-colors cursor-pointer">
                  Limpar todos
                </button>
              </div>
              <div className="divide-y divide-border max-h-48 overflow-y-auto">
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-2.5 px-4 py-2.5">
                    {isXML(f)
                      ? <FileCode size={14} className="text-emerald-500 shrink-0" />
                      : <FileText size={14} className="text-accent-500 shrink-0" />}
                    <span className="text-xs text-navy-700 truncate flex-1">{f.name}</span>
                    <span className={`text-[10px] font-medium shrink-0 ${isXML(f) ? 'text-emerald-500' : 'text-navy-400'}`}>
                      {isXML(f) ? 'XML' : 'PDF'}
                    </span>
                    <span className="text-[10px] text-navy-400 shrink-0">{(f.size / 1024).toFixed(0)} KB</span>
                    <button onClick={() => setFiles(fs => fs.filter((_, j) => j !== i))}
                      className="text-navy-300 hover:text-red-400 transition-colors cursor-pointer">
                      <X size={13} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <button className="btn-primary w-full py-3" onClick={handleUpload}
            disabled={!files.length || !clienteId || phase === 'processing' || phase === 'uploading'}>
            {phase === 'uploading'
              ? <><Loader2 size={15} className="animate-spin" />Enviando...</>
              : <><FileSearch size={15} />Iniciar Auditoria</>}
          </button>
        </div>

        {/* Painel direito — status */}
        <div className="lg:col-span-3">
          <div className="card h-full min-h-72 flex flex-col overflow-hidden">

            {/* Header do painel */}
            <div className="flex items-center gap-3 px-5 py-3.5 border-b border-border bg-navy-50">
              <Shield size={15} className="text-accent-600" />
              <span className="text-sm font-semibold text-navy-700">Painel de Processamento</span>
              {phase !== 'idle' && (
                <span className={`ml-auto badge text-[10px] ${
                  phase === 'completed' ? 'badge-green' :
                  phase === 'error'     ? 'badge-red' :
                  phase === 'timeout'   ? 'badge-yellow' : 'badge-blue'
                }`}>
                  {phase === 'idle'       ? 'Aguardando' :
                   phase === 'uploading'  ? 'Enviando' :
                   phase === 'processing' ? 'Processando' :
                   phase === 'completed'  ? 'Concluído' :
                   phase === 'error'      ? 'Erro' : 'Timeout'}
                </span>
              )}
            </div>

            {/* Idle */}
            {phase === 'idle' && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-3">
                <div className="w-16 h-16 rounded-2xl bg-navy-50 flex items-center justify-center">
                  <FileSearch size={28} className="text-navy-300" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-navy-400">Aguardando envio</p>
                  <p className="text-xs text-navy-300 mt-1 max-w-xs">
                    Selecione um cliente e os arquivos PDF para iniciar a auditoria pela Squad de 9 agentes.
                  </p>
                </div>
              </div>
            )}

            {/* Processando */}
            {(phase === 'uploading' || phase === 'processing') && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-4">
                <div className="w-16 h-16 rounded-full border-4 border-accent-100 border-t-accent-600 animate-spin" />
                <div>
                  <p className="text-sm font-semibold text-navy-800">
                    {phase === 'uploading' ? 'Enviando arquivos...' : 'Squad processando'}
                  </p>
                  <p className="text-xs text-navy-400 mt-0.5 capitalize">{progress.label}</p>
                </div>
                {phase === 'processing' && (
                  <div className="w-full max-w-xs">
                    <div className="flex justify-between text-[10px] text-navy-400 mb-1.5">
                      <span>Progresso</span>
                      <span className="font-semibold">{progress.pct}%</span>
                    </div>
                    <div className="w-full bg-navy-100 rounded-full h-2 overflow-hidden">
                      <div className="h-full bg-accent-600 rounded-full transition-all duration-500 ease-out"
                        style={{ width: `${progress.pct}%` }} />
                    </div>
                    <p className="text-[10px] text-navy-400 mt-2">Agentes: @Alfa @Beta @Sigma @Gama @Contador @Fiscal @Jurídico @Delta @Omega</p>
                  </div>
                )}
              </div>
            )}

            {/* Concluído */}
            {phase === 'completed' && (
              <div className="flex-1 flex flex-col p-5 gap-4">
                <div className="flex items-center gap-3 p-4 bg-emerald-50 border border-emerald-100 rounded-xl">
                  <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center shrink-0">
                    <CheckCircle size={18} className="text-emerald-600" />
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-emerald-800">Auditoria concluída com sucesso</p>
                    <p className="text-xs text-emerald-600">Laudo consolidado disponível para download.</p>
                  </div>
                </div>
                {progress.resultado && (
                  <div className="flex-1 bg-navy-50 rounded-xl border border-border p-4 overflow-y-auto min-h-24">
                    <p className="text-xs text-navy-600 leading-relaxed whitespace-pre-wrap font-mono">{progress.resultado}</p>
                  </div>
                )}
                <div className="flex gap-2">
                  <button onClick={handleDownload}
                    className="btn-primary flex-1 justify-center">
                    <Download size={14} /> Baixar Laudo PDF
                  </button>
                  <button className="btn-secondary" onClick={reset}>Nova auditoria</button>
                </div>
              </div>
            )}

            {/* Erro */}
            {phase === 'error' && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-3">
                <div className="w-12 h-12 rounded-full bg-red-50 flex items-center justify-center">
                  <AlertTriangle size={20} className="text-red-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-red-600">Erro na auditoria</p>
                  <p className="text-xs text-navy-400 mt-1 max-w-xs">{apiError}</p>
                </div>
                <button className="btn-secondary" onClick={reset}>Tentar novamente</button>
              </div>
            )}

            {/* Timeout */}
            {phase === 'timeout' && (
              <div className="flex-1 flex flex-col items-center justify-center p-8 text-center gap-3">
                <div className="w-12 h-12 rounded-full bg-amber-50 flex items-center justify-center">
                  <Clock size={20} className="text-amber-500" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-amber-700">Tempo limite excedido</p>
                  <p className="text-xs text-navy-400 mt-1 max-w-xs">O processo pode ainda estar em execução no servidor.</p>
                </div>
                <button className="btn-secondary" onClick={reset}>Nova auditoria</button>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}
