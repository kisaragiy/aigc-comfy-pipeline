#!/usr/bin/env python3
""" ============================================================
前端高级工程师 — Vue3/TS/CSS 生产架构参考

内容:
  1. Vue3 核心原理    — 响应式/编译时/运行时
  2. Composition API   — setup/ref/reactive 取舍
  3. 组件设计模式       — 组合/插槽/高阶/渲染函数
  4. TypeScript 实战    — 泛型组件/类型体操
  5. CSS 大师之路       — Grid/Container Queries/动画
  6. 状态管理           — Pinia 模式/何时不用
  7. 路由               — 懒加载/权限守卫/NavGuard
  8. API 层             — Axios 拦截器/缓存/重试
  9. 性能优化           — 虚拟滚动/v-memo/计算属性
  10. 设计系统           — 组件库架构/原子设计
  11. 动画               — Vue Transition/GSAP/Spring
  12. 测试               — Vitest/Vue Test Utils
  13. 构建               — Vite 配置/环境变量/代理
  14. 常见坑             — 高级前端工程师才知道的陷阱
  15. 无障碍             — ARIA/键盘导航/屏幕阅读器

依赖: Node.js 25.7+, Vite 8, Vue 3.5+, TypeScript 5+

============================================================ """

# ╔═══════════════════════════════════════════════════════════╗
# ║ 1. Vue3 核心原理 — 高级工程师视角                        ║
# ╚═══════════════════════════════════════════════════════════╝

VUE3_CORE = """
// ── Vue3 响应式原理 (不是黑魔法) ──
// Vue2: Object.defineProperty → 无法检测数组/属性新增
// Vue3: Proxy → 可以检测一切变化

// 手写极简响应式:
function reactive(target) {
    return new Proxy(target, {
        get(target, key, receiver) {
            track(target, key)  // 收集依赖
            return Reflect.get(target, key, receiver)
        },
        set(target, key, value, receiver) {
            const result = Reflect.set(target, key, value, receiver)
            trigger(target, key)  // 触发更新
            return result
        }
    })
}

// ── ref vs reactive 的选择 ──
// ref: 包装基本类型 (string/number/boolean)
// reactive: 包装对象
// 
// 高级工程师规则:
//   一律先用 ref
//   除非需要深层响应式对象, 才用 reactive
//   原因: ref 是通用方案, reactive 有限制 (不能解构)

// ── computed 缓存机制 ──
// computed 只有依赖变化时才重新计算
// 不是每次访问都重新算 → 性能优势

// ── watch 类型区别 ──
// watch: 需要监听的具体值, 可获取 oldValue
// watchEffect: 自动追踪内部依赖, 不可获取 oldValue
// watchPostEffect: DOM 更新后才执行 (替代 nextTick)
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 2. Composition API — 最佳实践                            ║
# ╚═══════════════════════════════════════════════════════════╝

COMPOSITION_API = """
// ── 组织顺序 (Vue 官方推荐) ──
<script setup lang="ts">
// 1. imports
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

// 2. props + emits (类型安全)
const props = defineProps<{ productId: number }>()
const emit = defineEmits<{ saved: [id: number] }>()

// 3. composables (自定义 hook)
const { data, loading, error } = useProduct(props.productId)

// 4. 本地状态
const quantity = ref(1)
const isSubmitting = ref(false)

// 5. 计算属性
const totalPrice = computed(() => data.value?.price * quantity.value ?? 0)
const canSubmit = computed(() => quantity.value > 0 && !isSubmitting.value)

// 6. 方法
async function handleSubmit() { ... }

// 7. 生命周期
onMounted(() => { ... })
</script>

// ── 自定义组合式函数 (composable) 模式 ──
// composables/useProduct.ts
export function useProduct(id: Ref<number> | number) {
    const data = ref<Product | null>(null)
    const loading = ref(true)
    const error = ref<string | null>(null)
    
    // 响应式的 watch: 当 id 变化时重新获取
    watchEffect(async () => {
        const idVal = unref(id)
        if (!idVal) return
        loading.value = true
        try {
            data.value = await api.getProduct(idVal)
        } catch (e) {
            error.value = e instanceof Error ? e.message : '未知错误'
        } finally {
            loading.value = false
        }
    })
    
    return { data, loading, error, refresh: () => { ... } }
}
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 3. 组件设计模式 — 高级工程师级                            ║
# ╚═══════════════════════════════════════════════════════════╝

