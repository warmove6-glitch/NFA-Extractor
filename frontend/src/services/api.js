import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8081',
  timeout: 120000, // 2 min — AI calls (Claude streaming) can take 30–60s
});

// Injeta JWT em todas as requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('orgatec_token');
  if (token) config.headers.Authorization = `Beare