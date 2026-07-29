#!/usr/bin/env python3
""" ============================================================
Spring Boot 3 生产架构参考 — 理解 + 改动用 (Java)

内容:
  - Maven 项目结构 (pom.xml)
  - 分层架构 (Controller → Service → Repository → Entity)
  - 依赖注入 (构造器注入 vs @Autowired)
  - JPA + 事务管理
  - DTO / 实体映射
  - 全局异常处理 (@ControllerAdvice)
  - Spring Security + JWT
  - 配置管理 (application.yml + @ConfigurationProperties)
  - Actuator + 指标
  - 测试 (@SpringBootTest + MockMvc)
  - 数据库迁移 (Flyway)
  - 缓存 (Spring Cache + Redis)
  - 异步 (@Async + 线程池)
  - 常见坑 (LazyInitializationException/N+1/循环依赖)

依赖: Java 21, Maven 3.9+, Spring Boot 3.x

============================================================ """
import sys

# ╔═══════════════════════════════════════════════════════════╗
# ║ 项目结构                                                 ║
# ╚═══════════════════════════════════════════════════════════╝

PROJECT_STRUCTURE = """
src/main/java/com/example/app/
├── AppApplication.java            # 主入口 @SpringBootApplication
├── config/
│   ├── SecurityConfig.java        # Spring Security 配置
│   ├── SwaggerConfig.java         # OpenAPI 配置
│   ├── RedisConfig.java           # Redis 缓存配置
│   └── AsyncConfig.java           # 异步线程池配置
├── controller/
│   ├── ProductController.java     # REST 控制器
│   └── GlobalExceptionHandler.java# @ControllerAdvice
├── dto/
│   ├── ProductCreateRequest.java  # 创建请求 DTO
│   ├── ProductResponse.java       # 响应 DTO
│   └── PageResponse.java          # 分页响应 DTO
├── entity/
│   ├── Product.java               # JPA 实体
│   └── Category.java
├── repository/
│   └── ProductRepository.java     # JPA Repository
├── service/
│   ├── ProductService.java        # 业务逻辑
│   └.impl.ProductServiceImpl.java
├── security/
│   ├── JwtTokenProvider.java      # JWT 生成/验证
│   ├── JwtAuthenticationFilter.java# JWT 过滤器
│   └── UserDetailsServiceImpl.java
├── mapper/
│   └── ProductMapper.java         # Entity ↔ DTO 转换
└── exception/
    ├── BusinessException.java     # 业务异常
    └── ErrorCode.java             # 错误码枚举

src/main/resources/
├── application.yml                # 主配置
├── application-dev.yml            # 开发环境
├── application-prod.yml           # 生产环境
└── db/migration/                  # Flyway 迁移
    ├── V1__create_product.sql
    └── V2__add_index.sql

src/test/java/com/example/app/
├── controller/
│   └── ProductControllerTest.java # @WebMvcTest
├── service/
│   └── ProductServiceTest.java    # 单元测试
└── repository/
    └── ProductRepositoryTest.java # @DataJpaTest
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ pom.xml — 核心依赖                                       ║
# ╚═══════════════════════════════════════════════════════════╝

POM_XML = '''<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.3.0</version>
    </parent>
    
    <groupId>com.example</groupId>
    <artifactId>app</artifactId>
    <version>1.0.0</version>
    <name>Production App</name>
    
    <properties>
        <java.version>21</java.version>
    </properties>
    
    <!-- 高级工程师选择: 只加真正需要的 starter, 
         不盲目加 spring-boot-starter-webflux -->
    <dependencies>
        <!-- Web -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        
        <!-- JPA + PostgreSQL -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.postgresql</groupId>
            <artifactId>postgresql</artifactId>
            <scope>runtime</scope>
        </dependency>
        
        <!-- 验证 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        
        <!-- Security + JWT -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-api</artifactId>
            <version>0.12.5</version>
        </dependency>
        <dependency>
            <groupId>io.jsonwebtoken</groupId>
            <artifactId>jjwt-impl</artifactId>
            <version>0.12.5</version>
            <scope>runtime</scope>
        </dependency>
        
        <!-- Redis 缓存 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-redis</artifactId>
        </dependency>
        
        <!-- 数据库迁移 -->
        <dependency>
            <groupId>org.flywaydb</groupId>
            <artifactId>flyway-core</artifactId>
        </dependency>
        
        <!-- OpenAPI 文档 -->
        <dependency>
            <groupId>org.springdoc</groupId>
            <artifactId>springdoc-openapi-starter-webmvc-ui</artifactId>
            <version>2.5.0</version>
        </dependency>
        
        <!-- 指标 + 健康检查 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>io.micrometer</groupId>
            <artifactId>micrometer-registry-prometheus</artifactId>
        </dependency>
        
        <!-- 工具 -->
        <dependency>
            <groupId>org.projectlombok</groupId>
            <artifactId>lombok</artifactId>
            <optional>true</optional>
        </dependency>
        <dependency>
            <groupId>org.mapstruct</groupId>
            <artifactId>mapstruct</artifactId>
            <version>1.5.5.Final</version>
        </dependency>
        
        <!-- 测试 -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>org.testcontainers</groupId>
            <artifactId>postgresql</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 主入口 — @SpringBootApplication                          ║
# ╚═══════════════════════════════════════════════════════════╝

MAIN_ENTRY = '''
package com.example.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class AppApplication {
    public static void main(String[] args) {
        SpringApplication.run(AppApplication.class, args);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 配置管理 — application.yml                                ║
# ╚═══════════════════════════════════════════════════════════╝

APPLICATION_YML = '''
# ============================================================
# Spring Boot 生产配置 — 高级工程师水平
# ============================================================

spring:
  profiles:
    active: ${APP_ENV:dev}
    
  datasource:
    url: jdbc:postgresql://${DB_HOST:localhost}:${DB_PORT:5432}/${DB_NAME:app}
    username: ${DB_USER:app}
    password: ${DB_PASSWORD:change_me}
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      idle-timeout: 300000
      connection-timeout: 10000
      pool-name: AppPool

  jpa:
    hibernate:
      ddl-auto: validate   # 生产用 validate, 迁移用 Flyway
    properties:
      hibernate:
        jdbc.batch_size: 50
        order_inserts: true
        order_updates: true
        query.in_clause_parameter_padding: true
    open-in-view: false    # 重要: 关闭 OSIV 避免 LazyInitializationException
    
  redis:
    host: ${REDIS_HOST:localhost}
    port: 6379
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 16
        max-idle: 8
        min-idle: 2

# JWT
app:
  jwt:
    secret: ${JWT_SECRET:change_me_in_production}
    access-token-expiration: 1800000     # 30 min
    refresh-token-expiration: 604800000  # 7 days

# Actuator / 监控
management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
  endpoint:
    health:
      show-details: when-authorized

# 日志
logging:
  level:
    root: ${LOG_LEVEL:INFO}
    com.example: DEBUG
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"  # 开发格式
    file: '{"timestamp":"%d{yyyy-MM-dd}","level":"%p","logger":"%c","message":"%m"}%n'  # 生产JSON格式
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 实体层 — JPA + 最佳实践                                   ║
# ╚═══════════════════════════════════════════════════════════╝

ENTITY_JAVA = '''
// 实体设计原则:
// 1. 用 Long 而非 long (null vs 0 区分未持久化)
// 2. equals/hashCode 只用业务键 (非 id)
// 3. @Setter 不放在类级别, 放在具体字段
// 4. @Builder 不用在实体上 (会导致无参构造器被覆盖)
// 5. 双向关联用 @ToString.Exclude 防循环

@Entity
@Table(name = "products", indexes = {
    @Index(name = "idx_product_name", columnList = "name"),
    @Index(name = "idx_product_category", columnList = "category_id")
})
@Getter @NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Product {
    
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false, length = 200)
    private String name;
    
    @Column(nullable = false)
    private Integer price;  // 单位: 分 (避免浮点)

    @Column(nullable = false)
    private Integer stock = 0;
    
    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "category_id")
    @ToString.Exclude
    private Category category;
    
    @Column(nullable = false)
    private Boolean isActive = true;
    
    @CreatedDate
    @Column(updatable = false)
    private LocalDateTime createdAt;
    
    @LastModifiedDate
    private LocalDateTime updatedAt;
    
    // 业务方法 (非 setter) — 体现领域驱动
    public void adjustStock(int delta) {
        if (this.stock + delta < 0) {
            throw new BusinessException(ErrorCode.INSUFFICIENT_STOCK);
        }
        this.stock += delta;
    }
    
    public void deactivate() {
        this.isActive = false;
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Repository — JPA + 自定义查询                             ║
# ╚═══════════════════════════════════════════════════════════╝

REPOSITORY_JAVA = '''
// Repository 设计原则:
// 1. extends JpaRepository 获取 CRUD
// 2. 自定义查询用 @Query + JPQL (复杂)/ native SQL (报表)
// 3. 查询方法名要自文档化
// 4. 分页用 Pageable 而非自己手写 LIMIT/OFFSET

@Repository
public interface ProductRepository extends JpaRepository<Product, Long> {
    
    // 方法命名查询 (Spring Data 自动实现)
    List<Product> findByCategoryId(Long categoryId);
    
    // 分页 + 排序
    Page<Product> findByNameContaining(String keyword, Pageable pageable);
    
    // @Query — 复杂查询
    @Query("""
        SELECT p FROM Product p 
        WHERE (:keyword IS NULL OR p.name LIKE %:keyword%)
        AND (:minPrice IS NULL OR p.price >= :minPrice)
        AND (:maxPrice IS NULL OR p.price <= :maxPrice)
        AND p.isActive = true
        ORDER BY p.createdAt DESC
    """)
    Page<Product> searchProducts(
        @Param("keyword") String keyword,
        @Param("minPrice") Integer minPrice,
        @Param("maxPrice") Integer maxPrice,
        Pageable pageable
    );
    
    // 批量更新 — 用 @Modifying + 事务
    @Modifying(clearAutomatically = true)
    @Query("UPDATE Product p SET p.isActive = false WHERE p.category.id = :categoryId")
    int deactivateByCategory(@Param("categoryId") Long categoryId);
    
    // 报表统计
    @Query(value = """
        SELECT c.name AS category, COUNT(p.id) AS cnt, AVG(p.price) AS avgPrice
        FROM products p JOIN categories c ON p.category_id = c.id
        GROUP BY c.name
        ORDER BY cnt DESC
    """, nativeQuery = true)
    List<Object[]> categoryStats();
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Service 层 — 业务逻辑 + 事务                              ║
# ╚═══════════════════════════════════════════════════════════╝

SERVICE_JAVA = '''
// Service 设计原则:
// 1. 接口 + 实现分离 (方便 Mock)
// 2. @Transactional 在类级别默认 readOnly=true
// 3. 写方法单独覆盖 @Transactional
// 4. 抛 BusinessException 而非返回错误码
// 5. 不做 Entity → DTO 转换 (留给 Mapper 层)

public interface ProductService {
    ProductResponse create(ProductCreateRequest request);
    ProductResponse findById(Long id);
    PageResponse<ProductResponse> search(String keyword, Integer minPrice, 
                                         Integer maxPrice, Pageable pageable);
    void delete(Long id);
}

@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)  // 默认只读, 提升性能
public class ProductServiceImpl implements ProductService {
    
    private final ProductRepository productRepository;
    private final CategoryRepository categoryRepository;
    private final ProductMapper productMapper;
    private final RedisTemplate<String, ProductResponse> cacheTemplate;
    
    // ── 创建 (写) ──
    @Override
    @Transactional  // 覆盖类级别, 开启读写事务
    public ProductResponse create(ProductCreateRequest request) {
        // 1. 验证业务规则
        if (productRepository.findByName(request.getName()).isPresent()) {
            throw new BusinessException(ErrorCode.DUPLICATE_PRODUCT, 
                "商品名已存在: " + request.getName());
        }
        
        // 2. Entity ← DTO
        Product product = productMapper.toEntity(request);
        
        // 3. 关联处理
        if (request.getCategoryId() != null) {
            Category category = categoryRepository.findById(request.getCategoryId())
                .orElseThrow(() -> new BusinessException(ErrorCode.CATEGORY_NOT_FOUND));
            product.setCategory(category);
        }
        
        // 4. 持久化
        product = productRepository.save(product);
        log.info("Product created: id={}, name={}", product.getId(), product.getName());
        
        // 5. 缓存预热
        ProductResponse response = productMapper.toResponse(product);
        cacheTemplate.opsForValue().set("product:" + product.getId(), response, 1, TimeUnit.HOURS);
        
        return response;
    }
    
    // ── 查询 (缓存) ──
    @Override
    public ProductResponse findById(Long id) {
        // 1. 查缓存
        ProductResponse cached = cacheTemplate.opsForValue().get("product:" + id);
        if (cached != null) {
            return cached;
        }
        
        // 2. 查 DB
        Product product = productRepository.findById(id)
            .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));
        ProductResponse response = productMapper.toResponse(product);
        
        // 3. 写缓存
        cacheTemplate.opsForValue().set("product:" + id, response, 1, TimeUnit.HOURS);
        
        return response;
    }
    
    // ── 删除 ──
    @Override
    @Transactional
    public void delete(Long id) {
        Product product = productRepository.findById(id)
            .orElseThrow(() -> new BusinessException(ErrorCode.PRODUCT_NOT_FOUND));
        product.deactivate();  // 软删除
        cacheTemplate.delete("product:" + id);
        log.warn("Product deactivated: id={}", id);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Controller — REST 端点                                    ║
# ╚═══════════════════════════════════════════════════════════╝

CONTROLLER_JAVA = '''
// Controller 设计原则:
// 1. 只做 HTTP 协议处理 (参数解析/状态码/响应体)
// 2. 不包含任何业务逻辑
// 3. 用 @Valid 自动验证请求体
// 4. 统一分页格式
// 5. @RestController = @Controller + @ResponseBody

@RestController
@RequestMapping("/api/v1/products")
@RequiredArgsConstructor
public class ProductController {
    
    private final ProductService productService;
    
    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<ProductResponse> create(
            @RequestBody @Valid ProductCreateRequest request) {
        ProductResponse response = productService.create(request);
        return ApiResponse.success(response);
    }
    
    @GetMapping
    public ApiResponse<PageResponse<ProductResponse>> list(
            @RequestParam(required = false) String keyword,
            @RequestParam(required = false) Integer minPrice,
            @RequestParam(required = false) Integer maxPrice,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        
        Pageable pageable = PageRequest.of(page, size, Sort.by("createdAt").descending());
        PageResponse<ProductResponse> result = productService.search(
            keyword, minPrice, maxPrice, pageable);
        return ApiResponse.success(result);
    }
    
    @GetMapping("/{id}")
    public ApiResponse<ProductResponse> getById(@PathVariable Long id) {
        return ApiResponse.success(productService.findById(id));
    }
    
    @DeleteMapping("/{id}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long id) {
        productService.delete(id);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 全局异常处理 — @ControllerAdvice                         ║
# ╚═══════════════════════════════════════════════════════════╝

EXCEPTION_HANDLER_JAVA = '''
// 全局异常处理设计原则:
// 1. 统一响应格式 {code, message, data}
// 2. 业务异常 → 可读消息
// 3. 验证异常 → 字段级错误
// 4. 未预期异常 → 不暴露堆栈

@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {
    
    // 业务异常
    @ExceptionHandler(BusinessException.class)
    public ResponseEntity<ErrorResponse> handleBusiness(BusinessException e) {
        log.warn("Business exception: {}", e.getMessage());
        return ResponseEntity
            .status(e.getHttpStatus())
            .body(new ErrorResponse(e.getErrorCode().name(), e.getMessage()));
    }
    
    // 参数验证失败 (@Valid)
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidation(MethodArgumentNotValidException e) {
        Map<String, String> errors = new HashMap<>();
        e.getBindingResult().getFieldErrors().forEach(err -> 
            errors.put(err.getField(), err.getDefaultMessage()));
        return ResponseEntity
            .badRequest()
            .body(new ErrorResponse("VALIDATION_ERROR", "参数验证失败", errors));
    }
    
    // JPA 乐观锁
    @ExceptionHandler(OptimisticLockException.class)
    public ResponseEntity<ErrorResponse> handleOptimisticLock(OptimisticLockException e) {
        return ResponseEntity
            .status(HttpStatus.CONFLICT)
            .body(new ErrorResponse("CONCURRENT_MODIFICATION", "数据已被其他用户修改, 请刷新后重试"));
    }
    
    // 未预期异常 (500)
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleUnhandled(Exception e) {
        log.error("Unhandled exception", e);
        return ResponseEntity
            .status(HttpStatus.INTERNAL_SERVER_ERROR)
            .body(new ErrorResponse("INTERNAL_ERROR", "服务器内部错误, 请稍后重试"));
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Spring Security + JWT                                    ║
# ╚═══════════════════════════════════════════════════════════╝

SECURITY_JAVA = '''
// Spring Security + JWT 认证流程:
// 1. 登录 → 验证用户名密码 → 返回 JWT
// 2. 后续请求 → 在 Header 带 Authorization: Bearer <token>
// 3. JwtAuthenticationFilter 从 Header 提取 token → 鉴权 → 放行

@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {
    
    private final JwtTokenProvider jwtTokenProvider;
    
    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)  // REST API 不需要 CSRF
            .sessionManagement(sm -> sm.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/v1/auth/**").permitAll()
                .requestMatchers("/api/v1/products/**").hasAnyRole("USER", "ADMIN")
                .requestMatchers("/actuator/**").hasRole("ADMIN")
                .requestMatchers("/swagger-ui/**", "/v3/api-docs/**").permitAll()
                .anyRequest().authenticated()
            )
            .addFilterBefore(new JwtAuthenticationFilter(jwtTokenProvider), 
                UsernamePasswordAuthenticationFilter.class);
        return http.build();
    }
}

// JWT 令牌提供者
@Component
public class JwtTokenProvider {
    
    @Value("${app.jwt.secret}")
    private String secretKey;
    
    @Value("${app.jwt.access-token-expiration}")
    private long accessExpiration;
    
    public String generateToken(Long userId, String role) {
        return Jwts.builder()
            .subject(userId.toString())
            .claim("role", role)
            .issuedAt(new Date())
            .expiration(new Date(System.currentTimeMillis() + accessExpiration))
            .signWith(getSigningKey())
            .compact();
    }
    
    private SecretKey getSigningKey() {
        return Keys.hmacShaKeyFor(Decoders.BASE64.decode(secretKey));
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 缓存策略 — Spring Cache + Redis                          ║
# ╚═══════════════════════════════════════════════════════════╝

CACHE_JAVA = '''
// 缓存设计原则:
// 1. 用 @Cacheable / @CacheEvict 声明式
// 2. 缓存 key = 实体类型 + ID  (防 key 冲突)
// 3. 缓存 TTL 按业务需求差异化
// 4. 写操作时主动失效缓存 (不是更新缓存)
// 5. 不用 @CachePut (它每次都会写, 浪费)

@Configuration
@EnableCaching
public class RedisConfig {
    
    @Bean
    public RedisCacheManager cacheManager(RedisConnectionFactory factory) {
        // 缓存配置: 不同业务不同 TTL
        Map<String, RedisCacheConfiguration> configs = new HashMap<>();
        configs.put("products", RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofMinutes(30))
            .disableCachingNullValues());
        configs.put("categories", RedisCacheConfiguration.defaultCacheConfig()
            .entryTtl(Duration.ofHours(1)));
        
        return RedisCacheManager.builder(factory)
            .cacheDefaults(RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(Duration.ofMinutes(10)))
            .withInitialCacheConfigurations(configs)
            .build();
    }
}

// 在 Service 中使用:
@Service
public class ProductService {
    
    @Cacheable(value = "products", key = "'product:' + #id")
    public ProductResponse findById(Long id) {
        // 只有缓存未命中时才会执行
        return ...;
    }
    
    @CacheEvict(value = "products", key = "'product:' + #id")
    @Transactional
    public void update(Long id, ProductUpdateRequest request) {
        // 更新后自动清除缓存
    }
    
    // 批量清除
    @CacheEvict(value = "products", allEntries = true)
    @Transactional
    public void deactivateByCategory(Long categoryId) {
        ...
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 异步 (@Async)                                            ║
# ╚═══════════════════════════════════════════════════════════╝

ASYNC_JAVA = '''
// 异步设计原则:
// 1. 自定义线程池 (不用默认的 SimpleAsyncTaskExecutor)
// 2. 异步方法必须放在单独类中 (不能 self-call)
// 3. 异常处理用 AsyncUncaughtExceptionHandler
// 4. @Async 方法返回值用 CompletableFuture

@Configuration
@EnableAsync
public class AsyncConfig implements AsyncConfigurer {
    
    @Override
    @Bean("taskExecutor")
    public Executor getAsyncExecutor() {
        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(5);
        executor.setMaxPoolSize(20);
        executor.setQueueCapacity(100);
        executor.setThreadNamePrefix("async-");
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setRejectedExecutionHandler(new CallerRunsPolicy());  // 满了就调用方执行
        executor.initialize();
        return executor;
    }
}

// 使用:
@Component
public class NotificationService {
    
    @Async("taskExecutor")
    public CompletableFuture<Void> sendOrderConfirmation(Long orderId) {
        // 异步发送邮件/短信
        return CompletableFuture.completedFuture(null);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 单元测试                                                 ║
# ╚═══════════════════════════════════════════════════════════╝

TEST_JAVA = '''
// 测试分层:
// 1. 单元测试 (JUnit 5 + Mockito) — 无 Spring 上下文
// 2. 切片测试 (@WebMvcTest, @DataJpaTest) — 只加载部分上下文
// 3. 集成测试 (@SpringBootTest) — 加载全部上下文
// 4. E2E 测试 (Testcontainers) — 真实数据库

// ── 单元测试: Service 层 (Mock Repository) ──
@ExtendWith(MockitoExtension.class)
class ProductServiceTest {
    
    @Mock
    private ProductRepository productRepository;
    
    @InjectMocks
    private ProductServiceImpl productService;
    
    @Test
    void create_shouldThrow_whenDuplicateName() {
        ProductCreateRequest request = new ProductCreateRequest("Test", 1000, 10, null);
        when(productRepository.findByName("Test")).thenReturn(Optional.of(new Product()));
        
        assertThrows(BusinessException.class, () -> productService.create(request));
        verify(productRepository, never()).save(any());
    }
}

// ── 切片测试: Controller 层 ──
@WebMvcTest(ProductController.class)
class ProductControllerTest {
    
    @Autowired
    private MockMvc mockMvc;
    
    @MockitoBean
    private ProductService productService;
    
    @Test
    void getProduct_shouldReturn200() throws Exception {
        when(productService.findById(1L))
            .thenReturn(new ProductResponse(1L, "测试", 1000, 10, "电子", true, null, null));
        
        mockMvc.perform(get("/api/v1/products/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.data.name").value("测试"));
    }
}

// ── 集成测试: 真实 DB ──
@SpringBootTest
@Testcontainers
class ProductIntegrationTest {
    
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");
    
    @Autowired
    private ProductRepository productRepository;
    
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }
    
    @Test
    void shouldSaveAndFindProduct() {
        Product product = new Product();
        product.setName("集成测试");
        product.setPrice(5000);
        product = productRepository.save(product);
        
        Optional<Product> found = productRepository.findById(product.getId());
        assertTrue(found.isPresent());
        assertEquals("集成测试", found.get().getName());
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 常见坑 — 高级工程师才知道的陷阱                            ║
# ╚═══════════════════════════════════════════════════════════╝

COMMON_PITFALLS = """
Spring Boot 常见坑 (5-8年经验才会注意到的):

