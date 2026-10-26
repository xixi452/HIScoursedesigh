import { useEffect, useState } from 'react'
import { api } from '../api.js'

function DoctorStation() {
  const [patients, setPatients] = useState([])
  const [drugs, setDrugs] = useState([])
  const [loadError, setLoadError] = useState('')
  const [success, setSuccess] = useState(null)
  const [error, setError] = useState('')

  // 当前正在编辑的处方：记录被编辑患者的 reg_id（null 表示没打开任何编辑区）
  const [editingRegId, setEditingRegId] = useState(null)
  const [diagnosis, setDiagnosis] = useState('')
  const [items, setItems] = useState([])
  const [submitting, setSubmitting] = useState(false)

  const load = async () => {
    try {
      const [p, d] = await Promise.all([
        api.waitingPatients(),
        api.drugs(),
      ])
      setPatients(p)
      setDrugs(d)
    } catch (e) {
      setLoadError(`加载失败：${e.message}`)
    }
  }

  useEffect(() => {
    let cancelled = false
    Promise.all([api.waitingPatients(), api.drugs()])
      .then(([p, d]) => {
        if (cancelled) return
        setPatients(p)
        setDrugs(d)
      })
      .catch((e) => {
        if (!cancelled) setLoadError(`加载失败：${e.message}`)
      })
    return () => {
      cancelled = true
    }
  }, [])

  // 打开某位患者的处方编辑区，重置表单
  const openEditor = (regId) => {
    setEditingRegId(regId)
    setDiagnosis('')
    setItems([])
    setSuccess(null)
    setError('')
  }

  const closeEditor = () => {
    setEditingRegId(null)
    setDiagnosis('')
    setItems([])
    setError('')
  }

  const addItem = () => {
    if (drugs.length === 0) return
    setItems((prev) => [
      ...prev,
      { drug_id: drugs[0].drug_id, quantity: 1 },
    ])
  }

  const updateItem = (idx, patch) => {
    setItems((prev) =>
      prev.map((it, i) => (i === idx ? { ...it, ...patch } : it)),
    )
  }

  const removeItem = (idx) => {
    setItems((prev) => prev.filter((_, i) => i !== idx))
  }

  const submit = async () => {
    setError('')
    setSuccess(null)
    if (!diagnosis.trim()) {
      setError('请填写诊断')
      return
    }
    if (items.length === 0) {
      setError('请至少添加一条处方明细')
      return
    }
    // 硬规则2【金额】：请求体只发药品与数量，绝不允许携带任何金额字段。
    // 金额一律由后端按药品档案单价计算后，在响应体里返回再展示。
    const payload = {
      reg_id: editingRegId,
      diagnosis: diagnosis.trim(),
      items: items.map((it) => ({
        drug_id: Number(it.drug_id),
        quantity: Number(it.quantity),
      })),
    }
    setSubmitting(true)
    try {
      const res = await api.createPrescription(payload)
      setSuccess(res)
    } catch (e) {
      // 硬规则3【库存】：400 时后端会给出中文 detail，原样展示，不吞掉。
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  // 参考展示用：根据 drug_id 找出档案单价（仅展示，不参与请求体）
  const priceOf = (drugId) => {
    const d = drugs.find((x) => x.drug_id === Number(drugId))
    return d ? d.price_cents : 0
  }

  return (
    <div className="card">
      <h2>医生站 · 待就诊患者</h2>
      <table className="data-table">
        <thead>
          <tr>
            <th>排队号</th>
            <th>患者</th>
            <th>科室</th>
            <th>医生</th>
            <th>挂号时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {patients.map((p) => (
            <tr key={p.reg_id}>
              <td>{p.queue_no}</td>
              <td>{p.patient_name}</td>
              <td>{p.dept_name}</td>
              <td>{p.doctor_name}</td>
              <td>{p.reg_time}</td>
              <td>
                <button
                  type="button"
                  onClick={() =>
                    editingRegId === p.reg_id
                      ? closeEditor()
                      : openEditor(p.reg_id)
                  }
                >
                  {editingRegId === p.reg_id ? '收起' : '开处方'}
                </button>
              </td>
            </tr>
          ))}
          {patients.length === 0 && (
            <tr>
              <td colSpan="6" className="empty">
                暂无候诊患者，请先到挂号台挂号
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="actions">
        <button type="button" onClick={load}>
          刷新
        </button>
      </div>

      {loadError && <div className="msg error">{loadError}</div>}

      {/* 处方编辑区（受控 state，无弹窗库） */}
      {editingRegId !== null && (
        <div className="card">
          <h3>开具处方（挂号号 {editingRegId}）</h3>
          <div className="field-row">
            <label>诊断</label>
            <input
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              placeholder="必填，如 上呼吸道感染"
            />
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>药品</th>
                <th>数量</th>
                <th>参考单价</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((it, idx) => (
                <tr key={idx}>
                  <td>
                    <select
                      value={it.drug_id}
                      onChange={(e) =>
                        updateItem(idx, { drug_id: Number(e.target.value) })
                      }
                    >
                      {drugs.map((d) => (
                        <option key={d.drug_id} value={d.drug_id}>
                          {d.generic_name}（{d.spec}）·
                          {(d.price_cents / 100).toFixed(2)} 元
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="number"
                      min="1"
                      value={it.quantity}
                      onChange={(e) =>
                        updateItem(idx, { quantity: e.target.value })
                      }
                      style={{ width: '80px' }}
                    />
                  </td>
                  <td>
                    {/* 参考单价仅展示，不进入请求体 */}
                    {(priceOf(it.drug_id) / 100).toFixed(2)} 元
                  </td>
                  <td>
                    <button type="button" onClick={() => removeItem(idx)}>
                      删除
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan="4" className="empty">
                    暂未添加明细
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="actions">
            <button type="button" onClick={addItem}>
              + 添加明细
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={submitting}
            >
              {submitting ? '开处方中…' : '提交处方'}
            </button>
            <button type="button" onClick={closeEditor}>
              取消
            </button>
          </div>

          {/* 硬规则2：提交失败的 e.message（后端中文 detail）原样渲染，不吞掉 */}
          {error && <div className="msg error">{error}</div>}

          {/* 提交成功后展示后端返回的金额（后端按药品档案单价计算） */}
          {success && (
            <div className="msg ok">
              处方开具成功，处方号 {success.prescription_no}（
              {success.status}）
              <table className="data-table">
                <thead>
                  <tr>
                    <th>药品</th>
                    <th>规格</th>
                    <th>单位</th>
                    <th>数量</th>
                    <th>单价</th>
                    <th>小计</th>
                  </tr>
                </thead>
                <tbody>
                  {success.items.map((it) => (
                    <tr key={it.item_id}>
                      <td>{it.generic_name}</td>
                      <td>{it.spec}</td>
                      <td>{it.unit}</td>
                      <td>{it.quantity}</td>
                      <td>{(it.unit_price_cents / 100).toFixed(2)} 元</td>
                      <td>{(it.amount_cents / 100).toFixed(2)} 元</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              合计：{(success.total_amount_cents / 100).toFixed(2)} 元
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default DoctorStation
