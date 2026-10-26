const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

const TOKEN_KEY = 'his_token'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token)
  } else {
    localStorage.removeItem(TOKEN_KEY)
  }
}

async function request(path, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const data = await res.json()
      if (Array.isArray(data.detail)) {
        detail = data.detail.map((d) => d.msg).join('; ')
      } else {
        detail = data.detail || JSON.stringify(data)
      }
    } catch {
      /* keep statusText */
    }
    if (res.status === 401) setToken(null)
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return res.json()
}

export const api = {
  login: (payload) =>
    request('/api/login', { method: 'POST', body: JSON.stringify(payload) }),
  me: () => request('/api/me'),
  schedules: () => request('/api/schedules'),
  waitingPatients: () => request('/api/reg-orders/waiting'),
  register: (payload) =>
    request('/api/register', { method: 'POST', body: JSON.stringify(payload) }),
  pay: (payload) =>
    request('/api/pay', { method: 'POST', body: JSON.stringify(payload) }),
  dispense: (payload) =>
    request('/api/dispense', { method: 'POST', body: JSON.stringify(payload) }),
  drugs: () => request('/api/drugs'),
  createPrescription: (payload) =>
    request('/api/prescriptions', { method: 'POST', body: JSON.stringify(payload) }),
  // ---- 第 10/11 课：数据集成与 AI 增强 ----
  triage: (payload) =>
    request('/api/triage', { method: 'POST', body: JSON.stringify(payload) }),
  importPatients: async (formData) => {
    const headers = {}
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(`${API_BASE}/api/import/patients`, {
      method: 'POST',
      headers,
      body: formData, // FormData 由浏览器自动设置 multipart boundary
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || res.statusText)
    }
    return res.json()
  },
  importDrugs: async (formData) => {
    const headers = {}
    const token = getToken()
    if (token) headers.Authorization = `Bearer ${token}`
    const res = await fetch(`${API_BASE}/api/drugs/import`, {
      method: 'POST',
      headers,
      body: formData,
    })
    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || res.statusText)
    }
    return res.json()
  },
  auditLogs: (params = {}) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/api/audit-logs${qs ? `?${qs}` : ''}`)
  },
  dailyReport: () => request('/api/report/daily'),
}
