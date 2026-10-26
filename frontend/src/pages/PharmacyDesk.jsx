import { useState } from 'react'
import { api } from '../api.js'

function PharmacyDesk() {
  const [prescriptionId, setPrescriptionId] = useState('')
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
    setLoading(true)
    try {
      const res = await api.dispense({
        prescription_id: Number(prescriptionId),
      })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h2>药房 · 处方发药</h2>
      <div className="field-row">
        <label>处方ID</label>
        <input
          value={prescriptionId}
          onChange={(e) => setPrescriptionId(e.target.value)}
          placeholder="如 1"
        />
      </div>
      <div className="actions">
        <button type="button" onClick={submit} disabled={loading}>
          {loading ? '发药中…' : '发药'}
        </button>
      </div>
      {error && <div className="msg error">{error}</div>}
      {result && (
        <div className="msg ok">
          发药成功：处方状态「{result.status}」
          <table className="data-table small">
            <thead>
              <tr>
                <th>药品</th>
                <th>批次号</th>
                <th>数量</th>
              </tr>
            </thead>
            <tbody>
              {result.records.map((r, i) => (
                <tr key={i}>
                  <td>{r.drug}</td>
                  <td>{r.batch_no}</td>
                  <td>{r.quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="hint">
            库存已在收费环节按 FEFO（效期最早优先）扣减，此处为药房确认发药并登记药师
          </div>
        </div>
      )}
    </div>
  )
}

export default PharmacyDesk
