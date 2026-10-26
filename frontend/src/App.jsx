import { useState } from 'react'
import './App.css'
import { api, setToken } from './api.js'
import RegisterDesk from './pages/RegisterDesk.jsx'
import DoctorStation from './pages/DoctorStation.jsx'
import CashierDesk from './pages/CashierDesk.jsx'
import PharmacyDesk from './pages/PharmacyDesk.jsx'
import DataImport from './pages/DataImport.jsx'
import AuditLogs from './pages/AuditLogs.jsx'

const TABS = [
  { key: 'register', label: '挂号台', roles: ['registrar'] },
  { key: 'doctor', label: '医生站', roles: ['doctor'] },
  { key: 'cashier', label: '收费处', roles: ['cashier'] },
  { key: 'pharmacy', label: '药房', roles: ['pharmacist'] },
  { key: 'import', label: '数据导入', roles: ['registrar', 'pharmacist'] },
  { key: 'audit', label: '审计日志', roles: ['admin'] },
]

function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setError('')
    setLoading(true)
    try {
      const res = await api.login({ username, password })
      setToken(res.access_token)
      onLogin(res.user)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>门诊 HIS MVP</h1>
      </header>
      <main className="content">
        <div className="card login-card">
          <h2>登录</h2>
          <div className="field-row">
            <label>用户名</label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="如 registrar"
              autoFocus
            />
          </div>
          <div className="field-row">
            <label>密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && submit()}
            />
          </div>
          <div className="actions">
            <button type="button" onClick={submit} disabled={loading}>
              {loading ? '登录中…' : '登录'}
            </button>
          </div>
          {error && <div className="msg error">{error}</div>}
          <div className="hint">
            演示账号：registrar/Reg@12345 · doctor/Doc@12345 · cashier/Cash@12345 ·
            pharmacist/Pharm@12345
          </div>
        </div>
      </main>
    </div>
  )
}

function App() {
  const [user, setUser] = useState(null)
  const [tab, setTab] = useState('register')

  if (!user) {
    return <Login onLogin={(u) => { setUser(u); setTab('register') }} />
  }

  const visibleTabs = TABS.filter(
    (t) => user.role_code === 'admin' || t.roles.includes(user.role_code),
  )

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  return (
    <div className="app">
      <header className="topbar">
        <h1>门诊 HIS MVP</h1>
        <nav className="tabs">
          {visibleTabs.map((t) => (
            <button
              key={t.key}
              type="button"
              className={tab === t.key ? 'tab active' : 'tab'}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="user-box">
          <span className="user-name">
            {user.real_name}（{user.role_name}）
          </span>
          <button type="button" className="logout" onClick={logout}>
            退出
          </button>
        </div>
      </header>
      <main className="content">
        {tab === 'register' && <RegisterDesk />}
        {tab === 'doctor' && <DoctorStation />}
        {tab === 'cashier' && <CashierDesk />}
        {tab === 'pharmacy' && <PharmacyDesk />}
        {tab === 'import' && <DataImport />}
        {tab === 'audit' && <AuditLogs />}
      </main>
    </div>
  )
}

export default App
