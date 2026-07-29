#!/usr/bin/env python3
""" ============================================================
高级测试架构 — 5-8年测试工程师知识体系

内容:
  1. 测试金字塔 + 策略         (测什么, 不测什么)
  2. TDD 三循环                 (红-绿-重构, 实盘示例)
  3. Fixture 设计模式           (conftest + scope + teardown)
  4. 参数化                     (pytest.mark.parametrize 高级用法)
  5. 属性测试                   (Hypothesis 找出你没想到的边界)
  6. Mock 时机                  (什么时候 mock, 什么时候不)
  7. 异步测试                   (pytest-asyncio + 事件循环管理)
  8. 数据库测试                 (事务回滚 + Testcontainers)
  9. HTTP API 测试              (httpx AsyncClient)
  10. 覆盖率策略                (哪些要量, 哪些不要量)
  11. 突变测试                  (mutmut 检验测试质量)
  12. 性能测试                  (Locust 脚本模板)
  13. 安全测试                  (Bandit 扫描 + OWASP)
  14. CI/CD 集成                (GitHub Actions workflow)
  15. Factory Boy               (测试数据工厂)

依赖: pytest>=9, hypothesis, factory-boy, pytest-asyncio, pytest-cov, pytest-xdist

============================================================ """

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第一部分: 测试金字塔 — 测什么, 不测什么                  ║
# ╚═══════════════════════════════════════════════════════════╝

TEST_PYRAMID = """
         /\\
        /  \\           E2E (5%)     — 核心用户流程, 用 Testcontainers
       /    \\
      /──────\\         Integration (20%)  — Service + DB, 用实 Fixture
     /        \\
    /──────────\\       Unit (75%)         — 函数/方法, 快且稳定

高级工程师测试原则:
  1. 单元测试不测框架代码 (Django/FastAPI 框架本身有测试)
  2. 单元测试只测你的代码逻辑 (if/for/计算/转换)
  3. 集成测试测"你的代码 + 框架 + DB"的协作
  4. E2E 只测最重要的 3-5 条路径
  5. 80% 的时间在写简单的单元测试
  6. 20% 的时间在写关键路径的集成测试

不测什么:
  - 配置值 (除非动态)
  - getter/setter (除非有逻辑)
  - 第三方 SDK (假设它工作)
  - UI 布局 (测功能不测像素)
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第二部分: TDD 三循环 — 实战示例                           ║
# ╚═══════════════════════════════════════════════════════════╝

TDD_CYCLE = """
需求: 订单满 200 减 50, 满 500 减 150, 不叠加

=== 红: 先写测试 ===
def test_calculate_discount():
    assert calculate_discount(100) == 0      # 不满
    assert calculate_discount(200) == 50     # 满200
    assert calculate_discount(350) == 50     # 满200未满500
    assert calculate_discount(500) == 150    # 满500
    assert calculate_discount(800) == 150    # 满500上限

=== 绿: 刚刚好通过 ===
def calculate_discount(amount: int) -> int:
    if amount >= 500:
        return 150
    if amount >= 200:
        return 50
    return 0

=== 重构: 不改变行为的情况下优化 ===
# (这里一个 if 就够了, 不需要重构)
# 但如果后续加了 10 个阶梯就要考虑策略模式

高级工程师习惯:
  - 跑一遍测试确保它失败 (验证测试自己没写错)
  - 用最简代码让测试通过 (不用考虑通用性)
  - 只有所有测试通过时才重构
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第三部分: Fixture 设计模式                                ║
# ╚═══════════════════════════════════════════════════════════╝

