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
│   │   ├── database.py    # SQLite database operations
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
- aiosqlite (SQLite async database)
- curl-cffi (HTTP client)
- playwright (browser automation for captcha)
- nodriver (alternative browser automation)

## Recent Changes
- Configured to run on port 5000 for Replit compatibility
- Changed default captcha method to yescaptcha (browser mode requires additional system dependencies)
- Added Python gitignore entries for Replit environment
