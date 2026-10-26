"""划价计算（纯函数）。

金额一律用"分"存整数；单价取药品目录快照，明细金额 = 数量 × 单价。
禁止信任前端传入的总金额或单价。
"""


def compute_line_amount(quantity: int, unit_price_cents: int) -> int:
    """计算单条明细金额（分）。边界：数量为 0/负数、单价为负都要拒绝。"""
    if quantity <= 0:
        raise ValueError("数量必须大于 0")
    if unit_price_cents < 0:
        raise ValueError("单价不能为负")
    return quantity * unit_price_cents


def compute_total(lines) -> int:
    """计算处方总额。lines 为 (quantity, unit_price_cents) 的序列。"""
    return sum(compute_line_amount(q, p) for q, p in lines)
