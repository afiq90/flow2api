# Flow2API

## Overview
Flow2API is an OpenAI-compatible API for Google VideoFX (Veo). It provides a FastAPI-based web service that serves as a proxy/adapter for Google's video generation services.

## Project Structure
```
├── main.py                 # Entry point - starts uvicorn server
├── src/
│   ├── main.py            # FastAPI app initialization, routes, lifespan
│   ├── api/
│   │   ├── routes.py      # API endpoints
│   │   └── admin.py       # Admin endpoints
│   ├── core/
│   │   ├── config.py      # Configuration management (loads from setting.toml)
│   │   ├── database.py    # PostgreSQL database operations (asyncpg)
│   │   ├── models.py      # Pydantic models
│   │   └── logger.py      # Logging utilities
│   └── services/
│       ├── flow_client.py          # Google Flow API client
│       ├── token_manager.py        # Token management
│       ├── proxy_manager.py        # Proxy management
│       ├── load_balancer.py        # Load balancing
│       ├── concurrency_manager.py  # Concurrency control
│       ├── generation_handler.py   # Generation request handling
│       ├── file_cache.py           # File caching
│       ├── browser_captcha.py      # Browser-based captcha solving (Playwright)
│       └── browser_captcha_personal.py  # Personal browser captcha (nodriver)
├── config/
│   └── setting.toml       # Configuration file
├── static/
│   ├── login.html         # Login page
│   └── manage.html        # Management console
└── tmp/                   # Temporary files for caching
```

## Database
- Uses PostgreSQL via asyncpg with connection pooling
- Database URL is configured via DATABASE_URL environment variable
- Tables are automatically created on first startup

## Configuration
Configuration is stored in `config/setting.toml`. Key settings:
- Server runs on port 5000 (configured for Replit)
- Default admin credentials: admin/admin
- Captcha method: yescaptcha (browser mode requires Playwright dependencies)

## Running the Application
The application starts automatically via the workflow command:
```bash
python main.py
```

## Dependencies
- Python 3.11
- FastAPI + Uvicorn
- asyncpg (PostgreSQL async driver with connection pooling)
- curl-cffi (HTTP client)
- aiohttp (async HTTP client)

## Captcha Methods
The application supports multiple captcha solving methods:
- **ezcaptcha** - Third-party captcha solving service (recommended for production)
- **yescaptcha** - Third-party captcha solving service
- **capmonster** - Third-party captcha solving service
- **capsolver** - Third-party captcha solving service
- **browser/personal** - Browser-based methods (require additional dependencies not installed by default)

## Production Deployment Notes
- **Browser captcha (personal/browser methods) is automatically disabled in production**
- The app detects `REPLIT_DEPLOYMENT=1` environment variable (set by Replit in deployments)
- This prevents timeout issues caused by Chromium/Playwright initialization
- For production, use third-party captcha services: ezcaptcha, yescaptcha, capmonster, or capsolver

## Recent Changes
- Added production detection to disable browser captcha in deployed environments (Jan 2026)
- Migrated from SQLite (aiosqlite) to PostgreSQL (asyncpg)
- Uses connection pooling for better performance
- Database URL configured via DATABASE_URL environment variable
- Configured to run on port 5000 for Replit compatibility
- Removed playwright and nodriver dependencies for lighter deployment
- Browser-based captcha methods now optional (graceful degradation if not installed)
- Recommended captcha method: ezcaptcha (or other third-party services)
