import { useEffect, useState } from 'react'
import { api } from '../api.js'

function RegisterDesk() {
  const [schedules, setSchedules] = useState([])
  const [scheduleId, setScheduleId] = useState('')
  const [patientId, setPatientId] = useState('1')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    try {
      setSchedules(await api.schedules())
    } catch (e) {
      setError(`加载号源失败：${e.message}`)
    }
  }

  useEffect(() => {
    let cancelled = false
    api
      .schedules()
      .then((data) => {
        if (!cancelled) setSchedules(data)
      })
      .catch((e) => {
        if (!cancelled) setError(`加载号源失败：${e.message}`)
      })
    return () => {
      cancelled = true
    }
  }, [])

  const submit = async () => {
    setError('')
    setResult(null)
    if (!scheduleId) {
      setError('请先选择一个号源')
      return
    }
    setLoading(true)
    try {
      const res = await api.register({
        patient_id: Number(patientId),
        schedule_id: Number(scheduleId),
      })
      setResult(res)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      load()
    }
  }

  return (
    <div className="card">
      <h2>挂号台 · 选号源挂号</h2>
      <div className="field-row">
        <label>患者ID</label>
        <input value={patientId} onChange={(e) => setPatientId(e.target.value)} />
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th></th>
            <th>日期</th>
            <th>时段</th>
            <th>号别</th>
            <th>科室</th>
            <th>医生</th>
            <th>挂号费</th>
            <th>余号</th>
          </tr>
        </thead>
        <tbody>
          {schedules.map((s) => (
            <tr
              key={s.schedule_id}
              className={scheduleId === String(s.schedule_id) ? 'selected' : ''}
              onClick={() => setScheduleId(String(s.schedule_id))}
            >
              <td>
                <input
                  type="radio"
                  name="schedule"
                  checked={scheduleId === String(s.schedule_id)}
                  onChange={() => setScheduleId(String(s.schedule_id))}
                />
              </td>
              <td>{s.work_date}</td>
              <td>{s.time_slot}</td>
              <td>{s.reg_level}</td>
              <td>{s.dept_name}</td>
              <td>
                {s.doctor_name}（{s.doctor_title}）
              </td>
              <td>{(s.fee_cents / 100).toFixed(2)} 元</td>
              <td>{s.remaining_count}</td>
            </tr>
          ))}
          {schedules.length === 0 && (
            <tr>
              <td colSpan="8" className="empty">
                暂无可挂号源，请先运行 seed_test_data.py
              </td>
            </tr>
          )}
        </tbody>
      </table>
      <div className="actions">
        <button type="button" onClick={submit} disabled={loading}>
          {loading ? '挂号中…' : '挂号'}
        </button>
      </div>
      {error && <div className="msg error">{error}</div>}
      {result && (
        <div className="msg ok">
          挂号成功：单号 {result.reg_no}，排队号 {result.queue_no}，费用{' '}
          {(result.fee_cents / 100).toFixed(2)} 元
        </div>
      )}
    </div>
  )
}

export default RegisterDesk
