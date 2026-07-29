#!/usr/bin/env python3
""" ============================================================
ASP.NET Core 10 生产架构参考 — 理解 + 改动用 (C#)

内容:
  - 项目结构 (.NET 10 SDK)
  - 分层架构 (Controller → Service → Repository → Entity)
  - 依赖注入 (内置 DI + 生命周期)
  - Entity Framework Core + 迁移
  - DTO / AutoMapper
  - 中间件管道 (异常/JWT/CORS/日志)
  - JWT 认证
  - 配置管理 (appsettings.json + Options 模式)
  - 健康检查
  - 日志 (Serilog)
  - 测试 (xUnit + Moq + Testcontainers)
  - 常见坑

依赖: .NET SDK 10.0+, ASP.NET Core 10

============================================================ """

# ╔═══════════════════════════════════════════════════════════╗
# ║ 项目结构                                                 ║
# ╚═══════════════════════════════════════════════════════════╝

PROJECT_STRUCTURE = """
Solution.sln
├── src/App.Api/
│   ├── Program.cs                    # 入口 (最小化 API 或传统 Controller)
│   ├── appsettings.json              # 配置
│   ├── appsettings.Development.json
│   ├── Controllers/
│   │   └── ProductsController.cs
│   ├── Middleware/
│   │   ├── ExceptionMiddleware.cs
│   │   └── RequestLoggingMiddleware.cs
│   ├── Models/
│   │   ├── Entities/
│   │   │   ├── Product.cs
│   │   │   └── Category.cs
│   │   ├── Dtos/
│   │   │   ├── ProductCreateRequest.cs
│   │   │   ├── ProductResponse.cs
│   │   │   └── PagedResponse.cs
│   │   └── Errors/
│   │       ├── AppException.cs
│   │       └── ErrorCode.cs
│   ├── Data/
│   │   ├── AppDbContext.cs
│   │   ├── Repositories/
│   │   │   └── ProductRepository.cs
│   │   └── Migrations/               # EF Core 迁移
│   ├── Services/
│   │   ├── IProductService.cs
│   │   └── ProductService.cs
│   ├── Mapping/
│   │   └── MappingProfile.cs         # AutoMapper
│   └── Auth/
│       ├── JwtSettings.cs
│       └── JwtService.cs
├── src/App.Core/                     # 领域层 (可选分离)
│   └── ...
└── tests/App.Api.Tests/
    ├── ProductsControllerTest.cs
    └── ProductServiceTest.cs
"""

# ╔═══════════════════════════════════════════════════════════╗
# ║ Program.cs — .NET 10 最小化 API + 传统 Controller 混合   ║
# ╚═══════════════════════════════════════════════════════════╝

