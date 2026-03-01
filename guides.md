# Guide: Running Flow2API on Replit (Dev & Production)

This guide covers the full setup for running Flow2API on Replit, including browser automation (Playwright/Patchright), PostgreSQL database, and upstream sync. Based on real fixes applied to this project.

---

## 1. System-Level Chromium Installation

Replit runs on NixOS. You **cannot** use `apt-get` or `brew`. Chromium must be installed as a Nix package.

In your `.replit` file, ensure `chromium` and `playwright-driver` are listed:

```toml
[nix]
packages = ["chromium", "playwright-driver"]
```

Verify it works:
```bash
which chromium
# e.g. /nix/store/...-chromium-xxx/bin/chromium
```

---

## 2. Python Dependencies

Both libraries in `requirements.txt` (patchright preferred, playwright as fallback):

```
patchright>=1.58.0
playwright>=1.40.0
```

---

## 3. Browser Binary Installation (Build Step)

Add a **build command** in `.replit`:

```toml
[deployment]
build = ["bash", "-c", "python -m playwright install chromium"]
```

---

## 4. Replit Docker Detection Fix (CRITICAL)

**Problem**: Replit containers have `/.dockerenv` which makes the app think it's in Docker and **disables browser captcha entirely**.

**Fix**: Check for Replit environment FIRST in `_is_running_in_docker()`:

```python
def _is_running_in_docker():
    # Replit has /.dockerenv but is NOT Docker — browsers work fine
    if os.environ.get('REPL_ID') or os.environ.get('REPL_SLUG'):
        return False
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open('/proc/1/cgroup', 'r') as f:
            content = f.read()
            if 'docker' in content or 'kubepods' in content or 'containerd' in content:
                return True
    except:
        pass
    if os.environ.get('DOCKER_CONTAINER') or os.environ.get('KUBERNETES_SERVICE_HOST'):
        return True
    return False
```

**File**: `src/services/browser_captcha.py`

---

## 5. Browser Launch Config for Replit

**Problem**: Default launch uses `headless=False` (no display on Replit) and Playwright's bundled browser (not installed on Replit).

**Fix**: Detect Replit, force headless, use system Nix chromium:

```python
import shutil

is_replit = bool(os.environ.get('REPL_ID') or os.environ.get('REPL_SLUG'))
headless_mode = True if is_replit else False
chrome_path = shutil.which('chromium') if is_replit else None

launch_kwargs = {
    'headless': headless_mode,
    'proxy': proxy_option,
    'args': [
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-setuid-sandbox',
        '--disable-gpu',
        '--disable-blink-features=AutomationControlled',
        '--no-first-run',
        '--no-zygote',
    ]
}
if chrome_path:
    launch_kwargs['executable_path'] = chrome_path

browser = await playwright.chromium.launch(**launch_kwargs)
```

**File**: `src/services/browser_captcha.py` — `_create_browser()` method

---

## 6. Import Strategy (Patchright → Playwright Fallback)

Patchright is preferred for anti-detection. Fallback to Playwright if not installed:

```python
BROWSER_ENGINE = "none"

try:
    from patchright.async_api import async_playwright, Route, BrowserContext
    BROWSER_ENGINE = "patchright"
except ImportError:
    try:
        from playwright.async_api import async_playwright, Route, BrowserContext
        BROWSER_ENGINE = "playwright"
    except ImportError:
        print("[BrowserCaptcha] ❌ patchright and playwright both not installed")
```

**File**: `src/services/browser_captcha.py`

---

## 7. PostgreSQL Database (Replit)

### Auto-Detection

Replit provides PostgreSQL via `DATABASE_URL` env var. The app auto-detects:

```python
# In src/main.py
import os
if os.environ.get("DATABASE_URL"):
    from .core.database_pg import PostgresDatabase
    db = PostgresDatabase()
    print("📦 Using PostgreSQL database")
else:
    db = Database()
    print("📦 Using SQLite database")
```

### Syncing database_pg.py with Upstream

When merging upstream changes, `database_pg.py` must be manually synced:

