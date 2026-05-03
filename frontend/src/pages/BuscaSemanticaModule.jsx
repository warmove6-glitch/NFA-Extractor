import React, { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Search, Sparkles, FileText, AlertCircle,
  Loader2, ChevronRight, X, Info,
} from 'lucide-react';
import api from '../services/api';

// Sugestões de exemplo para guiar o usuário
const SUGESTOES = [
  'venda de soja com irregularidade de ICMS',
  'nota de gado bovino acima de R$ 50.000',
  'insumos agrícolas com NCM divergente',
  'operações com omissão de receita no SPED',
  'NFA com CFOP incorreto para produtor rural',
];

const SIM_COLOR = (s) => {
  if (s >= 0.9) return { bg: 'rgba(16,185,129,0.12)', text: '#10b981', border: 'rgba(16,185,129,0.25)' };
  if (s >= 0.8) return { bg: 'rgba(99,102,241,0.12)', text: '#818cf8', border: 'rgba(99,102,241,0.25)' };
  return { bg: 'rgba(245,158,11,0.10)', text: '#f59e0b', border: 'rgba(245,158,11,0.25)' };
};

export default function BuscaSemanticaModule() {
  const [query,      setQuery]      = useState('');
  const [resultado,  setResultado]  = useState(null);
  const [loading,    setLoading]    = useState(false);
  const [erro,       setErro]       = useState('');
  const inputRef = useRef(null);

  const buscar = async (q = query) => {
    const texto = q.trim();
    if (!texto || texto.length < 3) return;
    setLoading(true); setErro(''); setResultado(null);
    try {
      const { data } = await api.get('/notas/buscar-similar', {
        params: { q: texto, limite: 8, threshold: 0.68 },
      });
      setResultado(data);
    } catch (err) {
      const msg = err.response?.data?.detail || 'Erro ao realizar busca semântica.';
      setErro(msg);
    } finally {
      setLoading(false);
    }
  };

  const usarSugestao = (s) => {
    setQuery(s);
    buscar(s);
    inputRef.current?.blur();
  };

  return (
    <div className="max-w-4xl space-y-6">

      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: '#f1f5f9', letterSpacing: '-0.025em' }}>
            Busca Semântica
          </h1>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold"
            style={{ background: 'rgba(99,102,241,0.15)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.3)' }}>
            pgvector
          </span>
        </div>
        <p className="text-sm" style={{ color: '#64748b' }}>
          Encontre notas fiscais por significado — sem precisar de palavras exatas.
        </p>
      </div>

      {/* Campo de busca */}
      <div className="relative">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none"
              style={{ color: '#475569' }} />
            <input
              ref={inputRef}
              type="text"
              className="input"
              style={{ paddingLeft: '40px', paddingRight: query ? '36px' : '12px', fontSize: '14px' }}
              placeholder="Ex: notas de soja com irregularidade tributária no Paraná..."
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && buscar()}
            />
            {query && (
              <button onClick={() => { setQuery(''); setResultado(null); setErro(''); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 transition-colors cursor-pointer"
                style={{ color: '#475569' }}>
                <X size={14} />
              </button>
            )}
          </div>
          <button
            onClick={() => buscar()}
            disabled={loading || query.trim().length < 3}
            className="btn-primary px-5"
            style={{ opacity: query.trim().length < 3 ? 0.5 : 1 }}>
            {loading
              ? <Loader2 size={14} className="animate-spin" />
              : <><Sparkles size={14} /> Buscar</>}
          </button>
        </div>

        {/* Info pgvector */}
        <div className="flex items-start gap-1.5 mt-2">
          <Info size={11} style={{ color: '#334155', marginTop: 2, flexShrink: 0 }} />
          <p className="text-[11px]" style={{ color: '#334155' }}>
            Busca semântica via pgvector + Voyage AI <span style={{color:'#475569'}}>voyage-finance-2</span> (treinado para documentos fiscais). Requer <span style={{color:'#475569'}}>VOYAGE_API_KEY</span> no .env.
          </p>
        </div>
      </div>

      {/* Sugestões */}
      <AnimatePresence>
        {!resultado && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-2">
            <p className="text-xs font-semibold uppercase tracking-widest" style={{ color: '#334155' }}>
              Exemplos de busca
            </p>
            <div className="flex flex-wrap gap-2">
              {SUGESTOES.map((s, i) => (
                <button key={i} onClick={() => usarSugestao(s)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs transition-all cursor-pointer"
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    color: '#64748b',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'rgba(99,102,241,0.1)';
                    e.currentTarget.style.borderColor = 'rgba(99,102,241,0.3)';
                    e.currentTarget.style.color = '#a5b4fc';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
                    e.currentTarget.style.color = '#64748b';
                  }}>
                  <ChevronRight size={11} />
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Erro */}
      <AnimatePresence>
        {erro && (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-3 p-4 rounded-xl"
            style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <AlertCircle size={16} style={{ color: '#ef4444', flexShrink: 0, marginTop: 1 }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: '#f87171' }}>Erro na busca</p>
              <p className="text-xs mt-0.5" style={{ color: '#64748b' }}>{erro}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Loading */}
      {loading && (
        <div className="flex items-center gap-3 py-8 justify-center">
          <Loader2 size={18} className="animate-spin" style={{ color: '#6366f1' }} />
          <span className="text-sm" style={{ color: '#64748b' }}>Gerando embedding e buscando similares...</span>
        </div>
      )}

      {/* Resultados */}
      <AnimatePresence>
        {resultado && !loading && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-3">

            {/* Cabeçalho resultado */}
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold" style={{ color: '#94a3b8' }}>
                {resultado.total > 0
                  ? <>{resultado.total} nota{resultado.total > 1 ? 's' : ''} similar{resultado.total > 1 ? 'es' : ''} encontrada{resultado.total > 1 ? 's' : ''}</>
                  : 'Nenhuma nota similar encontrada'}
              </p>
              <span className="text-xs px-2 py-0.5 rounded font-mono"
                style={{ background: 'rgba(255,255,255,0.04)', color: '#334155' }}>
                "{resultado.query}"
              </span>
            </div>

            {/* Lista vazia */}
            {resultado.total === 0 && (
              <div className="text-center py-12 rounded-xl"
                style={{ background: 'rgba(20,20,33,0.7)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <FileText size={28} style={{ color: '#1e293b', margin: '0 auto 12px' }} />
                <p className="text-sm" style={{ color: '#334155' }}>
                  Nenhuma nota indexada ainda, ou threshold muito alto.
                </p>
                <p className="text-xs mt-1" style={{ color: '#1e293b' }}>
                  As notas são indexadas automaticamente após a auditoria.
                </p>
              </div>
            )}

            {/* Cards de resultado */}
            {resultado.resultados.map((nota, i) => {
              const sim = Math.round((nota.similarity || 0) * 100);
              const sc = SIM_COLOR(nota.similarity || 0);
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="p-4 rounded-xl"
                  style={{ background: 'rgba(20,20,33,0.85)', border: '1px solid rgba(255,255,255,0.07)' }}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                        style={{ background: 'rgba(99,102,241,0.1)' }}>
                        <FileText size={14} style={{ color: '#6366f1' }} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {nota.numero && (
                            <span className="text-xs font-mono font-semibold" style={{ color: '#e2e8f0' }}>
                              NF nº {nota.numero}
                            </span>
                          )}
                          {nota.emissao && (
                            <span className="text-xs" style={{ color: '#475569' }}>
                              {nota.emissao}
                            </span>
                          )}
                          {nota.cliente_nome && (
                            <span className="text-xs px-1.5 py-0.5 rounded"
                              style={{ background: 'rgba(255,255,255,0.05)', color: '#64748b' }}>
                              {nota.cliente_nome}
                            </span>
                          )}
                        </div>
                        {nota.natureza && (
                          <p className="text-xs mt-1 truncate" style={{ color: '#94a3b8' }}>
                            {nota.natureza}
                          </p>
                        )}
                        {nota.descricao && (
                          <p className="text-[11px] mt-1 line-clamp-2" style={{ color: '#334155' }}>
                            {nota.descricao}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Badge de similaridade */}
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className="text-xs font-bold px-2 py-0.5 rounded-full"
                        style={{ background: sc.bg, color: sc.text, border: `1px solid ${sc.border}` }}>
                        {sim}% similar
                      </span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
