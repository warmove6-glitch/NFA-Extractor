import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8001',
  timeout: 120000, // 2 min — AI calls (Claude streaming) can take 30–60s
});

// Injeta JWT em todas as requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('orgatec_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Redireciona para login se o token expirar
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('orgatec_token');
      localStorage.removeItem('orgatec_user');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;
