import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8081',
  timeout: 30000,
});

/** Decodifica payload JWT sem dependência externa */
function parseJwt(token) {
  try {
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    return JSON.parse(atob(base64));
  } catch {
    return null;
  }
}

/** Verifica se o access token expira em menos de 2 minutos */
function isTokenExpiringSoon(token) {
  const payload = parseJwt(token);
  if (!payload?.exp) return true;
  return payload.exp * 1000 - Date.now() < 2 * 60 * 1000;
}

/** Controle de refresh concorrente — evita múltiplos refreshes simultâneos */
let refreshPromise = null;

async function refreshTokens() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      const refreshToken = localStorage.getItem('orgatec_refresh_token');
      if (!refreshToken) throw new Error('Sem refresh token');

      const res = await axios.post(
        `${import.meta.env.VITE_API_URL || 'http://localhost:8081'}/auth/refresh`,
        { refresh_token: refreshToken },
      );

      const { access_token, refresh_token } = res.data;
      localStorage.setItem('orgatec_token', access_token);
      localStorage.setItem('orgatec_refresh_token', refresh_token);
      return access_token;
    } catch {
      // Refresh falhou — limpar tudo e redirecionar
      localStorage.removeItem('orgatec_token');
      localStorage.removeItem('orgatec_refresh_token');
      localStorage.removeItem('orgatec_user');
      window.location.href = '/login';
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// Injeta JWT em todas as requisições + auto-refresh se expirando
api.interceptors.request.use(async (config) => {
  let token = localStorage.getItem('orgatec_token');

  if (token && isTokenExpiringSoon(token)) {
    token = await refreshTokens();
  }

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// Fallback: se receber 401, tenta refresh uma vez antes de deslogar
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config;
    if (err.response?.status === 401 && !original._retry) {
      original._retry = true;
      const newToken = await refreshTokens();
      if (newToken) {
        original.headers.Authorization = `Bearer ${newToken}`;
        return api(original);
      }
    }
    return Promise.reject(err);
  }
);

export default api;