1. **Check for new columns**: Compare `database.py` table schemas with `database_pg.py`
2. **Check method signatures**: Compare method params (e.g., `update_proxy_config`)
3. **Add migrations**: Add missing columns in `check_and_migrate_db()`

**Example — media_proxy columns added to proxy_config:**

```sql
-- Run directly via psql if migration hasn't run on restart:
ALTER TABLE proxy_config ADD COLUMN IF NOT EXISTS media_proxy_enabled BOOLEAN DEFAULT false;
ALTER TABLE proxy_config ADD COLUMN IF NOT EXISTS media_proxy_url TEXT;
```

Or via shell:
```bash
psql "$DATABASE_URL" -c "ALTER TABLE proxy_config ADD COLUMN IF NOT EXISTS media_proxy_enabled BOOLEAN DEFAULT false; ALTER TABLE proxy_config ADD COLUMN IF NOT EXISTS media_proxy_url TEXT;"
```

---

## 8. Upstream Sync Procedure

When syncing with `TheSmallHanCat/flow2api:main`:

### Steps
```bash
git fetch upstream
git merge upstream/main --allow-unrelated-histories --no-commit
# Accept upstream for all conflicts:
git checkout --theirs <conflicting files>
git add <all files>
# Then re-apply our Replit-specific changes (see below)
git commit -m "Merge upstream/main with Replit customizations"
git push origin main
```

### Files We Customize (re-apply after merge)

| File | Our Changes |
|---|---|
| `src/services/browser_captcha.py` | Replit Docker detection bypass, patchright import, headless + system chromium |
| `src/main.py` | PostgreSQL auto-detect (`DATABASE_URL` → `PostgresDatabase`) |
| `src/core/database_pg.py` | Must sync new columns/methods with upstream `database.py` |
| `requirements.txt` | `patchright>=1.58.0` added |
| `src/services/generation_handler.py` | `BROWSER_ENGINE` logging |

### Post-Merge Checklist

- [ ] Check `database_pg.py` method signatures match `database.py`
- [ ] Check for new DB columns in `database.py` — add to `database_pg.py` schema + migration
- [ ] Run DB migration (`psql` or restart app)
- [ ] Verify Docker detection bypass still present
- [ ] Verify headless + system chromium launch still present
- [ ] Verify `main.py` still has PostgreSQL auto-detect
- [ ] Test: proxy config save
- [ ] Test: image generation request

---

## 9. Patchright vs Playwright

| Feature | Playwright | Patchright |
|---|---|---|
| API | Full (Chromium, Firefox, WebKit) | Chromium only |
| Anti-detection | Basic | Patched CDP, stealth flags |
| Import path | `playwright.async_api` | `patchright.async_api` |
| Console API | Available | Disabled (anti-detection) |
| Drop-in replacement | - | Yes, same API as Playwright |

---

## 10. Troubleshooting

**"Docker 环境" / browser captcha disabled:**
- Replit has `/.dockerenv` — check that `_is_running_in_docker()` has the Replit bypass

**"Captcha Engine: none":**
- Docker detection is blocking imports. Fix the Docker detection first.

**"TargetClosedError: BrowserType.launch":**
- Missing chromium binary. Use `shutil.which('chromium')` as `executable_path`
- Or: running headed (`headless=False`) on Replit. Force `headless=True`

**"Browser not found" error:**
- Run `which chromium` to verify Nix installed it
- Ensure `chromium` is in `.replit` `[nix] packages`

**"column X does not exist" (PostgreSQL):**
- Upstream added new columns. Run migration manually:
  ```bash
  psql "$DATABASE_URL" -c "ALTER TABLE <table> ADD COLUMN IF NOT EXISTS <col> <type>;"
  ```

**"got an unexpected keyword argument" (PostgreSQL):**
- `database_pg.py` method signature is out of sync with upstream. Compare and update.

**"cannot import name '_save_to_db'":**
- Upstream `logger.py` changed. Remove references to internal functions that no longer exist.

**Timeout errors:**
- Increase timeouts for browser operations (30-60s for Replit cold starts)

**Memory issues:**
- Limit browser instances via semaphore. Browser automation is memory-heavy.
