"""FastAPI application initialization"""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pathlib import Path

import os
import httpx
from .core.config import config
from .core.database import Database
from .services.flow_client import FlowClient
from .services.proxy_manager import ProxyManager
from .services.token_manager import TokenManager
from .services.load_balancer import LoadBalancer
from .services.concurrency_manager import ConcurrencyManager
from .services.generation_handler import GenerationHandler
from .api import routes, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("=" * 60)
    print("Flow2API Starting...")
    print("=" * 60)

    # Get config from setting.toml
    config_dict = config.get_raw_config()

    # Check if database exists (determine if first startup)
    is_first_startup = not db.db_exists()

    # Initialize database tables structure
    await db.init_db()

    # Connect debug logger to database for persistent logging
    from .core.logger import set_db_instance
    set_db_instance(db)

    # For PostgreSQL, first-startup detection happens during init_db
    if hasattr(db, '_was_first_startup'):
        is_first_startup = db._was_first_startup

    # Handle database initialization based on startup type
    if is_first_startup:
        print("🎉 First startup detected. Initializing database and configuration from setting.toml...")
        await db.init_config_from_toml(config_dict, is_first_startup=True)
        print("✓ Database and configuration initialized successfully.")
    else:
        print("🔄 Existing database detected. Checking for missing tables and columns...")
        await db.check_and_migrate_db(config_dict)
        print("✓ Database migration check completed.")

    # Load admin config from database
    admin_config = await db.get_admin_config()
    if admin_config:
        config.set_admin_username_from_db(admin_config.username)
        config.set_admin_password_from_db(admin_config.password)
        config.api_key = admin_config.api_key

    # Load cache configuration from database
    cache_config = await db.get_cache_config()
    config.set_cache_enabled(cache_config.cache_enabled)
    config.set_cache_timeout(cache_config.cache_timeout)
    config.set_cache_base_url(cache_config.cache_base_url or "")

    # Load generation configuration from database
    generation_config = await db.get_generation_config()
    config.set_image_timeout(generation_config.image_timeout)
    config.set_video_timeout(generation_config.video_timeout)

    # Load debug configuration from database
    debug_config = await db.get_debug_config()
    config.set_debug_enabled(debug_config.enabled)

    # Load captcha configuration from database
    captcha_config = await db.get_captcha_config()
    
    config.set_captcha_method(captcha_config.captcha_method)
    config.set_yescaptcha_api_key(captcha_config.yescaptcha_api_key)
    config.set_yescaptcha_base_url(captcha_config.yescaptcha_base_url)
    config.set_capmonster_api_key(captcha_config.capmonster_api_key)
    config.set_capmonster_base_url(captcha_config.capmonster_base_url)
    config.set_ezcaptcha_api_key(captcha_config.ezcaptcha_api_key)
    config.set_ezcaptcha_base_url(captcha_config.ezcaptcha_base_url)
    config.set_capsolver_api_key(captcha_config.capsolver_api_key)
    config.set_capsolver_base_url(captcha_config.capsolver_base_url)

    # Initialize browser captcha service if needed (non-blocking to avoid deployment timeout)
    browser_service = None
    browser_init_task = None
    import asyncio

    if captcha_config.captcha_method in ("personal", "browser"):
        async def _init_browser_captcha():
            nonlocal browser_service
            try:
                if captcha_config.captcha_method == "personal":
                    from .services.browser_captcha_personal import BrowserCaptchaService
                    browser_service = await BrowserCaptchaService.get_instance(db)
                    print("✓ Browser captcha service initialized (nodriver mode)")

                    tokens_list = await token_manager.get_all_tokens()
                    resident_project_id = None
                    for t in tokens_list:
                        if t.current_project_id and t.is_active:
                            resident_project_id = t.current_project_id
                            break

                    if resident_project_id:
                        await browser_service.start_resident_mode(resident_project_id)
                        print(f"✓ Browser captcha resident mode started (project: {resident_project_id[:8]}...)")
                    else:
                        await browser_service.open_login_window()
                        print("⚠ No active token with project_id found, opened login window for manual setup")
                elif captcha_config.captcha_method == "browser":
                    from .services.browser_captcha import BrowserCaptchaService
                    browser_service = await BrowserCaptchaService.get_instance(db)
                    print("✓ Browser captcha service initialized (headless mode)")
            except Exception as e:
                print(f"⚠ Browser captcha initialization error (will retry on demand): {e}")

        browser_init_task = asyncio.create_task(_init_browser_captcha())

    # Initialize concurrency manager
    tokens = await token_manager.get_all_tokens()

    await concurrency_manager.initialize(tokens)

    # Start file cache cleanup task
    await generation_handler.file_cache.start_cleanup_task()

    # Start 429 auto-unban task
    async def auto_unban_task():
        """定时任务：每小时检查并解禁429被禁用的token"""
        while True:
            try:
                await asyncio.sleep(3600)  # 每小时执行一次
                await token_manager.auto_unban_429_tokens()
            except Exception as e:
                print(f"❌ Auto-unban task error: {e}")

    auto_unban_task_handle = asyncio.create_task(auto_unban_task())

    print(f"✓ Database initialized")
    print(f"✓ Total tokens: {len(tokens)}")
    print(f"✓ Cache: {'Enabled' if config.cache_enabled else 'Disabled'} (timeout: {config.cache_timeout}s)")
    print(f"✓ Captcha Method: {config.captcha_method}")
    print(f"✓ Debug Mode: {'Enabled' if config.debug_enabled else 'Disabled'}")
    print(f"✓ File cache cleanup task started")
    print(f"✓ 429 auto-unban task started (runs every hour)")
    print(f"✓ Server running on http://{config.server_host}:{config.server_port}")
    print("=" * 60)

    yield

    # Shutdown
    print("Flow2API Shutting down...")
    # Stop file cache cleanup task
    await generation_handler.file_cache.stop_cleanup_task()
    # Stop auto-unban task
    auto_unban_task_handle.cancel()
    try:
        await auto_unban_task_handle
    except asyncio.CancelledError:
        pass
    # Wait for browser init and close if initialized
    if browser_init_task is not None:
        if not browser_init_task.done():
            browser_init_task.cancel()
            try:
                await browser_init_task
            except asyncio.CancelledError:
                pass
        if browser_service:
            await browser_service.close()
            print("✓ Browser captcha service closed")
    print("✓ File cache cleanup task stopped")
    print("✓ 429 auto-unban task stopped")


