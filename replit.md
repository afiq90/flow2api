# Flow2API

## Overview
Flow2API is a Python FastAPI application that provides an OpenAI-compatible API for Google VideoFX (Veo). It includes token management, proxy support, captcha handling, and a web-based admin console.

## Project Architecture
- **Language**: Python 3.11
- **Framework**: FastAPI with Uvicorn
- **Database**: Dual database support:
  - **SQLite** via aiosqlite (stored in `data/flow.db`) - used locally when no `DATABASE_URL` is set
  - **PostgreSQL** via asyncpg - used in production when `DATABASE_URL` environment variable is present
- **Config**: TOML-based configuration (`config/setting.toml`)

### Database Architecture
- `src/core/database.py` - SQLite implementation (original, untouched)
- `src/core/database_pg.py` - PostgreSQL implementation (same interface as SQLite)
- Auto-detection in `src/main.py`: if `DATABASE_URL` env var exists, uses PostgreSQL; otherwise uses SQLite
- Both implementations share the same method signatures and return the same Pydantic models

### Directory Structure
- `main.py` - Entry point
- `src/main.py` - FastAPI app initialization, lifespan management
- `src/api/` - API routes and admin endpoints
- `src/core/` - Config, database, models, auth, logger
- `src/services/` - Business logic (token management, proxy, captcha, etc.)
- `static/` - Frontend HTML files (login.html, manage.html)
- `config/` - Configuration files

## Running
- Server runs on `0.0.0.0:5000` (configured in `config/setting.toml`)
- Workflow: `python main.py`
- Deployment: **VM** type (always running) — required because the app is stateful with browser instances, background tasks, and connection pools

### PostgreSQL Compatibility Notes
- `database_pg.py` includes `_normalize_dt()` to convert timezone-aware datetimes to naive UTC (asyncpg is strict about TIMESTAMP vs TIMESTAMPTZ)
- Float timestamps (e.g. `time.time()`) passed to `_at` fields are auto-converted to `datetime` objects
- Browser captcha checks for system Chromium first (`shutil.which`) to avoid slow Playwright downloads at startup

### Debug Logging
- Debug logs output to **stdout** (console) for visibility in both dev and production
- Debug logs are also stored in the `debug_logs` database table for persistent access
- API endpoints: `GET /api/debug-logs` and `DELETE /api/debug-logs` (admin auth required)
- Logger initialized in `src/core/logger.py`, connected to DB via `set_db_instance()` in `src/main.py`
- Captcha method is logged at startup and on each captcha request for debugging

## Key Dependencies
- fastapi, uvicorn, aiosqlite, asyncpg, pydantic, curl-cffi, bcrypt, tomli, python-multipart, playwright, nodriver
