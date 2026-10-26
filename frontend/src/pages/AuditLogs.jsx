import { useEffect, useState } from 'react'
import { api } from '../api.js'

function AuditLogs() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await api.auditLogs({ page: 1, page_size: 50 })
      setLogs(res.items || [])
      setTotal(res.total || 0)
    } catch (e) {
      setError(`加载审计日志失败：${e.message}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="card">
      <h2>操作审计日志</h2>
      <p className="hint">
        由审计中间件自动记录所有写操作（挂号/收费/发药/开方/导入/分诊）。共 {total} 条。
      </p>
      <div className="actions">
        <button type="button" onClick={load} disabled={loading}>
          {loading ? '加载中…' : '刷新'}
        </button>
      </div>
      {error && <div className="msg error">{error}</div>}
      <table className="data-table small">
        <thead>
          <tr>
            <th>ID</th>
            <th>操作人</th>
            <th>动作</th>
            <th>实体</th>
            <th>实体ID</th>
            <th>详情</th>
            <th>IP</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((l) => (
            <tr key={l.log_id}>
              <td>{l.log_id}</td>
              <td>{l.user_id ?? '-'}</td>
              <td>{l.action}</td>
              <td>{l.entity ?? '-'}</td>
              <td>{l.entity_id ?? '-'}</td>
              <td className="detail-cell">{l.detail ?? '-'}</td>
              <td>{l.ip ?? '-'}</td>
              <td>{l.created_at}</td>
            </tr>
          ))}
          {logs.length === 0 && (
            <tr>
              <td colSpan="8" className="empty">
                暂无审计记录，请先执行挂号/收费等操作
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export default AuditLogs
