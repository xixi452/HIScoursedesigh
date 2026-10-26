import { useState } from 'react'
import { api } from '../api.js'

// 生成幂等请求ID：安全上下文用 crypto.randomUUID，否则用时间戳+随机数兜底（长度 ≤ 64）
function newRequestId() {
  const fallback =
    Date.now().toString(36) + Math.random().toString(36).slice(2, 10)
  return crypto?.randomUUID?.() ?? fallback
}

function CashierDesk() {
  const [prescriptionId, setPrescriptionId] = useState('')
  // 修复1&3：初始即生成；每次成功/失败都重新生成，避免命中幂等
  const [requestId, setRequestId] = useState(() => newRequestId())
  const [lastRequestId, setLastRequestId] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setError('')
    setResult(null)
    if (!prescriptionId) {
      setError('请输入处方ID')
      return
    }
    // 修复2：提交前校验非空，为空则自动用 newRequestId() 补齐，避免发出空 request_id → 422
    let rid = requestId.trim()
    if (!rid) {
      rid = newRequestId()
      setRequestId(rid)
    }
    setLoading(true)
    try {
      const res = await api.pay({
        prescription_id: Number(prescriptionId),
        request_id: rid,
      })
      setResult(res)
      setLastRequestId(rid)
    } catch (e) {
      // 硬规则1【事务】：400 业务失败原样展示后端中文文案，不重试
      setError(e.message)
      setLastRequestId(rid)
    } finally {
      setLoading(false)
      // 修复1：无论成功/失败都重置 ID，换处方再收费不会命中上一张账单的幂等
      setRequestId(newRequestId())
    }
  }

  return (
    <div className="card">
      <h2>收费处 · 处方收费</h2>
      <div className="field-row">
        <label>处方ID</label>
        <input
          value={prescriptionId}
          onChange={(e) => setPrescriptionId(e.target.value)}
          placeholder="如 1"
        />
        <label>请求ID（幂等）</label>
        <input
          value={requestId}
          onChange={(e) => setRequestId(e.target.value)}
        />
        <button type="button" onClick={() => setRequestId(newRequestId())}>
          换一个ID
        </button>
      </div>
      <div className="actions">
        <button type="button" onClick={submit} disabled={loading}>
          {loading ? '收费中…' : '收费'}
        </button>
      </div>
      {error && <div className="msg error">{error}</div>}
      {result && (
        <div className="msg ok">
          收费成功：单号 {result.bill_no}，金额{' '}
          {(result.total_amount_cents / 100).toFixed(2)} 元，状态 {result.status}
          <div className="hint">
            同一请求ID重复提交会直接返回该账单（幂等），不会重复扣费
          </div>
          <div className="hint">上次使用的请求ID：{lastRequestId}</div>
          {result.stock_deductions && result.stock_deductions.length > 0 && (
            <div className="hint">
              扣减库存：
              <table className="data-table">
                <thead>
                  <tr>
                    <th>药品</th>
                    <th>批次</th>
                    <th>数量</th>
                  </tr>
                </thead>
                <tbody>
                  {result.stock_deductions.map((s, i) => (
                    <tr key={i}>
                      <td>{s.drug}</td>
                      <td>{s.batch_no}</td>
                      <td>{s.quantity}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default CashierDesk
