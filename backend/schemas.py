"""Pydantic 请求/响应模型集中定义（门诊 HIS MVP —— 处方相关）。

说明：现有路由（registration / payment / dispense）中的 RegisterRequest /
PayRequest / DispenseRequest 仍保留在各自文件里，本模块仅新增处方相关的
Schema，避免改动既有文件、避免破坏现有接口。

三条硬规则落实位置（针对处方金额——【金额】是 Schema 层的第一道防线）：
- 【金额】：PrescriptionItemIn 只允许 drug_id:int>0 与 quantity:int>0，
  绝对不含 unit_price_cents / amount_cents / total_amount_cents 等任何金额字段
  （见下方 PrescriptionItemIn 定义，约第 23~27 行）。金额一律由后端在事务内
  从 drugs.price_cents 现算（见 routers/prescription.py）。
- 【事务】/【库存】由 routers/prescription.py、routers/payment.py 落实，
  本文件只负责定义数据结构，不涉及数据库操作。
"""

from typing import List

from pydantic import BaseModel, Field


class PrescriptionItemIn(BaseModel):
    """处方明细输入：前端只传药品与数量，绝不允许任何金额字段。"""

    drug_id: int = Field(..., gt=0, description="药品ID（必须存在于 drugs 且 status='启用'）")
    quantity: int = Field(..., gt=0, description="药品数量（按最小包装单位）")


class PrescriptionCreateIn(BaseModel):
    """开处方请求体：只含挂号单、诊断与明细，不含任何金额字段。"""

    reg_id: int = Field(..., gt=0, description="挂号单ID（reg_orders.status 必须为'候诊'）")
    diagnosis: str = Field(..., min_length=1, max_length=200, description="诊断")
    items: List[PrescriptionItemIn] = Field(
        ..., min_length=1, description="处方明细（至少一条）"
    )


class PrescriptionItemOut(BaseModel):
    """处方明细响应：含后端现算出的单价与小计。"""

    item_id: int
    drug_id: int
    drug_code: str
    generic_name: str
    spec: str
    unit: str
    quantity: int
    unit_price_cents: int
    amount_cents: int


class PrescriptionOut(BaseModel):
    """开处方响应。"""

    prescription_id: int
    prescription_no: str
    reg_id: int
    total_amount_cents: int
    status: str
    items: List[PrescriptionItemOut]