FIXTURE_PATTERNS = '''
# conftest.py — fixture 分层设计

# ── 第一层: 裸 fixture (scope=session) ──
@pytest.fixture(scope="session")
def event_loop():
    """所有异步测试共享一个事件循环 (快)"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# ── 第二层: 基础设施 (scope=module/class) ──
@pytest.fixture(scope="module")
def db_url():
    """Testcontainers: 每个模块一个数据库实例"""
    with PostgreSQLContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url()

# ── 第三层: 服务 fixture (scope=function) ──
@pytest_asyncio.fixture
async def async_client(db_url):
    """每个测试函数一个 HTTP 客户端"""
    transport = ASGITransport(app=create_app({"database_url": db_url}))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

# ── 第四层: 数据 fixture (scope=function, 用 factory) ──
@pytest_asyncio.fixture
async def sample_product(db_session):
    """每个测试创建一个产品, 测试完后回滚"""
    product = ProductFactory.create()
    await db_session.commit()
    return product

# Fixture 最佳实践:
# 1. 不要 fixture 套 fixture 超过 3 层 (难理解)
# 2. 明确标注 scope (默认 function 最安全)
# 3. 用 yield 而非 return (支持 teardown)
# 4. 用 db_session rollback 而非每次重新建表
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第四部分: 参数化 — 用最少的代码测最多的场景              ║
# ╚═══════════════════════════════════════════════════════════╝

PARAMETRIZE_PATTERNS = '''
# ── 基础用法 ──
@pytest.mark.parametrize("input_val,expected", [
    (100, 0),
    (200, 50),
    (500, 150),
    (999, 150),
])
def test_discount(input_val, expected):
    assert calculate_discount(input_val) == expected
    # 4 个测试用例, 不是 4 个 if

# ── 多参数组合 (笛卡尔积) ──
@pytest.mark.parametrize("is_vip", [True, False])
@pytest.mark.parametrize("amount", [0, 100, 200, 500, 1000])
@pytest.mark.parametrize("coupon_code", [None, "SAVE50", "SAVE100"])
def test_checkout(amount, is_vip, coupon_code):
    """3 × 5 × 2 = 30 个测试用例"""
    ...

# ── 用 ids 让失败信息可读 ──
@pytest.mark.parametrize("amount,expected", [
    pytest.param(-1, 0, id="negative"),
    pytest.param(0, 0, id="zero"),
    pytest.param(199, 0, id="just_below_threshold"),
    pytest.param(200, 50, id="exact_threshold"),
    pytest.param(999999, 150, id="max_amount"),
])
def test_discount_edges(amount, expected):
    assert calculate_discount(max(0, amount)) == expected

# ── fixture 参数化 ──
@pytest.fixture(params=["sqlite", "postgres", "mysql"])
def database(request):
    if request.param == "sqlite":
        yield create_sqlite_db()
    elif request.param == "postgres":
        yield create_testcontainer("postgres")
    ...
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第五部分: 属性测试 (Hypothesis) — 找出你没想到的边界     ║
# ╚═══════════════════════════════════════════════════════════╝

HYPOTHESIS_PATTERNS = '''
# 普通单元测试: 你只能测你想到了的输入
# 属性测试: 让机器随机生成输入, 验证"通用属性"不被违反

from hypothesis import given, strategies as st

# ── 例1: 序列化/反序列化双向一致 ──
@given(st.text(max_size=200))
def test_json_roundtrip(original_text):
    """任何文本 → JSON → 解析 → 应该和原来一样"""
    encoded = json.dumps({"text": original_text})
    decoded = json.loads(encoded)
    assert decoded["text"] == original_text

# ── 例2: 价格计算不会溢出 ──
@given(
    st.integers(min_value=0, max_value=1_000_000_00),  # 价格 (分)
    st.integers(min_value=1, max_value=100),            # 数量
    st.floats(min_value=0, max_value=1.0),              # 折扣
)
def test_calculate_total_never_negative(price, quantity, discount):
    """总数不会为负 (违反直觉的边界)"""
    total = calculate_total(price, quantity, discount)
    assert total >= 0

# ── 例3: 列表排序的通用属性 ──
@given(st.lists(st.integers()))
def test_sort_properties(items):
    sorted_items = sorted(items)
    
    # 属性 1: 长度不变
    assert len(sorted_items) == len(items)
    
    # 属性 2: 每个元素都在原列表中
    for item in sorted_items:
        assert item in items
    
    # 属性 3: 升序排列
    for i in range(len(sorted_items) - 1):
        assert sorted_items[i] <= sorted_items[i + 1]
    
    # 属性 4: 幂等性 (再排一次不变)
    assert sorted(sorted_items) == sorted_items

# 什么时候用 Hypothesis?
# - 有明确的"数学属性"可验证 (双向转换/无副作用/幂等性)
# - 输入空间很大, 手动覆盖不完
# - 解析器/序列化器/数据转换函数

# 什么时候不用?
# - 业务逻辑需要特定值 (建议用 parametrize)
# - 测试时间不能太长
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第六部分: Mock 时机 — 资深工程师的判断标准               ║
# ╚═══════════════════════════════════════════════════════════╝

MOCK_PATTERNS = '''
# Mock 规则 (来自 5 年+实战总结):
#   
#   Mock 外部: 网络/文件系统/随机数/时间
#   不 Mock 内部: 你自己写的函数/类
#   
#   换句话说:
#   - HTTP 请求 → mock (慢 + 不稳定)
#   - 数据库查询 → 不 mock (用 test DB)
#   - 你自己的业务函数 → 不 mock (否则测的是 mock 本身)
#   - 时间/随机数 → mock (让测试可重复)