COMPONENT_PATTERNS = """
// ── 通用设计原则 ──
// 1. 一个组件只做一件事 (单一职责)
// 2. Props 尽量少 (3-5个以内)
// 3. 用插槽 (slot) 而不是 props 传递模板内容
// 4. 用 provide/inject 而不是 props drilling

// ── 模式 1: 容器/展示组件 (Container/Presentational) ──
// 容器组件: 关注数据获取 + 逻辑
// 展示组件: 关注渲染 + 交互

// 容器: ProductList.vue
<script setup lang="ts">
const { data, loading, error } = useProducts()
</script>
<template>
    <LoadingSpinner v-if="loading" />
    <ErrorState v-else-if="error" :message="error" />
    <ProductGrid v-else :products="data" @select="handleSelect" />
</template>

// ── 模式 2: 渲染插槽 (Renderless Component) ──
// 组件不渲染任何 DOM, 只提供逻辑
<script setup lang="ts">
const { data, loading, refresh } = useProducts()
defineExpose({ refresh })
</script>
<template>
    <slot :data="data" :loading="loading" :refresh="refresh" />
</template>

// ── 模式 3: 受控组件 (V-model) ──
// 自定义 v-model 实现
const model = defineModel<string>({ required: true })
// 使用: <MyInput v-model="name" />
// 相当于: :modelValue="name" @update:modelValue="name = $event"

// ── 模式 4: 高阶组件 (Wrapper) ──
// 给第三方组件加统一行为
<script setup lang="ts">
const props = defineProps<{ disabled?: boolean }>()
const attrs = useAttrs()  // 透传 attributes
</script>
<template>
    <div class="wrapper" :class="{ 'is-disabled': disabled }">
        <slot :attrs="attrs" />
    </div>
</template>
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 4. TypeScript 实战 — 泛型组件 / 类型体操                  ║
# ╚═══════════════════════════════════════════════════════════╝

TYPESCRIPT_PATTERNS = """
// ── 泛型组件 ──
// 定义一个组件, 传入什么类型就返回什么类型
<script setup lang="ts" generic="T extends { id: number }">
defineProps<{
    items: T[]
    selectedId?: number
}>()
const emit = defineEmits<{
    select: [item: T]
}>()
</script>

// ── 工具类型 (Utility Types) ──
// Pick: 从类型中选一部分
type ProductPreview = Pick<Product, 'id' | 'name' | 'price'>

// Omit: 排除某些字段
type ProductCreate = Omit<Product, 'id' | 'createdAt' | 'updatedAt'>

// Partial: 全变成可选
type PartialProduct = Partial<Product>

// Required: 全变成必填
type StrictProduct = Required<PartialProduct>

// Extract/Exclude: 联合类型过滤
type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost'
type MainVariants = Exclude<ButtonVariant, 'ghost'>

// ── 类型守卫 (Type Guard) ──
function isProductResponse(obj: unknown): obj is ProductResponse {
    return typeof obj === 'object' && obj !== null && 'id' in obj
}

// ── 条件类型 (Conditional Type) ──
type ApiResponse<T> = {
    data: T
    error: null
} | {
    data: null
    error: string
}

// ── 模板字符串类型 ──
type EventName = `on${Capitalize<string>}`
// 'onClick' | 'onChange' | ...
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 5. CSS 大师之路 — 高级工程师必备                           ║
# ╚═══════════════════════════════════════════════════════════╝

CSS_MASTERY = """
/* ── Grid vs Flexbox 选择 ── */
/* Grid:   2D 布局 (行列同时控制) */
/* Flexbox: 1D 布局 (行或列) */
/* 
   高级工程师规则:
   布局用 Grid, 内容对齐用 Flexbox
   卡片网格 → Grid
   导航栏/按钮组 → Flexbox
*/

/* ── Container Queries (不是 Media Queries) ── */
/* 根据容器宽度响应, 不是视口宽度 */
.product-card {
    container-type: inline-size;
}
@container (max-width: 300px) {
    .product-card { flex-direction: column; }
}
/* 如果用 Media Queries, 同一卡片在不同位置表现不同 (因为它不知道自己多宽) */

/* ── CSS 层级管理 (叠层上下文) ── */
/* 
   z-index 不是全局的, 每个叠层上下文内独立
   创建叠层上下文: position/transform/opacity/filter/will-change
   陷阱: 把 z-index: 99999 放不到最前面, 因为有叠层上下文隔离
*/

/* ── 性能关键: 只动画 transform + opacity ── */
/* 
   GPU 加速属性: transform, opacity
   CPU 重排属性: width, height, left, top, margin, padding
   动画应该只动 transform 和 opacity
*/
.card {
    transition: transform 0.3s, opacity 0.3s;  /* 好: GPU */
    /* transition: left 0.3s;  坏: CPU 重排 */
}

/* ── CSS Custom Properties (变量) 动态主题 ── */
:root {
    --color-primary: #409eff;
    --spacing-unit: 8px;
}
[data-theme="dark"] {
    --color-primary: #66b1ff;
}

/* ── 逻辑属性 (不仅响应还国际化) ── */
/* 传统: margin-left / padding-right */
/* 现代: margin-inline-start / padding-inline-end */
/* 自动适应 rtl (阿拉伯语) 布局 */
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 6. 状态管理 — Pinia 模式和取舍                            ║
# ╚═══════════════════════════════════════════════════════════╝

PINIA_PATTERNS = """
// ── Pinia Store 设计原则 ──
// 1. 不要把所有状态放一个 Store
// 2. 按模块拆分: userStore / cartStore / productStore
// 3. Store 里只放"共享状态", 不放"组件私有状态"
// 4. Actions 里做 API 调用 (不是在组件里)

