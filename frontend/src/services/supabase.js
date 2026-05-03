import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

/**
 * Login com email/senha via Supabase Auth.
 * Após autenticar, troca o token Supabase pelo token ORGATEC via /auth/supabase.
 */
export async function loginComSupabase(email, password) {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password })
  if (error) throw new Error(error.message)

  const supabaseToken = data.session.access_token
  const resp = await fetch(`${import.meta.env.VITE_API_URL}/auth/supabase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token: supabaseToken }),
  })
  if (!resp.ok) throw new Error('Falha ao trocar token Supabase → ORGATEC')
  return resp.json()
}

/**
 * Login com OAuth (Google, GitHub).
 * Redireciona para o provedor; ao voltar, chama trocarTokenSupabase().
 */
export async function loginComOAuth(provider = 'google') {
  const { error } = await supabase.auth.signInWithOAuth({
    provider,
    options: { redirectTo: `${window.location.origin}/auth/callback` },
  })
  if (error) throw new Error(error.message)
}

/**
 * Chama /auth/supabase com a sessão ativa após redirect OAuth.
 * Use no componente /auth/callback.
 */
export async function trocarTokenSupabase() {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session) throw new Error('Nenhuma sessão Supabase ativa')

  const resp = await fetch(`${import.meta.env.VITE_API_URL}/auth/supabase`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ access_token: session.access_token }),
  })
  if (!resp.ok) throw new Error('Falha ao trocar token')
  return resp.json()
}

export async function logout() {
  await supabase.auth.signOut()
  localStorage.removeItem('orgatec_token')
}
