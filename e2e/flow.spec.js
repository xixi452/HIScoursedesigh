// @ts-check
// E2E 主流程测试（Playwright request 驱动真实运行中的后端）：
// 登录 → 挂号 → 开方 → 收费 → 发药，覆盖四种角色与鉴权/越权。
const { test, expect } = require('@playwright/test')

async function login(request, username, password) {
  const r = await request.post('/api/login', {
    data: { username, password },
  })
  expect(r.status()).toBe(200)
  return (await r.json()).access_token
}

const auth = (token) => ({ Authorization: `Bearer ${token}` })

test.describe('E2E 主流程（登录→挂号→开方→收费→发药）', () => {
  test('四角色全链路走通', async ({ request }) => {
    // 1) 挂号员登录并挂号
    const registrarToken = await login(request, 'registrar', 'Reg@12345')
    let r = await request.post('/api/register', {
      headers: auth(registrarToken),
      data: { patient_id: 1, schedule_id: 1 },
    })
    expect(r.status()).toBe(201)
    const reg = await r.json()
    expect(reg.queue_no).toBe(1)
    expect(reg.status).toBe('候诊')

    // 2) 医生登录并开方（金额服务端计价：2*2000 + 1*3500 = 7500）
    const doctorToken = await login(request, 'doctor', 'Doc@12345')
    r = await request.post('/api/prescriptions', {
      headers: auth(doctorToken),
      data: {
        reg_id: reg.reg_id,
        diagnosis: '上呼吸道感染',
        items: [
          { drug_id: 1, quantity: 2 },
          { drug_id: 2, quantity: 1 },
        ],
      },
    })
    expect(r.status()).toBe(201)
    const rx = await r.json()
    expect(rx.total_amount_cents).toBe(7500)
    expect(rx.status).toBe('待收费')

    // 3) 收费员登录并收费
    const cashierToken = await login(request, 'cashier', 'Cash@12345')
    r = await request.post('/api/pay', {
      headers: auth(cashierToken),
      data: { prescription_id: rx.prescription_id, request_id: 'e2e-req-1' },
    })
    expect(r.status()).toBe(200)
    const bill = await r.json()
    expect(bill.total_amount_cents).toBe(7500)

    // 4) 药师登录并发药（FEFO 近效期优先）
    const pharmacistToken = await login(request, 'pharmacist', 'Pharm@12345')
    r = await request.post('/api/dispense', {
      headers: auth(pharmacistToken),
      data: { prescription_id: rx.prescription_id },
    })
    expect(r.status()).toBe(200)
    const disp = await r.json()
    expect(disp.status).toBe('已发药')
    expect(disp.records.length).toBeGreaterThan(0)
  })

  test('越权拦截：收费员调开方接口返回 403', async ({ request }) => {
    const cashierToken = await login(request, 'cashier', 'Cash@12345')
    const r = await request.post('/api/prescriptions', {
      headers: auth(cashierToken),
      data: {
        reg_id: 1,
        diagnosis: '越权测试',
        items: [{ drug_id: 1, quantity: 1 }],
      },
    })
    expect(r.status()).toBe(403)
  })

  test('号源不足：余量为 0 的号源挂号返回 409', async ({ request }) => {
    const registrarToken = await login(request, 'registrar', 'Reg@12345')
    const r = await request.post('/api/register', {
      headers: auth(registrarToken),
      data: { patient_id: 1, schedule_id: 3 },
    })
    expect(r.status()).toBe(409)
  })

  test('未登录访问受保护接口返回 401', async ({ request }) => {
    const r = await request.get('/api/schedules')
    expect(r.status()).toBe(401)
  })
})