# Initialize components - auto-detect PostgreSQL or SQLite
if os.environ.get("DATABASE_URL"):
    from .core.database_pg import PostgresDatabase
    db = PostgresDatabase()
    print("📦 Using PostgreSQL database")
else:
    db = Database()
    print("📦 Using SQLite database")
proxy_manager = ProxyManager(db)
flow_client = FlowClient(proxy_manager, db)
token_manager = TokenManager(db, flow_client)
concurrency_manager = ConcurrencyManager()
load_balancer = LoadBalancer(token_manager, concurrency_manager)
generation_handler = GenerationHandler(
    flow_client,
    token_manager,
    load_balancer,
    db,
    concurrency_manager,
    proxy_manager  # 添加 proxy_manager 参数
)

# Set dependencies
routes.set_generation_handler(generation_handler)
admin.set_dependencies(token_manager, proxy_manager, db)

# Create FastAPI app
app = FastAPI(
    title="Flow2API",
    description="OpenAI-compatible API for Google VideoFX (Veo)",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(routes.router)
app.include_router(admin.router)

@app.get("/ip.txt")
async def get_ip_details(request: Request):
    # Get client IP from headers or request
    client_ip = request.headers.get("x-forwarded-for")
    if client_ip:
        client_ip = client_ip.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    try:
        async with httpx.AsyncClient() as client:
            # We fetch info about the Replit server's own IP to get details like Country/State
            response = await client.get("https://ipapi.co/json/", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                details = [
                    f"IP: {data.get('ip')}",
                    f"Country: {data.get('country_name')}",
                    f"Region/State: {data.get('region')}",
                    f"City: {data.get('city')}",
                    f"Org: {data.get('org')}",
                    f"ASN: {data.get('asn')}"
                ]
                return PlainTextResponse("\n".join(details))
    except Exception as e:
        return PlainTextResponse(f"Error: {str(e)}")
    
    return PlainTextResponse(f"IP: {client_ip}\nDetails: Information unavailable")


# Static files - serve tmp directory for cached files
tmp_dir = Path(__file__).parent.parent / "tmp"
tmp_dir.mkdir(exist_ok=True)
app.mount("/tmp", StaticFiles(directory=str(tmp_dir)), name="tmp")

# HTML routes for frontend
static_path = Path(__file__).parent.parent / "static"


@app.get("/", response_class=HTMLResponse)
async def index():
    """Redirect to login page"""
    login_file = static_path / "login.html"
    if login_file.exists():
        return FileResponse(str(login_file))
    return HTMLResponse(content="<h1>Flow2API</h1><p>Frontend not found</p>", status_code=404)


@app.get("/login", response_class=HTMLResponse)
async def login_page():
    """Login page"""
    login_file = static_path / "login.html"
    if login_file.exists():
        return FileResponse(str(login_file))
    return HTMLResponse(content="<h1>Login Page Not Found</h1>", status_code=404)


@app.get("/manage", response_class=HTMLResponse)
async def manage_page():
    """Management console page"""
    manage_file = static_path / "manage.html"
    if manage_file.exists():
        return FileResponse(str(manage_file))
    return HTMLResponse(content="<h1>Management Page Not Found</h1>", status_code=404)