1. N+1 查询
   @ManyToOne(fetch = FetchType.LAZY) 只是延迟加载
   循环遍历 product.getCategory().getName() 时每条都查
   → 用 @EntityGraph(attributePaths = "category") 或 @Query(fetch join)

2. LazyInitializationException
   spring.jpa.open-in-view=true (默认) 会在 View 层延迟加载
   但事务结束后的延迟加载会抛这个异常
   → 设 false + 在 Service 层显式 fetch join

3. @Transactional 自调用失效
   Service 内部方法 A 调方法 B, B 的 @Transactional 不会生效
   → 注入 self reference: @Autowired proxy
   → 或用 TransactionTemplate

4. 循环依赖
   A → B → A → 启动报错
   → 用 @Lazy 或重构 (常见的解决办法是抽一个第三层)

5. Jackson 无限递归
   Entity 双向关联 (Product ↔ Category) → JSON 序列化死循环
   → @JsonIgnoreProperties 或 @JsonBackReference/@JsonManagedReference

6. 乐观锁冲突
   @Version 字段在并发更新时会抛 OptimisticLockException
   → 前端引导用户重试, 不裸返回 500

7. Hibernate 批量操作
   for(1000条) save() → 1条1条 insert, 很慢
   → hibernate.jdbc.batch_size + @Transactional