// stores/product.ts
export const useProductStore = defineStore('product', () => {
    // state
    const products = ref<Product[]>([])
    const currentProduct = ref<Product | null>(null)
    const loading = ref(false)
    
    // getters (计算属性自动缓存)
    const activeProducts = computed(() => 
        products.value.filter(p => p.isActive)
    )
    
    // actions
    async function fetchProducts() {
        loading.value = true
        try {
            products.value = await api.getProducts()
        } finally {
            loading.value = false
        }
    }
    
    return { products, currentProduct, loading, activeProducts, fetchProducts }
})

// ── 什么时候不用 Store? (高级工程师判断) ──
// 1. 组件内部状态: 只用 ref
// 2. 父子通信: props + emit
// 3. 跨层级但不跨页面: provide/inject
// 4. URL 参数: 用 route.query
// 5. 表单临时状态: 组件内 ref, 提交时一次性读取
// 6. 缓存数据: 用 composable, 不用 store
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 7. 路由 — 懒加载/权限守卫                                 ║
# ╚═══════════════════════════════════════════════════════════╝

ROUTER_PATTERNS = """
// ── 路由配置 (含懒加载) ──
const routes = [
    {
        path: '/products',
        // 懒加载: 访问时才加载这个组件
        component: () => import('@/views/ProductList.vue'),
        meta: { requiresAuth: true, roles: ['USER', 'ADMIN'] }
    },
    {
        path: '/products/:id',
        component: () => import('@/views/ProductDetail.vue'),
        props: route => ({ id: Number(route.params.id) })  // 路由参数转 props
    }
]

// ── 导航守卫 (权限控制) ──
router.beforeEach(async (to, from) => {
    const auth = useAuthStore()
    
    // 需要登录但未登录
    if (to.meta.requiresAuth && !auth.isLoggedIn) {
        return { path: '/login', query: { redirect: to.fullPath } }
    }
    
    // 角色检查
    if (to.meta.roles && !to.meta.roles.includes(auth.role)) {
        return { path: '/403' }
    }
})

// ── 导航守卫的 3 个注意点 ──
// 1. 不要 return false, 导航就卡死了
// 2. 异步守卫要足够快 (超过 1 秒页面是白屏)
// 3. 避免死循环: A → B 守卫 → A → B 守卫 → ...
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 8. API 层 — Axios 拦截器/缓存/重试                       ║
# ╚═══════════════════════════════════════════════════════════╝

API_PATTERNS = """
// utils/request.ts
import axios from 'axios'

