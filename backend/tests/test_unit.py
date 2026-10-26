"""单元测试：划价计算、FEFO 扣库存、挂号纯逻辑、密码哈希。

覆盖"正常 / 边界 / 异常"三类用例（测试清单由人工拟定，见 tests/测试清单.md）。
"""

import pytest

from security import hash_password, verify_password
from services.inventory import allocate_fefo
from services.pricing import compute_line_amount, compute_total
from services.registration import can_register, next_queue_no


# ---------------------------------------------------------------- 划价计算
class TestPricing:
    def test_normal_line_amount(self):
        assert compute_line_amount(2, 2000) == 4000
        assert compute_line_amount(1, 3500) == 3500

    def test_total(self):
        assert compute_total([(2, 2000), (1, 3500)]) == 7500

    def test_boundary_quantity_zero(self):
        with pytest.raises(ValueError):
            compute_line_amount(0, 2000)

    def test_boundary_price_zero(self):
        # 单价为 0 是合法边界（免费药品），金额应为 0
        assert compute_line_amount(3, 0) == 0

    def test_exception_negative_quantity(self):
        with pytest.raises(ValueError):
            compute_line_amount(-1, 2000)

    def test_exception_negative_price(self):
        with pytest.raises(ValueError):
            compute_line_amount(2, -100)


# ---------------------------------------------------------------- FEFO 扣库存
class TestFefoAllocation:
    def test_normal_fefo_order(self):
        batches = [
            {"stock_id": 1, "batch_no": "EARLY", "quantity": 1},
            {"stock_id": 2, "batch_no": "LATE", "quantity": 5},
        ]
        plan = allocate_fefo(batches, 2)
        # 先扣最早效期批次 1 盒，再扣下一批次 1 盒
        assert [(s["stock_id"], s["take"]) for s in plan] == [(1, 1), (2, 1)]

    def test_exact_match_single_batch(self):
        batches = [{"stock_id": 2, "batch_no": "LATE", "quantity": 5}]
        plan = allocate_fefo(batches, 5)
        assert len(plan) == 1 and plan[0]["take"] == 5

    def test_boundary_needed_zero(self):
        with pytest.raises(ValueError):
            allocate_fefo([{"stock_id": 1, "batch_no": "B", "quantity": 1}], 0)

    def test_exception_insufficient(self):
        batches = [{"stock_id": 1, "batch_no": "B", "quantity": 1}]
        with pytest.raises(ValueError):
            allocate_fefo(batches, 2)

    def test_total_equals_needed(self):
        batches = [
            {"stock_id": 1, "batch_no": "B1", "quantity": 3},
            {"stock_id": 2, "batch_no": "B2", "quantity": 3},
            {"stock_id": 3, "batch_no": "B3", "quantity": 3},
        ]
        plan = allocate_fefo(batches, 7)
        assert sum(s["take"] for s in plan) == 7


# ---------------------------------------------------------------- 挂号纯逻辑
class TestRegistration:
    def test_next_queue_no(self):
        assert next_queue_no(0) == 1
        assert next_queue_no(9) == 10

    def test_next_queue_no_negative(self):
        with pytest.raises(ValueError):
            next_queue_no(-1)

    def test_can_register_normal(self):
        assert can_register(1, "正常") is True

    def test_boundary_remaining_zero(self):
        assert can_register(0, "正常") is False

    def test_boundary_stopped(self):
        assert can_register(5, "停诊") is False


# ---------------------------------------------------------------- 密码哈希
class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("Admin@123")
        assert h != "Admin@123"
        assert h.startswith("$2")  # bcrypt 前缀

    def test_verify_correct(self):
        h = hash_password("secret-pw")
        assert verify_password("secret-pw", h) is True

    def test_verify_wrong(self):
        h = hash_password("secret-pw")
        assert verify_password("wrong", h) is False

    def test_same_password_different_salt(self):
        # 加盐：相同密码两次哈希结果不同（防彩虹表）
        assert hash_password("abc") != hash_password("abc")

    def test_verify_bad_hash_returns_false(self):
        assert verify_password("abc", "not-a-hash") is False
