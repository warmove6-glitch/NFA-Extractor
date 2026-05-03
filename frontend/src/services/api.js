import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://127.0.0.1:8081',
  timeout: 120_000,
});

// Injeta JWT em todas as requisições
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('orgatec_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Retry com exponential backoff para erros 5xx e de rede
api.interceptors.response.use(
  res => res,
  async err => {
    const config = err.config;
    if (!config) return Promise.reject(err);

    const status = err.response?.status;
    const isNetwork = !err.response;
    const shouldRetry = isNetwork || (status >= 500 && status !== 501);

    config._retryCount = config._retryCount ?? 0;

    if (shouldRetry && config._retryCount < 2) {
      config._retryCount += 1;
      const delay = Math.min(1000 * 2 ** config._retryCount, 8000);
      await new Promise(r => setTimeout(r, delay));
      return api(config);
    }

    if (status === 401) {
      localStorage.removeItem('orgatec_token');
      localStorage.removeItem('orgatec_user');
      window.location.href = '/login';
    }

    return Promise.reject(err);
  }
);

export default api;