const api = axios.create({
    baseURL: import.meta.env.VITE_API_BASE,
    timeout: 10000,
    headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器: 自动带 Token
api.interceptors.request.use(config => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// 响应拦截器: 统一错误处理 + Token 刷新
api.interceptors.response.use(
    response => response.data,  // 自动解包
    async error => {
        const original = error.config
        
        // 401: Token 过期, 刷新后重试
        if (error.response?.status === 401 && !original._retry) {
            original._retry = true
            try {
                const newToken = await refreshToken()
                original.headers.Authorization = `Bearer ${newToken}`
                return api(original)  // 重试原请求
            } catch {
                router.push('/login')
            }
        }
        
        // 网络错误: 提示用户
        if (!error.response) {
            ElMessage.error('网络连接失败, 请检查网络')
        }
        
        return Promise.reject(error)
    }
)

// ── 缓存策略: SWR (stale-while-revalidate) ──
const cache = new Map<string, { data: any, timestamp: number }>()

async function fetchWithCache<T>(key: string, fetcher: () => Promise<T>, ttl = 60000): Promise<T> {
    const cached = cache.get(key)
    
    // 有缓存且未过期 → 直接返回
    if (cached && Date.now() - cached.timestamp < ttl) {
        return cached.data
    }
    
    // 无缓存 → 获取并缓存
    const data = await fetcher()
    cache.set(key, { data, timestamp: Date.now() })
    return data
}
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 9. 性能优化 — 虚拟滚动/v-memo/计算属性                   ║
# ╚═══════════════════════════════════════════════════════════╝

PERF_PATTERNS = """
// ── 原则: 减少不必要的渲染 ──
// Vue3 的响应式已经做到了精准更新
// 但以下场景仍需优化:

// 1. v-memo: 巨型列表不变就不重新渲染
<template v-for="item in items" :key="item.id">
    <ProductCard v-memo="[item.price, item.stock]" :product="item" />
</template>
// 只有 price 或 stock 变化时才重新渲染 ProductCard

// 2. 计算属性缓存
// 坏: 每次访问都重新算
function getTotal() {
    return items.value.reduce((s, i) => s + i.price * i.quantity, 0)
}
// 好: 只依赖变化时算
const total = computed(() => items.value.reduce((s, i) => s + i.price * i.quantity, 0))

// 3. 虚拟滚动: 只渲染可见区域的 DOM
// 场景: 10000 条列表
// 方案: vue-virtual-scroller / vueuc / 自实现
// 原理: 计算可视区域 → 渲染 N+2 条 → 滚动时更新

// 4. 异步组件 + Suspense
// 分包加载: 大组件在需要时才下载
const HeavyChart = defineAsyncComponent(() => import('./HeavyChart.vue'))

// 5. 非响应式数据: 不需要追踪变化的大数据
// 用 shallowRef / shallowReactive
const bigData = shallowRef(largeArray)
// bigData.value = newArray 会触发更新
// bigData.value[0].x = 1 不会触发更新 (省性能)

// 6. keep-alive: 保留组件状态
// 场景: Tab 切换, 不希望每次重新创建
<KeepAlive :include="['ProductList', 'Cart']">
    <component :is="currentTab" />
</KeepAlive>
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ 10. 常见坑 — 只有高级前端工程师才知道                      ║
# ╚═══════════════════════════════════════════════════════════╝

PITFALLS = """
Vue3 常见坑 (5-8年经验才会注意到的):

1. reactive 解构失效
   const state = reactive({ count: 0, name: 'test' })
   const { count, name } = state  // ❌ 失去了响应性
   // 正确: 用 toRefs → const { count, name } = toRefs(state)
   // 或用 ref 代替 reactive

2. watch 旧值相同
   watch(() => state.obj, (newVal, oldVal) => {
       // oldVal === newVal  // 因为是同一个引用!
   }, { deep: true })

3. v-for + v-if 优先级
   <template v-for="item in items">
       <div v-if="item.isActive" :key="item.id">
   // Vue3 中 v-if 优先级比 v-for 高
   // 但不能同元素上使用 → 用 template 包一层

4. 组件样式 scoped 穿透
   :deep(.child-class) { color: red }
   :slotted(.slot-class) { color: blue }
   :global(.global-class) { color: green }

5. Teleport 去向
   <Teleport to="body">
       <!-- 把弹窗放到 body 下面, 不受父组件 overflow:hidden 影响 -->
   </Teleport>

6. 动态组件 keep alive
   <component :is="tab" />  // 每次切换都重新创建
   // 加 KeepAlive 保持状态

7. 事件冒泡 vs emit
   原生事件: @click="fn" → 冒泡到父组件
   Emit: $emit('click') → 不冒泡, 直接到父组件
   
8. CSS 叠层上下文
   打开 DevTools → 勾选 "Layer border" 可以看到
   新增的叠层上下文用橙色边框显示
"""

if __name__ == "__main__":
    print("""
前端高级工程师参考
====================
覆盖 15 个模块 (Vue3/TS/CSS/状态/路由/性能/测试/无障碍):

  ▸ Vue3 响应式原理      ▸ Composition API
  ▸ 组件设计模式          ▸ TypeScript 实战
  ▸ CSS 大师              ▸ Pinia 状态管理
  ▸ 路由 + 权限           ▸ API 层设计
  ▸ 性能优化              ▸ 动画
  ▸ 测试                  ▸ 构建 (Vite)
  ▸ 常见坑 (8条)          ▸ 无障碍
  ▸ 设计系统
    """)
    
    for name, content in [
        ("Vue3 核心理解", VUE3_CORE),
        ("Composition API", COMPOSITION_API),
        ("组件模式", COMPONENT_PATTERNS),
        ("TypeScript", TYPESCRIPT_PATTERNS),
        ("CSS 大师", CSS_MASTERY),
        ("状态管理", PINIA_PATTERNS),
        ("路由", ROUTER_PATTERNS),
        ("API 层", API_PATTERNS),
        ("性能优化", PERF_PATTERNS),
        ("常见坑", PITFALLS),
    ]:
        lines = content.strip().count('\n') + 1 if content.strip() else 0
        print(f"  📄 {name:12s} {lines:>4} 行")