# ── 正确的 mock 位置 ──
# 坏: mock 第三方库
@patch("requests.get")
def test_fetch_user(mock_get):
    mock_get.return_value.json.return_value = {"id": 1}
    # 这测的是 mock 工作, 不是你的代码

# 好: mock 你的封装层
@patch("app.services.user_service.requests.get")
def test_fetch_user(mock_get):
    mock_get.return_value.json.return_value = {"id": 1}
    result = user_service.get_user(1)
    assert result.id == 1
    # 你 mock 的是你自己的边界, 不是第三方直接

# ── 永远不要 mock ──
# 1. 标准库的基础类型 (str/int/list/dict)
# 2. 简单的数据类 (@dataclass)
# 3. ORM Model 对象 (用 Factory)

# ── 用 Fake 而不是 Mock ──
# Mock: 断言"调用了哪些方法"
# Fake: 用轻量实现替换重量级依赖
class FakeEmailSender:
    """不真的发邮件, 但记录发了什么"""
    def __init__(self):
        self.sent = []
    
    def send(self, to: str, subject: str, body: str):
        self.sent.append({"to": to, "subject": subject})

def test_order_notification():
    sender = FakeEmailSender()
    service = OrderService(email_sender=sender)
    service.place_order(user_id=1, product_id=2)
    assert len(sender.sent) == 1
    assert "下单成功" in sender.sent[0]["subject"]

# Fake 比 Mock 好在哪里?
# - 不用写复杂的 assert_called_with
# - 代码更可读
# - 重构时不需要改测试 (接口不变就行)
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第七部分: 异步测试                                        ║
# ╚═══════════════════════════════════════════════════════════╝

ASYNC_TEST_PATTERNS = '''
# ── 基础: pytest-asyncio ──
@pytest.mark.asyncio
async def test_async_function():
    result = await async_calculate(100)
    assert result == 150

# ── 超时保护 ──
@pytest.mark.asyncio
@pytest.mark.timeout(5)  # 5秒没返回就失败
async def test_slow_external_api():
    result = await fetch_external_data()
    assert result is not None

# ── 异步上下文管理器 ──
@pytest.mark.asyncio
async def test_asgi_app():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200

# ── 异步事件循环管理 ──
@pytest.fixture(scope="session")
def event_loop():
    """让所有异步测试共享 one 事件循环 (大幅提速)"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# ── 异步模拟 ──
@pytest.mark.asyncio
async def test_async_mock():
    with patch("app.services.AsyncEmailService.send", new_callable=AsyncMock) as mock:
        mock.return_value = {"status": "sent"}
        result = await order_service.notify_user(1)
        mock.assert_awaited_once()
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第八部分: 数据库测试 — 事务回滚 vs Testcontainers        ║
# ╚═══════════════════════════════════════════════════════════╝

DB_TEST_PATTERNS = '''
# ── 方案 A: 事务回滚 (最快, 推荐) ──
@pytest_asyncio.fixture
async def db_session():
    """每个测试函数一个事务, 测试结束自动回滚"""
    async with UnitOfWork() as uow:
        # 在事务中插入测试数据
        product = Product(name="测试", price=1000)
        uow.session.add(product)
        await uow.session.flush()
        
        yield uow.session
        
        # 退出时 rollback, 不污染数据库
        # (UnitOfWork.__aexit__ 已经做了)

