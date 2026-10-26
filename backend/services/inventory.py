"""FEFO（先到期先出）批次分配（纯函数）。

入参 batches 已按效期升序排好（调用方负责排序），每个元素为字典：
    {"stock_id": int, "batch_no": str, "quantity": int}
返回分配方案：list[{"stock_id", "batch_no", "take"}]，take 之和恰好等于 needed。
任一批次不足时整体失败（抛 ValueError），不产生部分扣减。
"""


def allocate_fefo(batches, needed: int):
    """按 FEFO 顺序分配 needed 个单位的库存。

    规则：
    - needed 必须 > 0，否则抛 ValueError；
    - 可用总量不足时抛 ValueError（整单失败，不允许部分分配）；
    - 依次从最早批次取，取完一个批次再取下一个。
    """
    if needed <= 0:
        raise ValueError("扣减数量必须大于 0")

    available = sum(b["quantity"] for b in batches)
    if available < needed:
        raise ValueError(f"库存不足：需要 {needed}，可用 {available}")

    plan = []
    remaining = needed
    for b in batches:
        if remaining <= 0:
            break
        take = min(remaining, b["quantity"])
        plan.append({"stock_id": b["stock_id"], "batch_no": b["batch_no"], "take": take})
        remaining -= take

    if remaining > 0:  # 理论上不会发生，防御性兜底
        raise ValueError("库存不足：分配失败")
    return plan