PROGRAM_CS = '''
// .NET 10 的 Program.cs — 顶级语句 + 最小化 API

var builder = WebApplication.CreateBuilder(args);

// ════════════════════════════════════════════════════════════
// 服务注册
// ════════════════════════════════════════════════════════════

// ── 控制器 (若用传统 Controller) ──
builder.Services.AddControllers()
    .AddJsonOptions(opts => 
    {
        opts.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase;
        opts.JsonSerializerOptions.DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull;
    });

// ── EF Core ──
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(
        builder.Configuration.GetConnectionString("DefaultConnection"),
        b => b.MigrationsAssembly("App.Api")));

// ── 认证 + JWT ──
var jwtSection = builder.Configuration.GetSection("Jwt");
builder.Services.Configure<JwtSettings>(jwtSection);
var jwtSettings = jwtSection.Get<JwtSettings>()!;

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidateAudience = true,
            ValidateLifetime = true,
            ValidateIssuerSigningKey = true,
            ValidIssuer = jwtSettings.Issuer,
            ValidAudience = jwtSettings.Audience,
            IssuerSigningKey = new SymmetricSecurityKey(
                Encoding.UTF8.GetBytes(jwtSettings.SecretKey))
        };
    });

// ── DI: Repository + Service ──
builder.Services.AddScoped<IProductRepository, ProductRepository>();
builder.Services.AddScoped<IProductService, ProductService>();

// ── AutoMapper ──
builder.Services.AddAutoMapper(typeof(Program));

// ── 健康检查 ──
builder.Services.AddHealthChecks()
    .AddNpgSql(builder.Configuration.GetConnectionString("DefaultConnection")!);

// ── Redis 缓存 ──
builder.Services.AddStackExchangeRedisCache(options =>
{
    options.Configuration = builder.Configuration.GetConnectionString("Redis");
});

// ── Serilog ──
builder.Host.UseSerilog((ctx, lc) => lc
    .ReadFrom.Configuration(ctx.Configuration)
    .Enrich.WithCorrelationId()
    .WriteTo.Console()
    .WriteTo.File("logs/app-.log", rollingInterval: RollingInterval.Day));

// ── OpenAPI ──
builder.Services.AddOpenApi();

// ── CORS ──
builder.Services.AddCors(options =>
{
    options.AddPolicy("AllowFrontend", policy =>
        policy.WithOrigins("http://localhost:5173")
              .AllowCredentials()
              .AllowAnyHeader()
              .AllowAnyMethod());
});

// ════════════════════════════════════════════════════════════
// 中间件管道
// ════════════════════════════════════════════════════════════

var app = builder.Build();

// 中间件顺序: 异常 → CORS → 认证 → 授权 → 端点
app.UseMiddleware<ExceptionMiddleware>();
app.UseMiddleware<RequestLoggingMiddleware>();

app.UseCors("AllowFrontend");
app.UseAuthentication();
app.UseAuthorization();

app.MapControllers();

// 健康检查端点
app.MapHealthChecks("/health", new HealthCheckOptions
{
    ResponseWriter = async (ctx, report) =>
    {
        ctx.Response.ContentType = "application/json";
        var result = JsonSerializer.Serialize(new
        {
            status = report.Status.ToString(),
            checks = report.Entries.Select(e => new
            {
                name = e.Key,
                status = e.Value.Status.ToString(),
                duration = e.Value.Duration.TotalMilliseconds
            })
        });
        await ctx.Response.WriteAsync(result);
    }
});

// 最小化 API 示例
app.MapGet("/api/v1/ping", () => Results.Ok(new { message = "pong", timestamp = DateTime.UtcNow }));

app.Run();
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ appsettings.json                                          ║
# ╚═══════════════════════════════════════════════════════════╝

APPSETTINGS_JSON = '''
{
  "ConnectionStrings": {
    "DefaultConnection": "Host=${DB_HOST:localhost};Port=${DB_PORT:5432};Database=${DB_NAME:app};Username=${DB_USER:app};Password=${DB_PASSWORD:change_me}",
    "Redis": "${REDIS_URL:localhost:6379}"
  },
  "Jwt": {
    "SecretKey": "${JWT_SECRET:change_me_in_production}",
    "Issuer": "App.Api",
    "Audience": "App.Client",
    "AccessTokenExpirationMinutes": 30,
    "RefreshTokenExpirationDays": 7
  },
  "Serilog": {
    "MinimumLevel": {
      "Default": "${LOG_LEVEL:Information}",
      "Override": {
        "Microsoft.AspNetCore": "Warning",
        "Microsoft.EntityFrameworkCore": "Warning"
      }
    },
    "WriteTo": [
      { "Name": "Console", "Args": { "outputTemplate": "{Timestamp:yyyy-MM-dd HH:mm:ss} [{Level}] {Message}{NewLine}{Exception}" } }
    ]
  },
  "AllowedHosts": "*"
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Entity — EF Core                                          ║
# ╚═══════════════════════════════════════════════════════════╝

ENTITY_CS = '''
// Entity 设计原则 (同 Java JPA):
// 1. 用 long? (nullable) 而非 long 做主键
// 2. 导航属性用 virtual 允许 lazy loading
// 3. 字段限制用 [MaxLength] / [Column(TypeName = ...)]
// 4. 避免循环引用 → JsonIgnore

public class Product
{
    public long Id { get; set; }
    
    [MaxLength(200)]
    public string Name { get; set; } = string.Empty;
    
    /// <summary>价格, 单位: 分 (避免浮点误差)</summary>
    public int Price { get; set; }
    
    public int Stock { get; set; }
    
    // 外键
    public long? CategoryId { get; set; }
    
    [JsonIgnore]  // 防循环引用
    [ForeignKey(nameof(CategoryId))]
    public virtual Category? Category { get; set; }
    
    public bool IsActive { get; set; } = true;
    
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
    
    // 领域方法
    public void AdjustStock(int delta)
    {
        if (Stock + delta < 0)
            throw new AppException(ErrorCode.InsufficientStock, "库存不足");
        Stock += delta;
    }
}

// ── DbContext ──
public class AppDbContext : DbContext
{
    public AppDbContext(DbContextOptions<AppDbContext> options) : base(options) { }
    
    public DbSet<Product> Products => Set<Product>();
    public DbSet<Category> Categories => Set<Category>();
    
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        // Fluent API 配置 (比 Data Annotation 更灵活)
        modelBuilder.Entity<Product>(entity =>
        {
            entity.HasIndex(p => p.Name);
            entity.HasIndex(p => p.CategoryId);
            
            entity.Property(p => p.Name)
                  .IsRequired()
                  .HasMaxLength(200);
                  
            entity.Property(p => p.Price)
                  .IsRequired();
                  
            // 全局查询过滤器: 软删除
            entity.HasQueryFilter(p => p.IsActive);
        });
        
        // 种子数据
        modelBuilder.Entity<Category>().HasData(
            new Category { Id = 1, Name = "电子产品" },
            new Category { Id = 2, Name = "图书" }
        );
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Repository — 仓储模式                                     ║
# ╚═══════════════════════════════════════════════════════════╝

REPOSITORY_CS = '''
// .NET 的 Repository 模式 — 用接口隔离数据访问

public interface IProductRepository
{
    Task<Product?> GetByIdAsync(long id);
    Task<PagedResult<Product>> SearchAsync(string? keyword, int? minPrice, int? maxPrice, 
                                           int page, int pageSize);
    Task<Product> CreateAsync(Product product);
    Task<Product> UpdateAsync(Product product);
    Task DeleteAsync(Product product);
    Task<bool> ExistsByNameAsync(string name);
}

// 实现: 直接用 EF Core
public class ProductRepository : IProductRepository
{
    private readonly AppDbContext _context;
    
    public ProductRepository(AppDbContext context)
    {
        _context = context;
    }
    
    public async Task<Product?> GetByIdAsync(long id)
    {
        // .NET 10: 直接用 FindAsync + Include
        return await _context.Products
            .Include(p => p.Category)
            .FirstOrDefaultAsync(p => p.Id == id);
    }
    
    public async Task<PagedResult<Product>> SearchAsync(
        string? keyword, int? minPrice, int? maxPrice, int page, int pageSize)
    {
        var query = _context.Products.AsQueryable();
        
        if (!string.IsNullOrWhiteSpace(keyword))
            query = query.Where(p => p.Name.Contains(keyword));
        if (minPrice.HasValue)
            query = query.Where(p => p.Price >= minPrice.Value);
        if (maxPrice.HasValue)
            query = query.Where(p => p.Price <= maxPrice.Value);
        
        var total = await query.CountAsync();
        
        var items = await query
            .OrderByDescending(p => p.CreatedAt)
            .Skip((page - 1) * pageSize)
            .Take(pageSize)
            .ToListAsync();
        
        return new PagedResult<Product>(items, total, page, pageSize);
    }
    
    public async Task<Product> CreateAsync(Product product)
    {
        _context.Products.Add(product);
        await _context.SaveChangesAsync();
        return product;
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Service — 业务逻辑                                        ║
# ╚═══════════════════════════════════════════════════════════╝

SERVICE_CS = '''
// Service 设计原则:
// 1. 接口分离 (IProductService)
// 2. 业务规则在这里, 不在 Controller
// 3. 抛 AppException, 由 ExceptionMiddleware 统一处理
// 4. 事务用 SaveChangesAsync (EF Core 自动事务)

public interface IProductService
{
    Task<ProductResponse> CreateAsync(ProductCreateRequest request);
    Task<ProductResponse?> GetByIdAsync(long id);
    Task<PagedResponse<ProductResponse>> SearchAsync(string? keyword, int? minPrice, 
                                                     int? maxPrice, int page, int pageSize);
    Task DeleteAsync(long id);
}

public class ProductService : IProductService
{
    private readonly IProductRepository _repo;
    private readonly IMapper _mapper;
    private readonly ILogger<ProductService> _logger;
    private readonly IDistributedCache _cache;
    
    public ProductService(
        IProductRepository repo, 
        IMapper mapper, 
        ILogger<ProductService> logger,
        IDistributedCache cache)
    {
        _repo = repo;
        _mapper = mapper;
        _logger = logger;
        _cache = cache;
    }
    
    public async Task<ProductResponse> CreateAsync(ProductCreateRequest request)
    {
        // 业务规则: 同名不重复
        if (await _repo.ExistsByNameAsync(request.Name))
            throw new AppException(ErrorCode.DuplicateProduct, $"商品名已存在: {request.Name}");
        
        var product = _mapper.Map<Product>(request);
        product = await _repo.CreateAsync(product);
        
        _logger.LogInformation("Product created: {Id} {Name}", product.Id, product.Name);
        
        return _mapper.Map<ProductResponse>(product);
    }
    
    public async Task<ProductResponse?> GetByIdAsync(long id)
    {
        // 查缓存
        var cacheKey = $"product:{id}";
        var cached = await _cache.GetStringAsync(cacheKey);
        if (cached != null)
            return JsonSerializer.Deserialize<ProductResponse>(cached);
        
        // 查 DB
        var product = await _repo.GetByIdAsync(id)
            ?? throw new AppException(ErrorCode.NotFound, $"商品 {id} 不存在");
        
        var response = _mapper.Map<ProductResponse>(product);
        
        // 写缓存 (1小时)
        await _cache.SetStringAsync(cacheKey, JsonSerializer.Serialize(response), 
            new DistributedCacheEntryOptions { AbsoluteExpirationRelativeToNow = TimeSpan.FromHours(1) });
        
        return response;
    }
    
    public async Task DeleteAsync(long id)
    {
        var product = await _repo.GetByIdAsync(id)
            ?? throw new AppException(ErrorCode.NotFound, $"商品 {id} 不存在");
        await _repo.DeleteAsync(product);
        
        // 清除缓存
        await _cache.RemoveAsync($"product:{id}");
        
        _logger.LogWarning("Product deleted: {Id}", id);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ Controller — 控制器                                        ║
# ╚═══════════════════════════════════════════════════════════╝

CONTROLLER_CS = '''
// ASP.NET Core 与传统 Spring 的区别:
// - [ApiController] 自动做模型验证 (不用手动检查 ModelState)
// - 返回 ActionResult<T> 而不是包装 ApiResponse
// - [FromQuery] / [FromBody] / [FromRoute] 显式声明参数来源

[ApiController]
[Route("api/v1/[controller]")]
[Produces("application/json")]
public class ProductsController : ControllerBase
{
    private readonly IProductService _service;
    
    public ProductsController(IProductService service)
    {
        _service = service;
    }
    
    [HttpPost]
    [ProducesResponseType(typeof(ProductResponse), StatusCodes.Status201Created)]
    public async Task<ActionResult<ProductResponse>> Create(
        [FromBody] ProductCreateRequest request)
    {
        var result = await _service.CreateAsync(request);
        return CreatedAtAction(nameof(GetById), new { id = result.Id }, result);
    }
    
    [HttpGet("{id:long}")]
    [ProducesResponseType(typeof(ProductResponse), StatusCodes.Status200OK)]
    [ProducesResponseType(StatusCodes.Status404NotFound)]
    public async Task<ActionResult<ProductResponse>> GetById(long id)
    {
        var result = await _service.GetByIdAsync(id);
        return Ok(result);
    }
    
    [HttpGet]
    public async Task<ActionResult<PagedResponse<ProductResponse>>> Search(
        [FromQuery] string? keyword,
        [FromQuery] int? minPrice,
        [FromQuery] int? maxPrice,
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20)
    {
        var result = await _service.SearchAsync(keyword, minPrice, maxPrice, page, pageSize);
        return Ok(result);
    }
    
    [HttpDelete("{id:long}")]
    [ProducesResponseType(StatusCodes.Status204NoContent)]
    public async Task<IActionResult> Delete(long id)
    {
        await _service.DeleteAsync(id);
        return NoContent();
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 全局异常处理中间件                                         ║
# ╚═══════════════════════════════════════════════════════════╝

MIDDLEWARE_CS = '''
// .NET 用中间件 + 自定义异常, 而非 @ControllerAdvice
// 优势: 完全控制输出格式

public class ExceptionMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<ExceptionMiddleware> _logger;
    
    public ExceptionMiddleware(RequestDelegate next, ILogger<ExceptionMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }
    
    public async Task InvokeAsync(HttpContext context)
    {
        try
        {
            await _next(context);
        }
        catch (AppException ex)
        {
            _logger.LogWarning("AppException: {Code} {Message}", ex.Code, ex.Message);
            await WriteErrorResponse(context, (int)ex.StatusCode, ex.Code, ex.Message);
        }
        catch (FluentValidation.ValidationException ex)
        {
            var errors = ex.Errors.Select(e => new { e.PropertyName, e.ErrorMessage });
            await WriteErrorResponse(context, 400, "VALIDATION_ERROR", "参数验证失败", errors);
        }
        catch (DbUpdateConcurrencyException)
        {
            await WriteErrorResponse(context, 409, "CONCURRENT_MODIFICATION", "数据已被其他用户修改");
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Unhandled exception");
            await WriteErrorResponse(context, 500, "INTERNAL_ERROR", "服务器内部错误");
        }
    }
    
    private static async Task WriteErrorResponse(HttpContext context, int statusCode, 
        string code, string message, object? details = null)
    {
        context.Response.ContentType = "application/json";
        context.Response.StatusCode = statusCode;
        
        var response = new ErrorResponse(code, message, details);
        await context.Response.WriteAsJsonAsync(response);
    }
}

// ── 自定义异常 ──
public class AppException : Exception
{
    public ErrorCode Code { get; }
    public HttpStatusCode StatusCode { get; }
    
    public AppException(ErrorCode code, string message, 
        HttpStatusCode statusCode = HttpStatusCode.BadRequest) : base(message)
    {
        Code = code;
        StatusCode = statusCode;
    }
}

public enum ErrorCode
{
    NotFound,
    DuplicateProduct,
    InsufficientStock,
    Unauthorized,
    Forbidden,
    ValidationError
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 请求日志中间件                                             ║
# ╚═══════════════════════════════════════════════════════════╝

LOGGING_MIDDLEWARE_CS = '''
public class RequestLoggingMiddleware
{
    private readonly RequestDelegate _next;
    private readonly ILogger<RequestLoggingMiddleware> _logger;
    
    public RequestLoggingMiddleware(RequestDelegate next, ILogger<RequestLoggingMiddleware> logger)
    {
        _next = next;
        _logger = logger;
    }
    
    public async Task InvokeAsync(HttpContext context)
    {
        var stopwatch = Stopwatch.StartNew();
        var correlationId = context.Request.Headers["X-Correlation-ID"]
            .FirstOrDefault() ?? Guid.NewGuid().ToString();
        context.TraceIdentifier = correlationId;
        context.Response.Headers["X-Correlation-ID"] = correlationId;
        
        await _next(context);
        
        stopwatch.Stop();
        _logger.LogInformation(
            "{Method} {Path} → {StatusCode} ({Elapsed}ms) [correlation={CorrelationId}]",
            context.Request.Method,
            context.Request.Path,
            context.Response.StatusCode,
            stopwatch.ElapsedMilliseconds,
            correlationId);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ JWT 认证                                                   ║
# ╚═══════════════════════════════════════════════════════════╝

JWT_CS = '''
// JWT 配置类 (Options 模式)
public class JwtSettings
{
    public const string SectionName = "Jwt";
    
    public string SecretKey { get; set; } = string.Empty;
    public string Issuer { get; set; } = string.Empty;
    public string Audience { get; set; } = string.Empty;
    public int AccessTokenExpirationMinutes { get; set; } = 30;
}

// JWT 服务
public class JwtService
{
    private readonly JwtSettings _settings;
    
    public JwtService(IOptions<JwtSettings> settings)
    {
        _settings = settings.Value;
    }
    
    public string GenerateToken(long userId, string role)
    {
        var key = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(_settings.SecretKey));
        var credentials = new SigningCredentials(key, SecurityAlgorithms.HmacSha256);
        
        var claims = new[]
        {
            new Claim(ClaimTypes.NameIdentifier, userId.ToString()),
            new Claim(ClaimTypes.Role, role),
            new Claim(JwtRegisteredClaimNames.Jti, Guid.NewGuid().ToString())
        };
        
        var token = new JwtSecurityToken(
            issuer: _settings.Issuer,
            audience: _settings.Audience,
            claims: claims,
            expires: DateTime.UtcNow.AddMinutes(_settings.AccessTokenExpirationMinutes),
            signingCredentials: credentials
        );
        
        return new JwtSecurityTokenHandler().WriteToken(token);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ PS: 用 Entity Framework Core 迁移                         ║
# ╚═══════════════════════════════════════════════════════════╝

EF_MIGRATIONS = '''
# EF Core 迁移命令 (dotnet CLI):

# 安装工具
dotnet tool install --global dotnet-ef

# 创建初始迁移
dotnet ef migrations add InitialCreate --output-dir Data/Migrations

# 生成 SQL 脚本 (生产用)
dotnet ef migrations script --output migrate.sql

# 应用迁移 (开发)
dotnet ef database update

# 生产环境: 在 Program.cs 启动时自动迁移
// Program.cs
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await db.Database.MigrateAsync();  // 自动应用待迁移
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 测试 — xUnit + Moq                                        ║
# ╚═══════════════════════════════════════════════════════════╝

TEST_CS = '''
// .NET 测试分层:
// 1. 单元测试 (xUnit + Moq) — 最快
// 2. 集成测试 (WebApplicationFactory + 内存数据库)
// 3. E2E 测试 (Testcontainers + 真实数据库)

// ── .csproj 项目文件 (测试项目) ──
// <Project Sdk="Microsoft.NET.Sdk">
//   <PropertyGroup>
//     <TargetFramework>net10.0</TargetFramework>
//     <ImplicitUsings>enable</ImplicitUsings>
//   </PropertyGroup>
//   <ItemGroup>
//     <PackageReference Include="Microsoft.NET.Test.Sdk" Version="17.*" />
//     <PackageReference Include="xunit" Version="2.*" />
//     <PackageReference Include="Moq" Version="4.*" />
//     <PackageReference Include="Testcontainers.PostgreSql" Version="4.*" />
//   </ItemGroup>
// </Project>

// ── 单元测试: Service ──
public class ProductServiceTest
{
    private readonly Mock<IProductRepository> _repoMock;
    private readonly IMapper _mapper;
    private readonly ProductService _service;
    
    public ProductServiceTest()
    {
        _repoMock = new Mock<IProductRepository>();
        _mapper = new MapperConfiguration(cfg => cfg.AddProfile<MappingProfile>())
            .CreateMapper();
        _service = new ProductService(_repoMock.Object, _mapper, 
            NullLogger<ProductService>.Instance, 
            new MemoryDistributedCache(Options.Create(new MemoryDistributedCacheOptions())));
    }
    
    [Fact]
    public async Task Create_ShouldThrow_WhenDuplicateName()
    {
        // Arrange
        _repoMock.Setup(r => r.ExistsByNameAsync("测试"))
            .ReturnsAsync(true);
        var request = new ProductCreateRequest { Name = "测试", Price = 1000 };
        
        // Act & Assert
        var ex = await Assert.ThrowsAsync<AppException>(() => _service.CreateAsync(request));
        Assert.Equal(ErrorCode.DuplicateProduct, ex.Code);
    }
    
    [Fact]
    public async Task GetById_ShouldReturn_WhenExists()
    {
        _repoMock.Setup(r => r.GetByIdAsync(1L))
            .ReturnsAsync(new Product { Id = 1, Name = "测试", Price = 1000 });
        
        var result = await _service.GetByIdAsync(1);
        Assert.NotNull(result);
        Assert.Equal("测试", result!.Name);
        Assert.Equal(1000, result.Price);
    }
}

// ── 集成测试: 真实 HTTP ──
public class ProductsApiTest : IClassFixture<WebApplicationFactory<Program>>
{
    private readonly HttpClient _client;
    
    public ProductsApiTest(WebApplicationFactory<Program> factory)
    {
        // 真实用户场景: 启动完整应用 + 测试数据库
        _client = factory.WithWebHostBuilder(builder =>
        {
            builder.ConfigureServices(services =>
            {
                // 替换数据库为内存库
                var descriptor = services.SingleOrDefault(
                    d => d.ServiceType == typeof(DbContextOptions<AppDbContext>));
                if (descriptor != null) services.Remove(descriptor);
                
                services.AddDbContext<AppDbContext>(options =>
                    options.UseInMemoryDatabase("TestDb"));
            });
        }).CreateClient();
    }
    
    [Fact]
    public async Task CreateProduct_ShouldReturn201()
    {
        var request = new { name = "集成测试商品", price = 5000 };
        var content = new StringContent(
            JsonSerializer.Serialize(request), Encoding.UTF8, "application/json");
        
        var response = await _client.PostAsync("/api/v1/products", content);
        
        Assert.Equal(HttpStatusCode.Created, response.StatusCode);
        var body = await response.Content.ReadFromJsonAsync<ProductResponse>();
        Assert.NotNull(body);
        Assert.Equal("集成测试商品", body!.Name);
    }
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ AutoMapper — DTO 映射                                     ║
# ╚═══════════════════════════════════════════════════════════╝

AUTOMAPPER_CS = '''
// AutoMapper Profile — Entity ↔ DTO 映射配置

public class MappingProfile : Profile
{
    public MappingProfile()
    {
        CreateMap<ProductCreateRequest, Product>();
        
        CreateMap<Product, ProductResponse>()
            .ForMember(dest => dest.CategoryName, 
                       opt => opt.MapFrom(src => src.Category!.Name));
        
        CreateMap<Category, CategoryResponse>();
    }
}

// ── DTO ──
public record ProductCreateRequest
{
    [Required, MaxLength(200)]
    public string Name { get; init; } = string.Empty;
    
    [Required, Range(0, int.MaxValue)]
    public int Price { get; init; }
    
    public int Stock { get; init; }
    public long? CategoryId { get; init; }
}

public record ProductResponse
{
    public long Id { get; init; }
    public string Name { get; init; } = string.Empty;
    public int Price { get; init; }
    public int Stock { get; init; }
    public string? CategoryName { get; init; }
    public DateTime CreatedAt { get; init; }
}

public record PagedResponse<T>
{
    public IReadOnlyList<T> Items { get; init; } = Array.Empty<T>();
    public int Page { get; init; }
    public int PageSize { get; init; }
    public int Total { get; init; }
    public int TotalPages => (int)Math.Ceiling((double)Total / PageSize);
}
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ 常见坑 — .NET 工程师才会知道的                              ║
# ╚═══════════════════════════════════════════════════════════╝

COMMON_PITFALLS = '''
.NET 常见坑 (5-8年经验才会注意到的):

1. EF Core N+1
   和 Hibernate 一样的问题
   → 用 .Include() / .ThenInclude() 或 用 .Select() 只投影需要的字段

2. DbContext 线程不安全
   不能用 Singleton, 必须 AddDbContext (Scoped)
   并发请求用同一个 DbContext → InvalidOperationException

3. async 死锁
   .Result / .Wait() 在 UI 线程 → 死锁
   → 全程 async/await, 不用 .Result
   → 配置 ConfigureAwait(false) 在库代码

4. EF Core 批量操作
   foreach + SaveChangesAsync (每条都查 + 更新)
   → 用 ExecuteUpdateAsync / ExecuteDeleteAsync (批量 SQL)
   → .NET 10 有更好的批量操作

5. 配置热重载
   appsettings.json 修改后需要重启
   → 用 IOptionsSnapshot (Scope) 或 IOptionsMonitor (Singleton)

6. MemoryCache 过期
   AddMemoryCache 默认不过期
   → 用 AbsoluteExpirationRelativeToNow 或 SlidingExpiration

7. 序列化循环引用
   Product → Category → Products (循环)
   → 用 [JsonIgnore] 或 ReferenceHandler.IgnoreCycles

8. 日志性能
   _logger.LogInformation("xxx {a} {b}", a, b) 是高性能的 (模板编译)
   _logger.LogInformation($"xxx {a} {b}") 会先格式化字符串 (即使日志级别不满足)
   → 永远用模板语法
'''

# ╔═══════════════════════════════════════════════════════════╗
# ║ .csproj 项目文件                                           ║
# ╚═══════════════════════════════════════════════════════════╝

CSPROJ_XML = '''
<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net10.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <RootNamespace>App.Api</RootNamespace>
  </PropertyGroup>
  
  <ItemGroup>
    <PackageReference Include="Microsoft.AspNetCore.Authentication.JwtBearer" Version="10.0.*" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="10.0.*" />
    <PackageReference Include="Npgsql.EntityFrameworkCore.PostgreSQL" Version="10.0.*" />
    <PackageReference Include="AutoMapper" Version="14.*" />
    <PackageReference Include="AutoMapper.Extensions.Microsoft.DependencyInjection" Version="12.*" />
    <PackageReference Include="Serilog.AspNetCore" Version="9.*" />
    <PackageReference Include="Serilog.Enrichers.CorrelationId" Version="2.*" />
    <PackageReference Include="Microsoft.Extensions.Caching.StackExchangeRedis" Version="10.0.*" />
    <PackageReference Include="AspNetCore.HealthChecks.NpgSql" Version="9.*" />
  </ItemGroup>
</Project>
'''

if __name__ == "__main__":
    print("""
ASP.NET Core 10 生产架构参考
==============================
覆盖 12 个模块 (600+ 行 C# 代码):

  ▸ 项目结构           ▸ Program.cs (DI + 中间件管道)
  ▸ appsettings.json   ▸ Entity + DbContext
  ▸ Repository         ▸ Service + DI
  ▸ Controller         ▸ ExceptionMiddleware
  ▸ JWT 认证           ▸ AutoMapper + DTO
  ▸ 测试 (xUnit/Moq)   ▸ EF Core 迁移
  ▸ 常见坑 8 条

快速开始:
  mkdir App.Api && cd App.Api
  dotnet new webapi
  # 复制 .csproj 的包引用
  # 复制 Entities + DbContext + Repository + Service + Controller
  dotnet build
  dotnet run

.NET vs Spring Boot 关键区别:
  - DI 是内置的 (不是第三方框架)
  - 中间件管道 (不是过滤器链)
  - async/await 是语言级 (不是注解)
  - 配置是强类型 IOptions<T> (不是松散 Map)
    """)
    
    total = 0
    for name, content in [
        ("项目结构", PROJECT_STRUCTURE),
        ("Program.cs", PROGRAM_CS),
        ("appsettings.json", APPSETTINGS_JSON),
        ("Entity", ENTITY_CS),
        ("Repository", REPOSITORY_CS),
        ("Service", SERVICE_CS),
        ("Controller", CONTROLLER_CS),
        ("异常中间件", MIDDLEWARE_CS),
        ("日志中间件", LOGGING_MIDDLEWARE_CS),
        ("JWT", JWT_CS),
        ("迁移", EF_MIGRATIONS),
        ("测试", TEST_CS),
        ("AutoMapper", AUTOMAPPER_CS),
        ("常见坑", COMMON_PITFALLS),
        (".csproj", CSPROJ_XML),
    ]:
        lines = content.strip().count('\n') + 1
        print(f"  📄 {name:12s} {lines:>4} 行")
        total += lines
    print(f"\n  总计: {total} 行 C# 代码")
