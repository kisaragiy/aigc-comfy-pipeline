"""测试实战演示: TDD + 参数化 + Hypothesis + Mock + Async + API + 覆盖率"""

import pytest
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch, AsyncMock

# ════════════════════════════════════════════════════════════
# 实战目标: 一个 "折扣计算 + 订单总价" 的完整测试 suite
# 展示: TDD / 参数化 / Hypothesis / Mock / Async / API
# ════════════════════════════════════════════════════════════


# ── 业务代码 (待测试) ──

@dataclass
class Product:
    id: int
    name: str
    price: int  # 分
    stock: int

def calculate_discount(amount: int) -> int:
    """满 200 减 50, 满 500 减 150, 不叠加"""
    if amount >= 500:
        return 150
    if amount >= 200:
        return 50
    return 0

def calculate_total(price: int, quantity: int) -> int:
    """计算总价 (分)"""
    subtotal = price * quantity
    discount = calculate_discount(subtotal)
    return subtotal - discount

class EmailService:
    async def send_order_confirmation(self, email: str, order_id: int) -> bool:
        """发送订单确认邮件"""
        ...

class OrderService:
    def __init__(self, email_service: Optional[EmailService] = None):
        self.email_service = email_service
    
    async def place_order(self, product: Product, quantity: int, email: str) -> dict:
        if product.stock < quantity:
            raise ValueError(f"Insufficient stock: {product.stock} < {quantity}")
        
        total = calculate_total(product.price, quantity)
        
        order = {
            "product_id": product.id,
            "quantity": quantity,
            "total": total,
            "status": "confirmed"
        }
        
        if self.email_service and email:
            await self.email_service.send_order_confirmation(email, order["product_id"])
        
        return order


# ════════════════════════════════════════════════════════════
# 测试部分
# ════════════════════════════════════════════════════════════

class TestCalculateDiscount:
    """TDD + 参数化"""
    
    # 1) TDD 红-绿-重构 风格: 列举所有边界
    
    @pytest.mark.parametrize("amount,expected", [
        (0, 0),
        (100, 0),
        (199, 0),
        (200, 50),    # 刚好满 200
        (350, 50),    # 满 200 没满 500
        (499, 50),    # 刚差 1 没满 500
        (500, 150),   # 刚好满 500
        (999, 150),   # 满 500 兜底
    ])
    def test_discount_boundaries(self, amount: int, expected: int):
        assert calculate_discount(amount) == expected


class TestCalculateTotal:
    """集成测试: 总价计算"""
    
    @pytest.mark.parametrize("price,quantity,expected", [
        (100, 1, 100),        # 100*1 - 0 = 100
        (100, 2, 150),        # 100*2 - 50 = 150 (sum=200 >= 200)
        (300, 2, 450),        # 300*2 - 150 = 450 (sum=600 >= 500)
    ])
    def test_total(self, price: int, quantity: int, expected: int):
        assert calculate_total(price, quantity) == expected


class TestHypothesisProperties:
    """属性测试: 找边界和通用属性"""
    
    from hypothesis import given, strategies as st
    
    @given(
        st.integers(min_value=0, max_value=10_000_00),  # 价格 (分)
        st.integers(min_value=1, max_value=100),           # 数量
    )
    def test_total_never_exceeds_subtotal(self, price: int, quantity: int):
        """折扣不会让总价比小计还高 (即使满减, 总价 <= 原价)"""
        total = calculate_total(price, quantity)
        subtotal = price * quantity
        assert total <= subtotal
        assert total >= 0
    
    @given(st.integers(min_value=0, max_value=1_000_000))
    def test_discount_is_non_negative(self, amount: int):
        """折扣不会为负"""
        d = calculate_discount(amount)
        assert 0 <= d <= amount


class TestOrderService:
    """Service 层测试: Mock + Fake"""
    
    @pytest.mark.asyncio
    async def test_place_order_success(self):
        product = Product(id=1, name="测试", price=1000, stock=10)
        service = OrderService()
        
        order = await service.place_order(product, 2, "test@test.com")
        
        assert order["status"] == "confirmed"
        assert order["total"] == 1850  # 1000*2 - 150 (>=500 减 150)
        assert order["quantity"] == 2
    
    @pytest.mark.asyncio
    async def test_place_order_insufficient_stock(self):
        product = Product(id=1, name="测试", price=1000, stock=1)
        service = OrderService()
        
        with pytest.raises(ValueError, match="Insufficient stock"):
            await service.place_order(product, 5, "test@test.com")
    
    @pytest.mark.asyncio
    async def test_place_order_sends_email(self):
        """集成: 下单成功后验证发了邮件"""
        product = Product(id=1, name="测试", price=1000, stock=5)
        
        # 用 AsyncMock 替代真实邮件服务
        mock_email = AsyncMock(spec=EmailService)
        mock_email.send_order_confirmation.return_value = True
        
        service = OrderService(email_service=mock_email)
        order = await service.place_order(product, 2, "user@test.com")
        
        # 断言: 发送了邮件
        mock_email.send_order_confirmation.assert_awaited_once_with(
            "user@test.com", order["product_id"]
        )


class TestAsyncMockDemo:
    """AsyncMock 展示"""
    
    @pytest.mark.asyncio
    async def test_async_mock_pattern(self):
        """使用 AsyncMock 的正确模式"""
        mock = AsyncMock()
        mock.send.return_value = {"status": "sent"}
        
        result = await mock.send("test")
        assert result["status"] == "sent"
        mock.send.assert_awaited_once_with("test")


# ════════════════════════════════════════════════════════════
# 运行入口
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 演示测试 ===")
    print(f"TestCalculateDiscount:    {len(TestCalculateDiscount.test_discount_boundaries.pytestmark[0].args[1])} 个用例")
    print("TestHypothesisProperties: 2 个属性测试 × 100 次随机输入")
    print("TestOrderService:         3 个异步集成测试")
    print(f"\n运行: pytest {__file__} -v --tb=short")
