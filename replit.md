# Flow2API

## Overview
Flow2API is a Python FastAPI application that provides an OpenAI-compatible API for Google VideoFX (Veo). It includes token management, proxy support, captcha handling, and a web-based admin console.

## Project Architecture
- **Language**: Python 3.11
- **Framework**: FastAPI with Uvicorn
- **Database**: Dual database support:
  - **SQLite** via aiosqlite (stored in `data/flow.db`) - used locally when no `DATABASE_URL` is set
  - **PostgreSQL** via asyncpg - used in production (e.g., Replit with Postgres integration).
- **Config**: TOML-based configuration (`config/setting.toml`), supplemented by a dynamic database-backed configuration system.

### Database Architecture
- `src/core/database.py` - SQLite implementation.
- `src/core/database_pg.py` - PostgreSQL implementation (standard for Replit production).
- **Auto-detection**: `src/main.py` checks for `DATABASE_URL`. If present, uses PostgreSQL; otherwise uses SQLite.
- **Normalization**: PostgreSQL implementation uses `_normalize_dt()` to ensure timezone-aware datetimes are converted to naive UTC (required by `asyncpg`).
- **Migrations**: The app performs automatic schema checks and migrations on startup to ensure tables and columns match the latest code version.

### Key Logic & Features
- **Token Management** (`src/services/token_manager.py`):
  - **AT Auto-refresh**: Automatically converts Session Tokens (ST) to Access Tokens (AT).
  - **ST Auto-refresh**: In `personal` mode, uses the browser to refresh ST if AT refresh fails.
  - **429 Handling**: Automatically bans tokens for 12 hours on rate limit (429) errors, with an hourly auto-unban task.
- **Captcha Handling** (`src/services/browser_captcha_personal.py`):
  - **nodriver Integration**: Uses `nodriver` for stealth browser automation.
  - **Resident Mode**: Maintains open tabs for specific projects to provide instant reCAPTCHA tokens, significantly reducing latency for generation requests.
  - **Environment Sensitivity**: Detects Replit/Docker environments to adjust browser flags (e.g., `--headless=new`).
- **Concurrency & Balancing**:
  - `ConcurrencyManager`: Tracks active tasks per token to respect Google's limits.
  - `LoadBalancer`: Distributes requests across active, healthy tokens.
- **Proxy Support**: Centralized `ProxyManager` providing rotation and fallback capabilities.

### Directory Structure
- `main.py` - Entry point
- `src/main.py` - FastAPI app initialization, lifespan management (starts background tasks: 429 unban, cache cleanup, browser init).
- `src/api/` - OpenAI-compatible endpoints (`routes.py`) and Admin Dashboard API (`admin.py`).
- `src/core/` - Core modules (Auth, Config, Models, Logger).
- `src/services/` - Business logic.
- `static/` - Frontend assets (Login and Management console).

## Replit Setup Guide (Fresh Environment)
1. **Modules**: Ensure `python-3.11` and `postgresql` (if using) are installed.
2. **Database**: 
   - Add the **PostgreSQL** integration in Replit.
   - The app will automatically detect `DATABASE_URL` and initialize the schema.
3. **Secrets**:
   - Add `SESSION_SECRET` (for admin login).
   - (Optional) Add proxy credentials if needed.
4. **Environment**: 
   - The app binds to `0.0.0.0:5000` for Replit web preview compatibility.
   - Run via `python main.py`.

## Recent Changes (History for Future Reference)
- **PostgreSQL Sync**: Implemented full parity between SQLite and PostgreSQL layers.
- **Browser Automation Upgrade**: Migrated to `nodriver` with resident tab support for low-latency captcha.
- **Auto-Migrations**: Added startup logic to automatically update DB schema (adding columns like `ban_reason`, `credits`, etc.).
- **Token Resilience**: Added ST-to-AT refresh logic and 429 auto-recovery.
- **Admin Debugging**: Added persistent debug log table in DB accessible via `/api/debug-logs`.

## Operational Notes for Future Agents
- **Debugging**: Check the `debug_logs` table first. The logger is connected to the database.
- **First Startup**: The app initializes `admin_config` from `setting.toml` only on the very first run. Subsequent changes should be made via the Admin UI.
- **Browser Flags**: On Replit, the app automatically detects the environment and uses `headless=True` for browser tasks.
