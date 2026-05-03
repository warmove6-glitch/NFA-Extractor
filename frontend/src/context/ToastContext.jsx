import React, { createContext, useContext, useState, useCallback } from 'react';
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react';

const ToastContext = createContext(null);

let _id = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const push = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++_id;
    setToasts(t => [...t, { id, message, type }]);
    if (duration > 0) setTimeout(() => remove(id), duration);
  }, []);

  const remove = useCallback((id) => {
    setToasts(t => t.filter(x => x.id !== id));
  }, []);

  const toast = {
    success: (msg, d) => push(msg, 'success', d),
    error:   (msg, d) => push(msg, 'error', d),
    info:    (msg, d) => push(msg, 'info', d),
    warning: (msg, d) => push(msg, 'warning', d),
  };

  const ICONS = {
    success: <CheckCircle2 size={16} />,
    error:   <XCircle size={16} />,
    info:    <Info size={16} />,
    warning: <AlertTriangle size={16} />,
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="toast-container">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.type}`}>
            {ICONS[t.type]}
            <span className="flex-1">{t.message}</span>
            <button onClick={() => remove(t.id)}
              className="ml-2 opacity-60 hover:opacity-100 transition-opacity shrink-0 cursor-pointer">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export const useToast = () => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast deve ser usado dentro de ToastProvider');
  return ctx;
};
