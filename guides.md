# Guide: Running Playwright / Patchright on Replit (Dev & Production)

This guide covers how we got browser automation (Playwright and Patchright) working successfully on Replit, both in the development environment and in production deployments. This is based on real experience from this project (Flow2API).

---

## 1. System-Level Chromium Installation

Replit runs on NixOS. You **cannot** use `apt-get` or `brew`. Instead, Chromium must be installed as a Nix package.

In your `.replit` file, make sure `chromium` and `playwright-driver` are listed under `[nix] packages`:

```toml
[nix]
packages = ["chromium", "playwright-driver"]
```

This installs a system-wide Chromium binary at a path like:
```
/nix/store/...-chromium-xxx/bin/chromium
```

You can verify it works by running in the Shell:
```bash
which chromium
```

---

## 2. Python Dependencies

Add both libraries to your `requirements.txt` (keep both so you have a fallback):

```
patchright>=1.58.0
playwright>=1.40.0
```

Install them:
```bash
pip install patchright playwright
```

---

## 3. Browser Binary Installation (Build Step)

Even with Chromium installed via Nix, Playwright/Patchright need their own browser binaries registered. Add a **build command** in your `.replit` file:

```toml
[deployment]
build = ["bash", "-c", "python -m playwright install chromium"]
```

This ensures the browser binary is set up before the app starts in production.

For Patchright, you can also run:
```bash
python -m patchright install chromium
```

---

## 4. Headless Mode Detection

On Replit, there is **no display server** (no X11/Wayland). You must run the browser in **headless mode**. The project detects the Replit environment automatically using environment variables:

```python
import os

# Replit sets REPL_ID in its environment
is_replit = bool(os.environ.get('REPL_ID'))
headless = True if is_replit else False
```

This way, the browser runs headless on Replit but can run with a visible window on your local machine for debugging.

---

## 5. Required Browser Launch Flags

Replit containers have limited resources and no sandbox support. These flags are essential:

```python
launch_args = [
    '--no-sandbox',
    '--disable-dev-shm-usage',
    '--disable-setuid-sandbox',
    '--disable-gpu',
    '--disable-blink-features=AutomationControlled',
]
```

- `--no-sandbox`: Required because Replit doesn't support the Linux sandbox.
- `--disable-dev-shm-usage`: Prevents crashes due to limited shared memory in containers.
- `--disable-gpu`: No GPU available in Replit containers.
- `--disable-blink-features=AutomationControlled`: Helps avoid bot detection.

---

## 6. Using System Chromium Path

Instead of relying on Playwright/Patchright's bundled browser, use the system Chromium installed via Nix. This is more reliable on Replit:

```python
import shutil

chrome_path = (
    shutil.which('chromium')
    or shutil.which('chromium-browser')
    or shutil.which('google-chrome')
)

# For Playwright:
browser = await playwright.chromium.launch(
    headless=True,
    executable_path=chrome_path,  # Use system Chromium
    args=['--no-sandbox', '--disable-dev-shm-usage']
)

# For Patchright (same API):
browser = await playwright.chromium.launch(
    headless=True,
    executable_path=chrome_path,
    args=['--no-sandbox', '--disable-dev-shm-usage']
)
```

---

## 7. Import Strategy (Patchright with Playwright Fallback)

This project uses Patchright as the primary engine with an automatic fallback to Playwright. Patchright is a drop-in replacement with the exact same API, but better anti-detection:

```python
BROWSER_ENGINE = "none"

try:
    from patchright.async_api import async_playwright
    BROWSER_ENGINE = "patchright"
except ImportError:
    try:
        from playwright.async_api import async_playwright
        BROWSER_ENGINE = "playwright"
    except ImportError:
        print("Neither patchright nor playwright is installed!")
```

You can then use `BROWSER_ENGINE` to log which engine is active.

---

## 8. Docker vs Replit Detection

If you also deploy via Docker, you need to detect the environment properly. Replit is NOT Docker, so check for Replit first:

```python
def _is_running_in_docker():
    # Replit has its own env vars - it's not Docker
    if os.environ.get('REPL_ID') or os.environ.get('REPL_SLUG'):
        return False
    if os.path.exists('/.dockerenv'):
        return True
    return False
```

---

## 9. Production Deployment Checklist

When deploying (publishing) on Replit:

1. **Nix packages**: Ensure `chromium` and `playwright-driver` are in `.replit` packages.
2. **Build step**: Set `build = ["bash", "-c", "python -m playwright install chromium"]` in `.replit` deployment config.
3. **Headless**: The app must detect `REPL_ID` and run headless.
4. **No sandbox flags**: Always include `--no-sandbox` and `--disable-dev-shm-usage`.
5. **System Chromium**: Use `shutil.which('chromium')` to find the Nix-installed binary.
6. **Timeouts**: Browser operations should have generous timeouts (30-60s) because Replit containers can be slow on cold starts.
7. **Memory**: Browser automation is memory-heavy. Avoid running too many browser instances simultaneously. Use a semaphore to limit concurrency.

---

## 10. Patchright vs Playwright - Key Differences

| Feature | Playwright | Patchright |
|---|---|---|
| API | Full (Chromium, Firefox, WebKit) | Chromium only |
| Anti-detection | Basic | Patched CDP, stealth flags |
| Import path | `playwright.async_api` | `patchright.async_api` |
| Console API | Available | Disabled (anti-detection) |
| Drop-in replacement | - | Yes, same API as Playwright |

---

## 11. Troubleshooting

**"Browser not found" error:**
- Run `which chromium` in Shell to verify Nix installed it.
- Make sure `chromium` is in `.replit` `[nix] packages`.

**"No usable sandbox" crash:**
- Add `--no-sandbox` to launch args.

**Browser crashes on startup:**
- Add `--disable-dev-shm-usage` flag.
- Check memory usage - you may be running too many instances.

**Works in dev but not in production:**
- Make sure the build step installs the browser binary.
- Check deployment logs for errors.
- Ensure headless mode is enabled (no display in production).

**Timeout errors:**
- Increase timeouts for page loads and browser operations.
- Replit cold starts can be slow; allow 30-60 seconds for first browser launch.
