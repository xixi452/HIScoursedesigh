"""挂号事务的纯逻辑部分（纯函数）。"""


def can_register(remaining_count: int, status: str) -> bool:
    """号源是否可再挂一个：状态正常且余量 > 0。"""
    return status == "正常" and remaining_count > 0


def next_queue_no(existing_count: int) -> int:
    """排队号 = 当前号源下已挂号人数 + 1。"""
    if existing_count < 0:
        raise ValueError("已挂号人数不能为负")
    return existing_count + 1