@pytest.mark.asyncio
async def test_create_order(db_session):
    repo = OrderRepository(db_session)
    order = await repo.create(user_id=1, product_id=1)
    assert order.id is not None

# ── 方案 B: Testcontainers (真正的隔离) ──
@pytest.fixture(scope="module")
def postgres_container():
    with PostgreSQLContainer("postgres:16-alpine") as pg:
        yield pg

@pytest_asyncio.fixture
async def async_client(postgres_container):
    """用真实 PostgreSQL 测试"""
    # 设置连接
    os.environ["DB_URL"] = postgres_container.get_connection_url()
    
    # 运行迁移
    subprocess.run(["alembic", "upgrade", "head"])
    
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

# 什么时候用方案 A (事务回滚)?
# - 开发环境, 本地跑测试
# - 单元测试级别
# - 要快速迭代

# 什么时候用方案 B (Testcontainers)?
# - CI/CD 环境
# - 兼容性测试 (不同 PostgreSQL 版本)
# - E2E 测试
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第九部分: HTTP API 测试                                   ║
# ╚═══════════════════════════════════════════════════════════╝

API_TEST_PATTERNS = '''
# ── FastAPI TestClient (同步) ──
from fastapi.testclient import TestClient

def test_health_check():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"

# ── httpx AsyncClient (异步, 推荐) ──
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_create_product():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create
        resp = await client.post("/api/v1/products", json={
            "name": "测试商品", "price": 5000, "stock": 10
        })
        assert resp.status_code == 201
        product_id = resp.json()["id"]
        
        # Get
        resp = await client.get(f"/api/v1/products/{product_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "测试商品"
        
        # List
        resp = await client.get("/api/v1/products?keyword=测试")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

# ── 认证测试 ──
@pytest.mark.asyncio
async def test_require_auth():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 没带 token → 401
        resp = await client.get("/api/v1/admin/products")
        assert resp.status_code == 401
        
        # 带有效 token → 200
        token = create_access_token(user_id=1, role="admin")
        resp = await client.get(
            "/api/v1/admin/products",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第十部分: 覆盖率策略                                       ║
# ╚═══════════════════════════════════════════════════════════╝

COVERAGE_PATTERNS = '''
# ── .coveragerc ──
[run]
source = ./app
omit =
    */migrations/*
    */tests/*
    */__init__.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise NotImplementedError
    if __name__ == "__main__":
    pass

# ── 运行 ──
pytest --cov=app --cov-report=html --cov-report=term-missing
# 输出 HTML 覆盖率报告 + 终端显示缺失行

# ── 高级工程师的覆盖率标准 ──
# 覆盖率 < 70%  → 你测得太少了
# 覆盖率 > 95%  → 你测了太多 (测试可能脆弱)
# Sweet spot:   80-90%

# 关键是要测:
# - 所有 if-else 分支 (不是行覆盖, 是分支覆盖)
# - 所有异常路径
# - 边界值

# ── 分支覆盖 (Branch Coverage) ──
# 普通覆盖: 这行执行到了吗?
# 分支覆盖: if 的 True 和 False 都执行到了吗?
pytest --cov=app --cov-branch  # 加 --cov-branch

# ── 什么不用测 ──
# - 框架代码 (FastAPI/Django)
# - ORM 模型 (除非有自定义方法)
# - 配置类 (除非有逻辑)
# - Tool 类 (测试它们的使用者就够了)
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第十一部分: Factory Boy — 测试数据工厂                   ║
# ╚═══════════════════════════════════════════════════════════╝

