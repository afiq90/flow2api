"""Database storage layer for Flow2API - PostgreSQL version"""
import asyncpg
import json
import os
from datetime import datetime
from typing import Optional, List
from .models import Token, TokenStats, Task, RequestLog, AdminConfig, ProxyConfig, GenerationConfig, CacheConfig, Project, CaptchaConfig, PluginConfig


class Database:
    """PostgreSQL database manager"""

    def __init__(self):
        self.database_url = os.environ.get("DATABASE_URL")
        self.pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    def db_exists(self) -> bool:
        """Check if database connection is available"""
        return self.database_url is not None

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(self.database_url, min_size=2, max_size=10)
        return self.pool

    async def close(self):
        """Close the connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def _table_exists(self, conn, table_name: str) -> bool:
        """Check if a table exists in the database"""
        result = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
            table_name
        )
        return result

    async def _column_exists(self, conn, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table"""
        try:
            result = await conn.fetchval(
                """SELECT EXISTS(
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = $1 AND column_name = $2
                )""",
                table_name, column_name
            )
            return result
        except:
            return False

    async def _ensure_config_rows(self, conn, config_dict: dict = None):
        """Ensure all config tables have their default rows"""
        count = await conn.fetchval("SELECT COUNT(*) FROM admin_config")
        if count == 0:
            admin_username = "admin"
            admin_password = "admin"
            api_key = "han1234"
            error_ban_threshold = 3

            if config_dict:
                global_config = config_dict.get("global", {})
                admin_username = global_config.get("admin_username", "admin")
                admin_password = global_config.get("admin_password", "admin")
                api_key = global_config.get("api_key", "han1234")
                admin_config = config_dict.get("admin", {})
                error_ban_threshold = admin_config.get("error_ban_threshold", 3)

            await conn.execute("""
                INSERT INTO admin_config (id, username, password, api_key, error_ban_threshold)
                VALUES (1, $1, $2, $3, $4)
            """, admin_username, admin_password, api_key, error_ban_threshold)

        count = await conn.fetchval("SELECT COUNT(*) FROM proxy_config")
        if count == 0:
            proxy_enabled = False
            proxy_url = None

            if config_dict:
                proxy_config = config_dict.get("proxy", {})
                proxy_enabled = proxy_config.get("proxy_enabled", False)
                proxy_url = proxy_config.get("proxy_url", "")
                proxy_url = proxy_url if proxy_url else None

            await conn.execute("""
                INSERT INTO proxy_config (id, enabled, proxy_url)
                VALUES (1, $1, $2)
            """, proxy_enabled, proxy_url)

        count = await conn.fetchval("SELECT COUNT(*) FROM generation_config")
        if count == 0:
            image_timeout = 300
            video_timeout = 1500

            if config_dict:
                generation_config = config_dict.get("generation", {})
                image_timeout = generation_config.get("image_timeout", 300)
                video_timeout = generation_config.get("video_timeout", 1500)

            await conn.execute("""
                INSERT INTO generation_config (id, image_timeout, video_timeout)
                VALUES (1, $1, $2)
            """, image_timeout, video_timeout)

        count = await conn.fetchval("SELECT COUNT(*) FROM cache_config")
        if count == 0:
            cache_enabled = False
            cache_timeout = 7200
            cache_base_url = None

            if config_dict:
                cache_config = config_dict.get("cache", {})
                cache_enabled = cache_config.get("enabled", False)
                cache_timeout = cache_config.get("timeout", 7200)
                cache_base_url = cache_config.get("base_url", "")
                cache_base_url = cache_base_url if cache_base_url else None

            await conn.execute("""
                INSERT INTO cache_config (id, cache_enabled, cache_timeout, cache_base_url)
                VALUES (1, $1, $2, $3)
            """, cache_enabled, cache_timeout, cache_base_url)

        count = await conn.fetchval("SELECT COUNT(*) FROM debug_config")
        if count == 0:
            debug_enabled = False
            log_requests = True
            log_responses = True
            mask_token = True

            if config_dict:
                debug_config = config_dict.get("debug", {})
                debug_enabled = debug_config.get("enabled", False)
                log_requests = debug_config.get("log_requests", True)
                log_responses = debug_config.get("log_responses", True)
                mask_token = debug_config.get("mask_token", True)

            await conn.execute("""
                INSERT INTO debug_config (id, enabled, log_requests, log_responses, mask_token)
                VALUES (1, $1, $2, $3, $4)
            """, debug_enabled, log_requests, log_responses, mask_token)

        count = await conn.fetchval("SELECT COUNT(*) FROM captcha_config")
        if count == 0:
            captcha_method = "browser"
            yescaptcha_api_key = ""
            yescaptcha_base_url = "https://api.yescaptcha.com"

            if config_dict:
                captcha_config = config_dict.get("captcha", {})
                captcha_method = captcha_config.get("captcha_method", "browser")
                yescaptcha_api_key = captcha_config.get("yescaptcha_api_key", "")
                yescaptcha_base_url = captcha_config.get("yescaptcha_base_url", "https://api.yescaptcha.com")

            await conn.execute("""
                INSERT INTO captcha_config (id, captcha_method, yescaptcha_api_key, yescaptcha_base_url)
                VALUES (1, $1, $2, $3)
            """, captcha_method, yescaptcha_api_key, yescaptcha_base_url)

        count = await conn.fetchval("SELECT COUNT(*) FROM plugin_config")
        if count == 0:
            await conn.execute("""
                INSERT INTO plugin_config (id, connection_token)
                VALUES (1, '')
            """)

    async def check_and_migrate_db(self, config_dict: dict = None):
        """Check database integrity and perform migrations if needed"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            print("Checking database integrity and performing migrations...")

            if not await self._table_exists(conn, "cache_config"):
                print("  ✓ Creating missing table: cache_config")
                await conn.execute("""
                    CREATE TABLE cache_config (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        cache_enabled BOOLEAN DEFAULT FALSE,
                        cache_timeout INTEGER DEFAULT 7200,
                        cache_base_url TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)

            if not await self._table_exists(conn, "captcha_config"):
                print("  ✓ Creating missing table: captcha_config")
                await conn.execute("""
                    CREATE TABLE captcha_config (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        captcha_method TEXT DEFAULT 'browser',
                        yescaptcha_api_key TEXT DEFAULT '',
                        yescaptcha_base_url TEXT DEFAULT 'https://api.yescaptcha.com',
                        capmonster_api_key TEXT DEFAULT '',
                        capmonster_base_url TEXT DEFAULT 'https://api.capmonster.cloud',
                        ezcaptcha_api_key TEXT DEFAULT '',
                        ezcaptcha_base_url TEXT DEFAULT 'https://api.ez-captcha.com',
                        capsolver_api_key TEXT DEFAULT '',
                        capsolver_base_url TEXT DEFAULT 'https://api.capsolver.com',
                        website_key TEXT DEFAULT '6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV',
                        page_action TEXT DEFAULT 'FLOW_GENERATION',
                        browser_proxy_enabled BOOLEAN DEFAULT FALSE,
                        browser_proxy_url TEXT,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)

            if not await self._table_exists(conn, "plugin_config"):
                print("  ✓ Creating missing table: plugin_config")
                await conn.execute("""
                    CREATE TABLE plugin_config (
                        id INTEGER PRIMARY KEY DEFAULT 1,
                        connection_token TEXT DEFAULT '',
                        auto_enable_on_update BOOLEAN DEFAULT TRUE,
                        created_at TIMESTAMP DEFAULT NOW(),
                        updated_at TIMESTAMP DEFAULT NOW()
                    )
                """)

            if await self._table_exists(conn, "tokens"):
                columns_to_add = [
                    ("at", "TEXT"),
                    ("at_expires", "TIMESTAMP"),
                    ("credits", "INTEGER DEFAULT 0"),
                    ("user_paygate_tier", "TEXT"),
                    ("current_project_id", "TEXT"),
                    ("current_project_name", "TEXT"),
                    ("image_enabled", "BOOLEAN DEFAULT TRUE"),
                    ("video_enabled", "BOOLEAN DEFAULT TRUE"),
                    ("image_concurrency", "INTEGER DEFAULT -1"),
                    ("video_concurrency", "INTEGER DEFAULT -1"),
                    ("ban_reason", "TEXT"),
                    ("banned_at", "TIMESTAMP"),
                ]

                for col_name, col_type in columns_to_add:
                    if not await self._column_exists(conn, "tokens", col_name):
                        try:
                            await conn.execute(f"ALTER TABLE tokens ADD COLUMN {col_name} {col_type}")
                            print(f"  ✓ Added column '{col_name}' to tokens table")
                        except Exception as e:
                            print(f"  ✗ Failed to add column '{col_name}': {e}")

            if await self._table_exists(conn, "admin_config"):
                if not await self._column_exists(conn, "admin_config", "error_ban_threshold"):
                    try:
                        await conn.execute("ALTER TABLE admin_config ADD COLUMN error_ban_threshold INTEGER DEFAULT 3")
                        print("  ✓ Added column 'error_ban_threshold' to admin_config table")
                    except Exception as e:
                        print(f"  ✗ Failed to add column 'error_ban_threshold': {e}")

            if await self._table_exists(conn, "captcha_config"):
                captcha_columns_to_add = [
                    ("browser_proxy_enabled", "BOOLEAN DEFAULT FALSE"),
                    ("browser_proxy_url", "TEXT"),
                    ("capmonster_api_key", "TEXT DEFAULT ''"),
                    ("capmonster_base_url", "TEXT DEFAULT 'https://api.capmonster.cloud'"),
                    ("ezcaptcha_api_key", "TEXT DEFAULT ''"),
                    ("ezcaptcha_base_url", "TEXT DEFAULT 'https://api.ez-captcha.com'"),
                    ("capsolver_api_key", "TEXT DEFAULT ''"),
                    ("capsolver_base_url", "TEXT DEFAULT 'https://api.capsolver.com'"),
                ]

                for col_name, col_type in captcha_columns_to_add:
                    if not await self._column_exists(conn, "captcha_config", col_name):
                        try:
                            await conn.execute(f"ALTER TABLE captcha_config ADD COLUMN {col_name} {col_type}")
                            print(f"  ✓ Added column '{col_name}' to captcha_config table")
                        except Exception as e:
                            print(f"  ✗ Failed to add column '{col_name}': {e}")

            if await self._table_exists(conn, "token_stats"):
                stats_columns_to_add = [
                    ("today_image_count", "INTEGER DEFAULT 0"),
                    ("today_video_count", "INTEGER DEFAULT 0"),
                    ("today_error_count", "INTEGER DEFAULT 0"),
                    ("today_date", "DATE"),
                    ("consecutive_error_count", "INTEGER DEFAULT 0"),
                ]

                for col_name, col_type in stats_columns_to_add:
                    if not await self._column_exists(conn, "token_stats", col_name):
                        try:
                            await conn.execute(f"ALTER TABLE token_stats ADD COLUMN {col_name} {col_type}")
                            print(f"  ✓ Added column '{col_name}' to token_stats table")
                        except Exception as e:
                            print(f"  ✗ Failed to add column '{col_name}': {e}")

            if await self._table_exists(conn, "plugin_config"):
                if not await self._column_exists(conn, "plugin_config", "auto_enable_on_update"):
                    try:
                        await conn.execute("ALTER TABLE plugin_config ADD COLUMN auto_enable_on_update BOOLEAN DEFAULT TRUE")
                        print("  ✓ Added column 'auto_enable_on_update' to plugin_config table")
                    except Exception as e:
                        print(f"  ✗ Failed to add column 'auto_enable_on_update': {e}")

            await self._ensure_config_rows(conn, config_dict=config_dict)
            print("Database migration check completed.")

    async def init_db(self):
        """Initialize database tables"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tokens (
                    id SERIAL PRIMARY KEY,
                    st TEXT UNIQUE NOT NULL,
                    at TEXT,
                    at_expires TIMESTAMP,
                    email TEXT NOT NULL,
                    name TEXT,
                    remark TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_used_at TIMESTAMP,
                    use_count INTEGER DEFAULT 0,
                    credits INTEGER DEFAULT 0,
                    user_paygate_tier TEXT,
                    current_project_id TEXT,
                    current_project_name TEXT,
                    image_enabled BOOLEAN DEFAULT TRUE,
                    video_enabled BOOLEAN DEFAULT TRUE,
                    image_concurrency INTEGER DEFAULT -1,
                    video_concurrency INTEGER DEFAULT -1,
                    ban_reason TEXT,
                    banned_at TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id SERIAL PRIMARY KEY,
                    project_id TEXT UNIQUE NOT NULL,
                    token_id INTEGER NOT NULL REFERENCES tokens(id),
                    project_name TEXT NOT NULL,
                    tool_name TEXT DEFAULT 'PINHOLE',
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS token_stats (
                    id SERIAL PRIMARY KEY,
                    token_id INTEGER NOT NULL REFERENCES tokens(id),
                    image_count INTEGER DEFAULT 0,
                    video_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    last_success_at TIMESTAMP,
                    last_error_at TIMESTAMP,
                    today_image_count INTEGER DEFAULT 0,
                    today_video_count INTEGER DEFAULT 0,
                    today_error_count INTEGER DEFAULT 0,
                    today_date DATE,
                    consecutive_error_count INTEGER DEFAULT 0
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT UNIQUE NOT NULL,
                    token_id INTEGER NOT NULL REFERENCES tokens(id),
                    model TEXT NOT NULL,
                    prompt TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'processing',
                    progress INTEGER DEFAULT 0,
                    result_urls TEXT,
                    error_message TEXT,
                    scene_id TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    completed_at TIMESTAMP
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS request_logs (
                    id SERIAL PRIMARY KEY,
                    token_id INTEGER REFERENCES tokens(id),
                    operation TEXT NOT NULL,
                    request_body TEXT,
                    response_body TEXT,
                    status_code INTEGER NOT NULL,
                    duration FLOAT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    username TEXT DEFAULT 'admin',
                    password TEXT DEFAULT 'admin',
                    api_key TEXT DEFAULT 'han1234',
                    error_ban_threshold INTEGER DEFAULT 3,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS proxy_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    enabled BOOLEAN DEFAULT FALSE,
                    proxy_url TEXT,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS generation_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    image_timeout INTEGER DEFAULT 300,
                    video_timeout INTEGER DEFAULT 1500,
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS cache_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    cache_enabled BOOLEAN DEFAULT FALSE,
                    cache_timeout INTEGER DEFAULT 7200,
                    cache_base_url TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS debug_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    enabled BOOLEAN DEFAULT FALSE,
                    log_requests BOOLEAN DEFAULT TRUE,
                    log_responses BOOLEAN DEFAULT TRUE,
                    mask_token BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS captcha_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    captcha_method TEXT DEFAULT 'browser',
                    yescaptcha_api_key TEXT DEFAULT '',
                    yescaptcha_base_url TEXT DEFAULT 'https://api.yescaptcha.com',
                    capmonster_api_key TEXT DEFAULT '',
                    capmonster_base_url TEXT DEFAULT 'https://api.capmonster.cloud',
                    ezcaptcha_api_key TEXT DEFAULT '',
                    ezcaptcha_base_url TEXT DEFAULT 'https://api.ez-captcha.com',
                    capsolver_api_key TEXT DEFAULT '',
                    capsolver_base_url TEXT DEFAULT 'https://api.capsolver.com',
                    website_key TEXT DEFAULT '6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV',
                    page_action TEXT DEFAULT 'FLOW_GENERATION',
                    browser_proxy_enabled BOOLEAN DEFAULT FALSE,
                    browser_proxy_url TEXT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("""
                CREATE TABLE IF NOT EXISTS plugin_config (
                    id INTEGER PRIMARY KEY DEFAULT 1,
                    connection_token TEXT DEFAULT '',
                    auto_enable_on_update BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """)

            await conn.execute("CREATE INDEX IF NOT EXISTS idx_task_id ON tasks(task_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_token_st ON tokens(st)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_project_id ON projects(project_id)")

        self._initialized = True

    async def add_token(self, token: Token) -> int:
        """Add a new token"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            token_id = await conn.fetchval("""
                INSERT INTO tokens (st, at, at_expires, email, name, remark, is_active,
                                   credits, user_paygate_tier, current_project_id, current_project_name,
                                   image_enabled, video_enabled, image_concurrency, video_concurrency)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id
            """, token.st, token.at, token.at_expires, token.email, token.name, token.remark,
                  token.is_active, token.credits, token.user_paygate_tier,
                  token.current_project_id, token.current_project_name,
                  token.image_enabled, token.video_enabled,
                  token.image_concurrency, token.video_concurrency)

            await conn.execute("""
                INSERT INTO token_stats (token_id) VALUES ($1)
            """, token_id)

            return token_id

    async def get_token(self, token_id: int) -> Optional[Token]:
        """Get token by ID"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tokens WHERE id = $1", token_id)
            if row:
                return Token(**dict(row))
            return None

    async def get_token_by_st(self, st: str) -> Optional[Token]:
        """Get token by ST"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tokens WHERE st = $1", st)
            if row:
                return Token(**dict(row))
            return None

    async def get_token_by_email(self, email: str) -> Optional[Token]:
        """Get token by email"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tokens WHERE email = $1", email)
            if row:
                return Token(**dict(row))
            return None

    async def get_all_tokens(self) -> List[Token]:
        """Get all tokens"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM tokens ORDER BY created_at DESC")
            return [Token(**dict(row)) for row in rows]

    async def get_active_tokens(self) -> List[Token]:
        """Get all active tokens"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM tokens WHERE is_active = TRUE ORDER BY last_used_at ASC NULLS FIRST")
            return [Token(**dict(row)) for row in rows]

    async def update_token(self, token_id: int, **kwargs):
        """Update token fields"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            updates = []
            params = []
            param_idx = 1

            for key, value in kwargs.items():
                if value is not None:
                    updates.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1

            if updates:
                params.append(token_id)
                query = f"UPDATE tokens SET {', '.join(updates)} WHERE id = ${param_idx}"
                await conn.execute(query, *params)

    async def delete_token(self, token_id: int):
        """Delete token and related data"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM token_stats WHERE token_id = $1", token_id)
            await conn.execute("DELETE FROM projects WHERE token_id = $1", token_id)
            await conn.execute("DELETE FROM tokens WHERE id = $1", token_id)

    async def add_project(self, project: Project) -> int:
        """Add a new project"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            project_id = await conn.fetchval("""
                INSERT INTO projects (project_id, token_id, project_name, tool_name, is_active)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, project.project_id, project.token_id, project.project_name,
                  project.tool_name, project.is_active)
            return project_id

    async def get_project_by_id(self, project_id: str) -> Optional[Project]:
        """Get project by UUID"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM projects WHERE project_id = $1", project_id)
            if row:
                return Project(**dict(row))
            return None

    async def get_projects_by_token(self, token_id: int) -> List[Project]:
        """Get all projects for a token"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM projects WHERE token_id = $1 ORDER BY created_at DESC",
                token_id
            )
            return [Project(**dict(row)) for row in rows]

    async def delete_project(self, project_id: str):
        """Delete project"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM projects WHERE project_id = $1", project_id)

    async def create_task(self, task: Task) -> int:
        """Create a new task"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            task_id = await conn.fetchval("""
                INSERT INTO tasks (task_id, token_id, model, prompt, status, progress, scene_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id
            """, task.task_id, task.token_id, task.model, task.prompt,
                  task.status, task.progress, task.scene_id)
            return task_id

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tasks WHERE task_id = $1", task_id)
            if row:
                task_dict = dict(row)
                if task_dict.get("result_urls"):
                    task_dict["result_urls"] = json.loads(task_dict["result_urls"])
                return Task(**task_dict)
            return None

    async def update_task(self, task_id: str, **kwargs):
        """Update task"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            updates = []
            params = []
            param_idx = 1

            for key, value in kwargs.items():
                if value is not None:
                    if key == "result_urls" and isinstance(value, list):
                        value = json.dumps(value)
                    updates.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1

            if updates:
                params.append(task_id)
                query = f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ${param_idx}"
                await conn.execute(query, *params)

    async def increment_token_stats(self, token_id: int, stat_type: str):
        """Increment token statistics"""
        if stat_type == "image":
            await self.increment_image_count(token_id)
        elif stat_type == "video":
            await self.increment_video_count(token_id)
        elif stat_type == "error":
            await self.increment_error_count(token_id)

    async def get_token_stats(self, token_id: int) -> Optional[TokenStats]:
        """Get token statistics"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM token_stats WHERE token_id = $1", token_id)
            if row:
                return TokenStats(**dict(row))
            return None

    async def increment_image_count(self, token_id: int):
        """Increment image generation count with daily reset"""
        from datetime import date
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            today = date.today()
            row = await conn.fetchrow("SELECT today_date FROM token_stats WHERE token_id = $1", token_id)

            if row and row['today_date'] != today:
                await conn.execute("""
                    UPDATE token_stats
                    SET image_count = image_count + 1,
                        today_image_count = 1,
                        today_date = $1
                    WHERE token_id = $2
                """, today, token_id)
            else:
                await conn.execute("""
                    UPDATE token_stats
                    SET image_count = image_count + 1,
                        today_image_count = today_image_count + 1,
                        today_date = $1
                    WHERE token_id = $2
                """, today, token_id)

    async def increment_video_count(self, token_id: int):
        """Increment video generation count with daily reset"""
        from datetime import date
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            today = date.today()
            row = await conn.fetchrow("SELECT today_date FROM token_stats WHERE token_id = $1", token_id)

            if row and row['today_date'] != today:
                await conn.execute("""
                    UPDATE token_stats
                    SET video_count = video_count + 1,
                        today_video_count = 1,
                        today_date = $1
                    WHERE token_id = $2
                """, today, token_id)
            else:
                await conn.execute("""
                    UPDATE token_stats
                    SET video_count = video_count + 1,
                        today_video_count = today_video_count + 1,
                        today_date = $1
                    WHERE token_id = $2
                """, today, token_id)

    async def increment_error_count(self, token_id: int):
        """Increment error count with daily reset"""
        from datetime import date
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            today = date.today()
            row = await conn.fetchrow("SELECT today_date FROM token_stats WHERE token_id = $1", token_id)

            if row and row['today_date'] != today:
                await conn.execute("""
                    UPDATE token_stats
                    SET error_count = error_count + 1,
                        consecutive_error_count = consecutive_error_count + 1,
                        today_error_count = 1,
                        today_date = $1,
                        last_error_at = NOW()
                    WHERE token_id = $2
                """, today, token_id)
            else:
                await conn.execute("""
                    UPDATE token_stats
                    SET error_count = error_count + 1,
                        consecutive_error_count = consecutive_error_count + 1,
                        today_error_count = today_error_count + 1,
                        today_date = $1,
                        last_error_at = NOW()
                    WHERE token_id = $2
                """, today, token_id)

    async def reset_error_count(self, token_id: int):
        """Reset consecutive error count"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE token_stats SET consecutive_error_count = 0 WHERE token_id = $1
            """, token_id)

    async def get_admin_config(self) -> Optional[AdminConfig]:
        """Get admin configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM admin_config WHERE id = 1")
            if row:
                return AdminConfig(**dict(row))
            return None

    async def update_admin_config(self, **kwargs):
        """Update admin configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            updates = []
            params = []
            param_idx = 1

            for key, value in kwargs.items():
                if value is not None:
                    updates.append(f"{key} = ${param_idx}")
                    params.append(value)
                    param_idx += 1

            if updates:
                updates.append("updated_at = NOW()")
                query = f"UPDATE admin_config SET {', '.join(updates)} WHERE id = 1"
                await conn.execute(query, *params)

    async def get_proxy_config(self) -> Optional[ProxyConfig]:
        """Get proxy configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM proxy_config WHERE id = 1")
            if row:
                return ProxyConfig(**dict(row))
            return None

    async def update_proxy_config(self, enabled: bool, proxy_url: Optional[str] = None):
        """Update proxy configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE proxy_config
                SET enabled = $1, proxy_url = $2, updated_at = NOW()
                WHERE id = 1
            """, enabled, proxy_url)

    async def get_generation_config(self) -> Optional[GenerationConfig]:
        """Get generation configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM generation_config WHERE id = 1")
            if row:
                return GenerationConfig(**dict(row))
            return None

    async def update_generation_config(self, image_timeout: int, video_timeout: int):
        """Update generation configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE generation_config
                SET image_timeout = $1, video_timeout = $2, updated_at = NOW()
                WHERE id = 1
            """, image_timeout, video_timeout)

    async def add_request_log(self, log: RequestLog):
        """Add request log"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO request_logs (token_id, operation, request_body, response_body, status_code, duration)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, log.token_id, log.operation, log.request_body, log.response_body,
                  log.status_code, log.duration)

    async def get_logs(self, limit: int = 100, token_id: Optional[int] = None):
        """Get request logs with token email"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            if token_id:
                rows = await conn.fetch("""
                    SELECT
                        rl.id,
                        rl.token_id,
                        rl.operation,
                        rl.request_body,
                        rl.response_body,
                        rl.status_code,
                        rl.duration,
                        rl.created_at,
                        t.email as token_email,
                        t.name as token_username
                    FROM request_logs rl
                    LEFT JOIN tokens t ON rl.token_id = t.id
                    WHERE rl.token_id = $1
                    ORDER BY rl.created_at DESC
                    LIMIT $2
                """, token_id, limit)
            else:
                rows = await conn.fetch("""
                    SELECT
                        rl.id,
                        rl.token_id,
                        rl.operation,
                        rl.request_body,
                        rl.response_body,
                        rl.status_code,
                        rl.duration,
                        rl.created_at,
                        t.email as token_email,
                        t.name as token_username
                    FROM request_logs rl
                    LEFT JOIN tokens t ON rl.token_id = t.id
                    ORDER BY rl.created_at DESC
                    LIMIT $1
                """, limit)

            return [dict(row) for row in rows]

    async def clear_all_logs(self):
        """Clear all request logs"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM request_logs")

    async def init_config_from_toml(self, config_dict: dict, is_first_startup: bool = True):
        """Initialize database configuration from setting.toml"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            if is_first_startup:
                await self._ensure_config_rows(conn, config_dict)
            else:
                await self._ensure_config_rows(conn, config_dict=None)

    async def reload_config_to_memory(self):
        """Reload all configuration from database to in-memory Config instance"""
        from .config import config

        admin_config = await self.get_admin_config()
        if admin_config:
            config.set_admin_username_from_db(admin_config.username)
            config.set_admin_password_from_db(admin_config.password)
            config.api_key = admin_config.api_key

        cache_config = await self.get_cache_config()
        if cache_config:
            config.set_cache_enabled(cache_config.cache_enabled)
            config.set_cache_timeout(cache_config.cache_timeout)
            config.set_cache_base_url(cache_config.cache_base_url or "")

        generation_config = await self.get_generation_config()
        if generation_config:
            config.set_image_timeout(generation_config.image_timeout)
            config.set_video_timeout(generation_config.video_timeout)

        debug_config = await self.get_debug_config()
        if debug_config:
            config.set_debug_enabled(debug_config.enabled)

        captcha_config = await self.get_captcha_config()
        if captcha_config:
            config.set_captcha_method(captcha_config.captcha_method)
            config.set_yescaptcha_api_key(captcha_config.yescaptcha_api_key)
            config.set_yescaptcha_base_url(captcha_config.yescaptcha_base_url)

    async def get_cache_config(self) -> CacheConfig:
        """Get cache configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM cache_config WHERE id = 1")
            if row:
                return CacheConfig(**dict(row))
            return CacheConfig(cache_enabled=False, cache_timeout=7200)

    async def update_cache_config(self, enabled: bool = None, timeout: int = None, base_url: Optional[str] = None):
        """Update cache configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM cache_config WHERE id = 1")

            if row:
                current = dict(row)
                new_enabled = enabled if enabled is not None else current.get("cache_enabled", False)
                new_timeout = timeout if timeout is not None else current.get("cache_timeout", 7200)
                new_base_url = base_url if base_url is not None else current.get("cache_base_url")

                if base_url == "":
                    new_base_url = None

                await conn.execute("""
                    UPDATE cache_config
                    SET cache_enabled = $1, cache_timeout = $2, cache_base_url = $3, updated_at = NOW()
                    WHERE id = 1
                """, new_enabled, new_timeout, new_base_url)
            else:
                new_enabled = enabled if enabled is not None else False
                new_timeout = timeout if timeout is not None else 7200
                new_base_url = base_url if base_url is not None else None

                await conn.execute("""
                    INSERT INTO cache_config (id, cache_enabled, cache_timeout, cache_base_url)
                    VALUES (1, $1, $2, $3)
                """, new_enabled, new_timeout, new_base_url)

    async def get_debug_config(self) -> 'DebugConfig':
        """Get debug configuration"""
        from .models import DebugConfig
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM debug_config WHERE id = 1")
            if row:
                return DebugConfig(**dict(row))
            return DebugConfig(enabled=False, log_requests=True, log_responses=True, mask_token=True)

    async def update_debug_config(
        self,
        enabled: bool = None,
        log_requests: bool = None,
        log_responses: bool = None,
        mask_token: bool = None
    ):
        """Update debug configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM debug_config WHERE id = 1")

            if row:
                current = dict(row)
                new_enabled = enabled if enabled is not None else current.get("enabled", False)
                new_log_requests = log_requests if log_requests is not None else current.get("log_requests", True)
                new_log_responses = log_responses if log_responses is not None else current.get("log_responses", True)
                new_mask_token = mask_token if mask_token is not None else current.get("mask_token", True)

                await conn.execute("""
                    UPDATE debug_config
                    SET enabled = $1, log_requests = $2, log_responses = $3, mask_token = $4, updated_at = NOW()
                    WHERE id = 1
                """, new_enabled, new_log_requests, new_log_responses, new_mask_token)
            else:
                new_enabled = enabled if enabled is not None else False
                new_log_requests = log_requests if log_requests is not None else True
                new_log_responses = log_responses if log_responses is not None else True
                new_mask_token = mask_token if mask_token is not None else True

                await conn.execute("""
                    INSERT INTO debug_config (id, enabled, log_requests, log_responses, mask_token)
                    VALUES (1, $1, $2, $3, $4)
                """, new_enabled, new_log_requests, new_log_responses, new_mask_token)

    async def get_captcha_config(self) -> CaptchaConfig:
        """Get captcha configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM captcha_config WHERE id = 1")
            if row:
                return CaptchaConfig(**dict(row))
            return CaptchaConfig()

    async def update_captcha_config(
        self,
        captcha_method: str = None,
        yescaptcha_api_key: str = None,
        yescaptcha_base_url: str = None,
        capmonster_api_key: str = None,
        capmonster_base_url: str = None,
        ezcaptcha_api_key: str = None,
        ezcaptcha_base_url: str = None,
        capsolver_api_key: str = None,
        capsolver_base_url: str = None,
        browser_proxy_enabled: bool = None,
        browser_proxy_url: str = None
    ):
        """Update captcha configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM captcha_config WHERE id = 1")

            if row:
                current = dict(row)
                new_method = captcha_method if captcha_method is not None else current.get("captcha_method", "yescaptcha")
                new_yes_key = yescaptcha_api_key if yescaptcha_api_key is not None else current.get("yescaptcha_api_key", "")
                new_yes_url = yescaptcha_base_url if yescaptcha_base_url is not None else current.get("yescaptcha_base_url", "https://api.yescaptcha.com")
                new_cap_key = capmonster_api_key if capmonster_api_key is not None else current.get("capmonster_api_key", "")
                new_cap_url = capmonster_base_url if capmonster_base_url is not None else current.get("capmonster_base_url", "https://api.capmonster.cloud")
                new_ez_key = ezcaptcha_api_key if ezcaptcha_api_key is not None else current.get("ezcaptcha_api_key", "")
                new_ez_url = ezcaptcha_base_url if ezcaptcha_base_url is not None else current.get("ezcaptcha_base_url", "https://api.ez-captcha.com")
                new_cs_key = capsolver_api_key if capsolver_api_key is not None else current.get("capsolver_api_key", "")
                new_cs_url = capsolver_base_url if capsolver_base_url is not None else current.get("capsolver_base_url", "https://api.capsolver.com")
                new_proxy_enabled = browser_proxy_enabled if browser_proxy_enabled is not None else current.get("browser_proxy_enabled", False)
                new_proxy_url = browser_proxy_url if browser_proxy_url is not None else current.get("browser_proxy_url")

                await conn.execute("""
                    UPDATE captcha_config
                    SET captcha_method = $1, yescaptcha_api_key = $2, yescaptcha_base_url = $3,
                        capmonster_api_key = $4, capmonster_base_url = $5,
                        ezcaptcha_api_key = $6, ezcaptcha_base_url = $7,
                        capsolver_api_key = $8, capsolver_base_url = $9,
                        browser_proxy_enabled = $10, browser_proxy_url = $11, updated_at = NOW()
                    WHERE id = 1
                """, new_method, new_yes_key, new_yes_url, new_cap_key, new_cap_url,
                      new_ez_key, new_ez_url, new_cs_key, new_cs_url, new_proxy_enabled, new_proxy_url)
            else:
                new_method = captcha_method if captcha_method is not None else "yescaptcha"
                new_yes_key = yescaptcha_api_key if yescaptcha_api_key is not None else ""
                new_yes_url = yescaptcha_base_url if yescaptcha_base_url is not None else "https://api.yescaptcha.com"
                new_cap_key = capmonster_api_key if capmonster_api_key is not None else ""
                new_cap_url = capmonster_base_url if capmonster_base_url is not None else "https://api.capmonster.cloud"
                new_ez_key = ezcaptcha_api_key if ezcaptcha_api_key is not None else ""
                new_ez_url = ezcaptcha_base_url if ezcaptcha_base_url is not None else "https://api.ez-captcha.com"
                new_cs_key = capsolver_api_key if capsolver_api_key is not None else ""
                new_cs_url = capsolver_base_url if capsolver_base_url is not None else "https://api.capsolver.com"
                new_proxy_enabled = browser_proxy_enabled if browser_proxy_enabled is not None else False
                new_proxy_url = browser_proxy_url

                await conn.execute("""
                    INSERT INTO captcha_config (id, captcha_method, yescaptcha_api_key, yescaptcha_base_url,
                        capmonster_api_key, capmonster_base_url, ezcaptcha_api_key, ezcaptcha_base_url,
                        capsolver_api_key, capsolver_base_url, browser_proxy_enabled, browser_proxy_url)
                    VALUES (1, $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """, new_method, new_yes_key, new_yes_url, new_cap_key, new_cap_url,
                      new_ez_key, new_ez_url, new_cs_key, new_cs_url, new_proxy_enabled, new_proxy_url)

    async def get_plugin_config(self) -> PluginConfig:
        """Get plugin configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM plugin_config WHERE id = 1")
            if row:
                return PluginConfig(**dict(row))
            return PluginConfig()

    async def update_plugin_config(self, connection_token: str, auto_enable_on_update: bool = True):
        """Update plugin configuration"""
        pool = await self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM plugin_config WHERE id = 1")

            if row:
                await conn.execute("""
                    UPDATE plugin_config
                    SET connection_token = $1, auto_enable_on_update = $2, updated_at = NOW()
                    WHERE id = 1
                """, connection_token, auto_enable_on_update)
            else:
                await conn.execute("""
                    INSERT INTO plugin_config (id, connection_token, auto_enable_on_update)
                    VALUES (1, $1, $2)
                """, connection_token, auto_enable_on_update)
