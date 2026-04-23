import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Upload, FileText, Activity, CheckCircle, AlertTriangle, Loader2 } from 'lucide-react';
import api from '../services/api';

const AuditoriaModule = () => {
  const [files, setFiles] = useState([]);
  const [taskId, setTaskId] = useState(null);
  const [status, setStatus] = useState(null); // idle, processing, completed, error
  const [progressData, setProgressData] = useState({ progress: 0, status_text: '' });

  // Polling para o status da auditoria
  useEffect(() => {
    let interval;
    if (taskId && status === 'processing') {
      interval = setInterval(async () => {
        try {
          const res = await api.get(`/auditoria/status/${taskId}`);
          const data = res.data;
          
          setProgressData({ 
            progress: data.progress, 
            status_text: data.status.replace('_', ' ').toUpperCase() 
          });

          if (data.status === 'concluido') {
            setStatus('completed');
            clearInterval(interval);
          } else if (data.status === 'erro') {
            setStatus('error');
            clearInterval(interval);
          }
        } catch (err) {
          console.error("Erro ao consultar status:", err);
        }
      }, 2000);
    }
    return () => clearInterval(interval);
  }, [taskId, status]);

  const handleUpload = async () => {
    if (files.length === 0) return;
    
    setStatus('processing');
    const formData = new FormData();
    files.forEach(f => formData.append('files', f));

    try {
      const res = await api.post('/auditoria/upload/1', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setTaskId(res.data.task_id);
    } catch (err) {
      console.error(err);
      setStatus('error');
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <h1 className="text-4xl font-extrabold mb-2">Célula de Auditoria Forense</h1>
      <p className="text-sovereign-400 mb-8">Processamento assíncrono de lotes de NFAs via Motor ORGATEC.</p>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Upload Card */}
        <div className="lg:col-span-1 space-y-6">
          <div className="sovereign-card p-6 border-dashed border-2 border-sovereign-700 hover:border-sovereign-cyan transition-all group">
            <label className="cursor-pointer flex flex-col items-center justify-center py-10">
              <Upload className="text-sovereign-500 group-hover:text-sovereign-cyan transition-colors mb-4" size={48} />
              <span className="text-sm font-bold text-sovereign-400">Arraste ou Selecione NFAs</span>
              <input 
                type="file" 
                multiple 
                className="hidden" 
                onChange={(e) => setFiles(Array.from(e.target.files))}
              />
            </label>
          </div>
          
          {files.length > 0 && (
            <div className="sovereign-card p-4 space-y-2">
              <p className="text-xs font-bold text-sovereign-600 uppercase">Lote Selecionado</p>
              {files.map((f, i) => (
                <div key={i} className="flex items-center gap-2 text-sm text-sovereign-300">
                  <FileText size={16} className="text-sovereign-cyan" />
                  {f.name}
                </div>
              ))}
              <button 
                onClick={handleUpload}
                disabled={status === 'processing'}
                className="w-full mt-4 bg-sovereign-cyan hover:bg-sovereign-neon py-3 rounded-xl font-bold transition-all disabled:opacity-50"
              >
                DISPARAR AUDITORIA
              </button>
            </div>
          )}
        </div>

        {/* Status/Monitor Card */}
        <div className="lg:col-span-2">
          <AnimatePresence mode="wait">
            {status === 'processing' ? (
              <motion.div 
                key="processing"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0 }}
                className="sovereign-card p-8 h-full flex flex-col items-center justify-center text-center"
              >
                <Loader2 size={64} className="text-sovereign-cyan animate-spin mb-6" />
                <h2 className="text-2xl font-bold mb-2">Protocolo em Execução</h2>
                <p className="text-sovereign-400 mb-8">{progressData.status_text}</p>
                
                <div className="w-full max-w-md bg-sovereign-950 rounded-full h-4 mb-4 overflow-hidden border border-sovereign-800">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${progressData.progress}%` }}
                    className="h-full bg-sovereign-cyan shadow-[0_0_15px_#0ea5e9]"
                  />
                </div>
                <span className="text-sovereign-cyan font-black">{progressData.progress}%</span>
              </motion.div>
            ) : status === 'completed' ? (
              <motion.div 
                key="completed"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="sovereign-card p-8 h-full"
              >
                <div className="flex items-center gap-4 mb-6">
                  <CheckCircle size={48} className="text-green-400" />
                  <div>
                    <h2 className="text-2xl font-bold">Veredito Concluído</h2>
                    <p className="text-sovereign-400">Análise bio-contábil finalizada com sucesso.</p>
                  </div>
                </div>
                
                <div className="bg-sovereign-950 p-6 rounded-2xl border border-sovereign-800 mb-6">
                  <p className="text-slate-200 leading-relaxed italic">
                    "O cruzamento de dados revelou um excedente patrimonial não lastreado. Hipótese técnica: Hub de lavagem detectado..."
                  </p>
                </div>
                
                <button className="bg-white text-sovereign-950 font-black px-8 py-3 rounded-xl hover:bg-slate-200 transition-all">
                  BAIXAR LAUDO FORENSE PDF
                </button>
              </motion.div>
            ) : (
              <div className="sovereign-card p-8 h-full flex flex-col items-center justify-center text-center text-sovereign-600 border-dashed">
                <Activity size={64} className="mb-4 opacity-20" />
                <p>Aguardando submissão de lote para iniciar protocolos de investigação.</p>
              </div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

export default AuditoriaModule;