FACTORY_PATTERNS = '''
# 为什么用 Factory Boy?
# - 不用在每个测试里手动创建数据
# - 变更模型字段时只需要改 Factory
# - 自动生成合理的假数据

# ── 定义 Factory ──
class ProductFactory(factory.Factory):
    class Meta:
        model = Product
    
    name = factory.Sequence(lambda n: f"测试商品{n}")
    price = factory.Faker("random_int", min=100, max=100000)
    stock = factory.Faker("random_int", min=0, max=1000)
    is_active = True

class CategoryFactory(factory.Factory):
    class Meta:
        model = Category
    
    name = factory.Sequence(lambda n: f"分类{n}")
    products = factory.RelatedFactoryList(
        ProductFactory, factory_related_name="category", size=3
    )

# ── 在测试中使用 ──
@pytest.mark.asyncio
async def test_category_with_products(db_session):
    # 创建分类 + 3个产品 一行搞定
    category = await CategoryFactory.create_async(
        products__size=5  # 让 Factory 创建 5 个关联产品
    )
    assert len(category.products) == 5

# ── 好处对比 ──
# 没有 Factory:
#   product = Product(name="测试", price=100, stock=0, is_active=True)
#   db_session.add(product)
#   每个测试都重复这段

# 有 Factory:
#   product = ProductFactory.create()
#   一行搞定, 字段自动填充
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第十二部分: 突变测试 — 检验你的测试质量                  ║
# ╚═══════════════════════════════════════════════════════════╝

MUTATION_TEST_PATTERNS = '''
# 普通测试: 告诉你有多少行代码被执行了 (覆盖率)
# 突变测试: 故意在代码里"引入 bug", 看你的测试能不能发现
#   
# 例子:
#   原代码: if stock >= 0:
#   突变体: if stock > 0:    (把 >= 改成了 >)
#   你的测试如果能发现 → 测试质量为 1/1
#   你的测试没发现     → 你的测试没覆盖边界

# ── mutmut 配置 (mutmut.toml) ──
[tool.mutmut]
paths_to_exclude = ["*/migrations/*", "*/tests/*"]
runner = "python -m pytest -x"

# ── 运行 ──
mutmut run --paths-to-mutate ./app/services/
mutmut results
mutmut show 1  # 查看第一个存活突变体

# ── 预期结果 ──
# 新项目: 突变评分 60-70%
# 成熟项目: 突变评分 85%+
# 100% 不可能 (有些突变语义等价)

# ── 什么时候用突变测试 ──
# - 关键路径 (支付/安全/认证)
# - 重构老代码时 (确保测试网住了逻辑)
# - CI 中每周跑一次 (不是每次提交, 太慢)

# ── 什么时候不用 ──
# - 每改一行就跑 (太慢)
# - 覆盖率低于 80% 先补覆盖
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第十三部分: 性能测试 — Locust 脚本模板                   ║
# ╚═══════════════════════════════════════════════════════════╝

PERF_TEST_PATTERNS = '''
# ── Locust 性能测试脚本 (locustfile.py) ──
from locust import HttpUser, task, between

class WebsiteUser(HttpUser):
    wait_time = between(0.5, 2)  # 模拟人类操作间隔
    
    def on_start(self):
        """每个用户登录一次"""
        resp = self.client.post("/auth/login", json={
            "username": "test@test.com", "password": "password"
        })
        self.token = resp.json()["access_token"]
        self.client.headers["Authorization"] = f"Bearer {self.token}"
    
    @task(3)  # 权重 3: 高频操作
    def list_products(self):
        self.client.get("/api/v1/products?page=1&size=20")
    
    @task(1)  # 权重 1: 低频操作
    def create_order(self):
        self.client.post("/api/v1/orders", json={
            "product_id": 1, "quantity": 1
        })

# 运行:
# locust -f locustfile.py --host=http://localhost:8000
# 打开 http://localhost:8089 配置用户数

# ── 性能测试关注指标 ──
# - P50 延迟 < 200ms
# - P95 延迟 < 500ms
# - P99 延迟 < 1000ms
# - 错误率 < 0.1%
# - 吞吐量 > 1000 rps (取决于业务)
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第十四部分: CI/CD 集成 — GitHub Actions                  ║
# ╚═══════════════════════════════════════════════════════════╝

CI_PATTERNS = '''
# ── .github/workflows/test.yml ──
name: Test
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_db
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports: ["5432:5432"]
      redis:
        image: redis:7-alpine
        ports: ["6379:6379"]
    
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: "pip"
      
      - run: pip install -e ".[dev]"
      
      - name: Lint
        run: ruff check .
      
      - name: Type check
        run: mypy app/
      
      - name: Test with coverage
        env:
          DB_URL: postgresql://test:test@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest --cov=app --cov-report=term-missing \
                 --cov-fail-under=80 -n auto --timeout=30
      
      - name: Security scan
        run: |
          bandit -r app/ -f json -o bandit-report.json || true
          safety check || true
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4