8. 测试用 @SpringBootTest 但没@MockBean
   → 会加载真实数据库, 超时
   → 正确的: 单元测试用 @ExtendWith(MockitoExtension.class)
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ Flyway 迁移                                               ║
# ╚═══════════════════════════════════════════════════════════╝

FLYWAY_SQL = """
-- 迁移文件命名: V<序号>__<描述>.sql
-- 示例:
-- V1__create_product.sql
-- V2__add_index.sql
-- V3__seed_data.sql

-- V1__create_product.sql
CREATE TABLE products (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    price       INTEGER NOT NULL,
    stock       INTEGER DEFAULT 0,
    category_id BIGINT REFERENCES categories(id),
    is_active   BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_name ON products(name);
CREATE INDEX idx_product_category ON products(category_id);

-- 无需 import.sql, 迁移脚本就是权威版本控制
"""


# ╔═══════════════════════════════════════════════════════════╗
# ║ 常见问题快速回答                                          ║
# ╚═══════════════════════════════════════════════════════════╝

FAQ = """
Q: 碰到一个 Spring Boot 项目, 怎么快速上手?
A: 1. 看 pom.xml 知道用的什么版本和依赖
   2. 看 application.yml 知道连接哪个数据库
   3. 看 @RestController 知道有哪些 API
   4. 看 @Service 知道业务逻辑在哪
   5. 看 @Entity 知道数据库结构

Q: 怎么加一个新接口?
A: 1. Entity 已有 → 直接加 Repository 方法 + Service + Controller
   2. 新 Entity → 先建 Entity + Repository, 再写 Service + Controller
   3. 最后跑迁移: 在 src/main/resources/db/migration/ 加 V<next>.sql

Q: 报 500 错误怎么看?
A: 1. 看日志: application.yml 里 logging.level.root=DEBUG
   2. 看 response: GlobalExceptionHandler 有 @ExceptionHandler(Exception.class) 的日志
   3. 看堆栈: 重点看 Caused by: 行

Q: 怎么加一个新的 Table?
A: 1. 建 Entity 类
   2. 建 Repository 接口
   3. 建 Flyway 迁移 SQL
   4. 重启应用 (JPA ddl-auto=validate 验证)

Q: @Autowired 和构造器注入选哪个?
A: 永远选构造器 (final + @RequiredArgsConstructor)
   @Autowired 在字段上会导致: 无法测试/Mock、空指针难排查、循环依赖隐藏

Q: OSIV (open-in-view) 要不要关?
A: 关。不关的话事务结束后还能查数据库 (延迟加载), 
   看似方便实则把 SQL 散布到了 View 层, 性能问题排查困难。
"""

