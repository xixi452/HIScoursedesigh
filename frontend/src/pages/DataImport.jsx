import { useRef, useState } from 'react'
import { api } from '../api.js'

const TEMPLATE = `name,gender,birth_date,id_card,phone
张三,男,1990-03-15,330106199003151234,13812345678
李四,女,1985-11-02,330106198511021234,13900001111
错误示例,未知,1990-13-99,12345,138
重复示例,男,1990-03-15,330106199003151234,13812345678`

function DataImport() {
  const fileRef = useRef(null)
  const [csvText, setCsvText] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setError('')
    setResult(null)
    const file = fileRef.current?.files?.[0]
    if (!file && !csvText.trim()) {
      setError('请选择 CSV 文件，或在下方粘贴 CSV 内容')
      return
    }
    setLoading(true)
    try {
      const form = new FormData()
      if (file) {
        form.append('file', file)
      } else {
        form.append('csv_text', csvText)
      }
      setResult(await api.importPatients(form))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const fillSample = () => {
    setCsvText(TEMPLATE)
  }

  return (
    <div className="card">
      <h2>患者数据 CSV 批量导入</h2>
      <p className="hint">
        表头：<code>name,gender,birth_date,id_card,phone</code>（gender 为
        男/女/未知；phone 可选）。身份证号服务端自动脱敏入库，错误行不影响合法行。
      </p>

      <div className="field-row">
        <label>选择 CSV 文件</label>
        <input type="file" accept=".csv,text/csv" ref={fileRef} />
      </div>

      <div className="field-row">
        <label>或粘贴 CSV 内容</label>
        <textarea
          rows="6"
          value={csvText}
          onChange={(e) => setCsvText(e.target.value)}
          placeholder="name,gender,birth_date,id_card,phone\n张三,男,1990-03-15,330106199003151234,13812345678"
        />
      </div>

      <div className="actions">
        <button type="button" onClick={submit} disabled={loading}>
          {loading ? '导入中…' : '开始导入'}
        </button>
        <button type="button" className="ghost" onClick={fillSample}>
          填充示例数据
        </button>
      </div>

      {error && <div className="msg error">{error}</div>}

      {result && (
        <div className="import-result">
          <div className="import-summary">
            <span>共 {result.total_rows} 行</span>
            <span className="ok-text">成功 {result.success}</span>
            <span className="err-text">失败 {result.failed}</span>
          </div>

          {result.created_patients.length > 0 && (
            <table className="data-table small">
              <thead>
                <tr>
                  <th>行号</th>
                  <th>患者编号</th>
                  <th>姓名</th>
                  <th>身份证（脱敏）</th>
                </tr>
              </thead>
              <tbody>
                {result.created_patients.map((p) => (
                  <tr key={p.patient_no}>
                    <td>{p.row}</td>
                    <td>{p.patient_no}</td>
                    <td>{p.name}</td>
                    <td>{p.id_card_masked}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {result.errors.length > 0 && (
            <table className="data-table small">
              <thead>
                <tr>
                  <th>行号</th>
                  <th>姓名</th>
                  <th>失败原因</th>
                </tr>
              </thead>
              <tbody>
                {result.errors.map((e, i) => (
                  <tr key={i}>
                    <td>{e.row}</td>
                    <td>{e.name}</td>
                    <td>{e.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

export default DataImport