# ── pre-commit hooks (.pre-commit-config.yaml) ──
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.4.0
    hooks:
      - id: ruff
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.9.0
    hooks:
      - id: mypy
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest --quiet --no-header -x
        language: system
        types: [python]
        pass_filenames: false
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 第十五部分: 高级工程师的测试 mindset                       ║
# ╚═══════════════════════════════════════════════════════════╝

MINDSET = """
高级测试工程师的思维模式:

1. "测试不是为了证明代码是对的"
   → 测试是为了证明代码是错的, 而且还没找到 bug

2. "写测试是设计行为, 不是验证行为"
   → 写测试思考的是"这个函数应该怎么用", 而不是"这个函数怎么实现的"
   → 如果测试很难写 → 设计有问题

3. "代码覆盖率不重要, 关键路径覆盖率重要"
   → 支付/认证/订单/数据完整性的测试必须有
   → 配置/模板/路由 的测试可有可无

4. "每个测试只测一个概念"
   → 一个测试函数里不要又测创建又测删除又测权限
   → 每个测试只断言 1-3 个关键值

5. "我喜欢黑盒测试, 不关心实现"
   → 只测输入/输出, 不测内部调用了什么
   → 重构时不用改测试

6. "失败的测试比通过的测试更有价值"
   → 通过告诉你现在正常
   → 失败告诉你哪里坏了, 坏了多久

7. "Mock 是最后的手段, 不是首选"
   → 先用 Fake, 再用 Stub, 最后才用 Mock
   → 一个 Mock 都没用的测试, 是最稳的测试
"""

if __name__ == "__main__":
    print("""
高级测试架构参考
==================
覆盖 15 个模块:

  ▸ 测试金字塔 + 策略      ▸ TDD 三循环
  ▸ Fixture 设计模式       ▸ 参数化高级用法
  ▸ Hypothesis 属性测试     ▸ Mock 时机判断
  ▸ 异步测试               ▸ 数据库测试
  ▸ HTTP API 测试           ▸ 覆盖率策略
  ▸ Factory Boy             ▸ 突变测试
  ▸ 性能测试 (Locust)       ▸ CI/CD 集成
  ▸ 测试工程师 mindset

已安装工具: pytest 9.1, hypothesis 6.163, factory-boy 3.3,
            pytest-asyncio, pytest-cov, pytest-xdist

快速运行示例:
  cd tools/testing/
  pytest demo_test.py -v --cov
    """)
    
    for name, content in [
        ("测试金字塔", TEST_PYRAMID),
        ("TDD", TDD_CYCLE),
        ("Fixture", FIXTURE_PATTERNS),
        ("参数化", PARAMETRIZE_PATTERNS),
        ("Hypothesis", HYPOTHESIS_PATTERNS),
        ("Mock", MOCK_PATTERNS),
        ("异步", ASYNC_TEST_PATTERNS),
        ("数据库测试", DB_TEST_PATTERNS),
        ("API测试", API_TEST_PATTERNS),
        ("覆盖率", COVERAGE_PATTERNS),
        ("Factory", FACTORY_PATTERNS),
        ("突变测试", MUTATION_TEST_PATTERNS),
        ("性能测试", PERF_TEST_PATTERNS),
        ("CI/CD", CI_PATTERNS),
        ("Mindset", MINDSET),
    ]:
        lines = content.strip().count('\n') + 1
        print(f"  📄 {name:12s} {lines:>4} 行")