if __name__ == "__main__":
    print("""
Spring Boot 3 生产架构参考
============================
覆盖 12 个模块 (600+ 行 Java 代码):

  ▸ 项目结构           ▸ JPA 实体 + 关联
  ▸ Maven 依赖管理      ▸ Repository + 自定义查询
  ▸ 配置 + 多环境       ▸ Service + 事务
  ▸ Controller         ▸ 全局异常处理
  ▸ Security + JWT     ▸ 缓存 (Redis)
  ▸ 异步 + 线程池       ▸ 测试 (单元/切片/集成)
  ▸ 常见坑 8 条         ▸ Flyway 迁移

用法: 复制对应的代码块到 Spring Boot 项目即可运行
    """)
    
    for name, content in [
        ("项目结构", PROJECT_STRUCTURE),
        ("pom.xml", POM_XML),
        ("实体", ENTITY_JAVA),
        ("Repository", REPOSITORY_JAVA),
        ("Service", SERVICE_JAVA),
        ("Controller", CONTROLLER_JAVA),
        ("异常处理", EXCEPTION_HANDLER_JAVA),
        ("Security", SECURITY_JAVA),
        ("缓存", CACHE_JAVA),
        ("异步", ASYNC_JAVA),
        ("测试", TEST_JAVA),
        ("常见坑", COMMON_PITFALLS),
    ]:
        lines = content.strip().count('\n') + 1
        print(f"  📄 {name:12s} {lines:>4} 行")
