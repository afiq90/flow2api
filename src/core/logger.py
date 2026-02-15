"""Debug logger module for detailed API request/response logging"""
import json
import sys
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from .config import config

_db_instance = None

def set_db_instance(db):
    global _db_instance
    _db_instance = db

def _save_to_db(level: str, category: str, message: str, details: str = None):
    """Fire-and-forget save to database"""
    if _db_instance is None:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_db_instance.add_debug_log(level, category, message, details))
    except RuntimeError:
        pass


class DebugLogger:
    """Debug logger for API requests and responses - outputs to stdout for production visibility"""

    def _mask_token(self, token: str) -> str:
        """Mask token for logging (show first 6 and last 6 characters)"""
        if not config.debug_mask_token or len(token) <= 12:
            return token
        return f"{token[:6]}...{token[-6:]}"

    def _format_timestamp(self) -> str:
        """Format current timestamp"""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    def _write_separator(self, char: str = "=", length: int = 80):
        """Write separator line"""
        print(char * length, flush=True)

    def _truncate_large_fields(self, data: Any, max_length: int = 200) -> Any:
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                if key in ("encodedImage", "base64", "imageData", "data") and isinstance(value, str) and len(value) > max_length:
                    result[key] = f"{value[:100]}... (truncated, total {len(value)} chars)"
                else:
                    result[key] = self._truncate_large_fields(value, max_length)
            return result
        elif isinstance(data, list):
            return [self._truncate_large_fields(item, max_length) for item in data]
        elif isinstance(data, str) and len(data) > 10000:
            return f"{data[:100]}... (truncated, total {len(data)} chars)"
        return data

    def log_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        body: Optional[Any] = None,
        files: Optional[Dict] = None,
        proxy: Optional[str] = None
    ):
        """Log API request details to stdout"""
        print(f"🔵 [REQUEST] {method} {url}", flush=True)

        if not config.debug_enabled:
            return

        if not config.debug_log_requests:
            return

        try:
            self._write_separator()
            print(f"🔵 [REQUEST] {self._format_timestamp()}", flush=True)
            print(f"  Captcha Method: {config.captcha_method}", flush=True)
            self._write_separator("-")

            print(f"  Method: {method}", flush=True)
            print(f"  URL: {url}", flush=True)

            masked_headers = dict(headers)
            if "Authorization" in masked_headers or "authorization" in masked_headers:
                auth_key = "Authorization" if "Authorization" in masked_headers else "authorization"
                auth_value = masked_headers[auth_key]
                if auth_value.startswith("Bearer "):
                    token = auth_value[7:]
                    masked_headers[auth_key] = f"Bearer {self._mask_token(token)}"

            if "Cookie" in masked_headers:
                cookie_value = masked_headers["Cookie"]
                if "__Secure-next-auth.session-token=" in cookie_value:
                    parts = cookie_value.split("=", 1)
                    if len(parts) == 2:
                        st_token = parts[1].split(";")[0]
                        masked_headers["Cookie"] = f"__Secure-next-auth.session-token={self._mask_token(st_token)}"

            print("  📋 Headers:", flush=True)
            for key, value in masked_headers.items():
                print(f"    {key}: {value}", flush=True)

            if body is not None:
                print("  📦 Request Body:", flush=True)
                if isinstance(body, (dict, list)):
                    truncated_body = self._truncate_large_fields(body)
                    body_str = json.dumps(truncated_body, indent=2, ensure_ascii=False)
                    print(f"    {body_str}", flush=True)
                else:
                    print(f"    {str(body)[:2000]}", flush=True)

            if files:
                print("  📎 Files: <file data>", flush=True)

            if proxy:
                print(f"  🌐 Proxy: {proxy}", flush=True)

            self._write_separator()
            sys.stdout.flush()

            details_parts = [f"Method: {method}", f"URL: {url}"]
            if body is not None:
                if isinstance(body, (dict, list)):
                    truncated_body = self._truncate_large_fields(body)
                    details_parts.append(f"Body: {json.dumps(truncated_body, ensure_ascii=False)[:2000]}")
            if proxy:
                details_parts.append(f"Proxy: {proxy}")
            _save_to_db("REQUEST", "API", f"{method} {url}", "\n".join(details_parts))

        except Exception as e:
            print(f"❌ Error logging request: {e}", flush=True)

    def log_response(
        self,
        status_code: int,
        headers: Dict[str, str],
        body: Any,
        duration_ms: Optional[float] = None
    ):
        """Log API response details to stdout"""
        print(f"🟢 [RESPONSE] {status_code}", flush=True)

        if not config.debug_enabled:
            return

        if not config.debug_log_responses:
            return

        try:
            self._write_separator()
            print(f"🟢 [RESPONSE] {self._format_timestamp()}", flush=True)
            self._write_separator("-")

            status_emoji = "✅" if 200 <= status_code < 300 else "❌"
            print(f"  Status: {status_code} {status_emoji}", flush=True)

            if duration_ms is not None:
                print(f"  Duration: {duration_ms:.2f}ms", flush=True)

            print("  📋 Response Headers:", flush=True)
            for key, value in headers.items():
                print(f"    {key}: {value}", flush=True)

            print("  📦 Response Body:", flush=True)
            if isinstance(body, (dict, list)):
                body_to_log = self._truncate_large_fields(body)
                body_str = json.dumps(body_to_log, indent=2, ensure_ascii=False)
                print(f"    {body_str}", flush=True)
            elif isinstance(body, str):
                try:
                    parsed = json.loads(body)
                    parsed = self._truncate_large_fields(parsed)
                    body_str = json.dumps(parsed, indent=2, ensure_ascii=False)
                    print(f"    {body_str}", flush=True)
                except:
                    if len(body) > 2000:
                        print(f"    {body[:2000]}... (truncated)", flush=True)
                    else:
                        print(f"    {body}", flush=True)
            else:
                print(f"    {str(body)}", flush=True)

            self._write_separator()
            sys.stdout.flush()

            details_parts = [f"Status: {status_code}"]
            if duration_ms is not None:
                details_parts.append(f"Duration: {duration_ms:.2f}ms")
            if isinstance(body, (dict, list)):
                body_to_log = self._truncate_large_fields(body)
                details_parts.append(f"Body: {json.dumps(body_to_log, ensure_ascii=False)[:2000]}")
            elif isinstance(body, str):
                details_parts.append(f"Body: {body[:2000]}")
            _save_to_db("RESPONSE", "API", f"Response {status_code}", "\n".join(details_parts))

        except Exception as e:
            print(f"❌ Error logging response: {e}", flush=True)

    def log_error(
        self,
        error_message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None
    ):
        """Log API error details to stdout"""
        print(f"🔴 [ERROR] {error_message}", flush=True)
        if not config.debug_enabled:
            return

        try:
            self._write_separator()
            print(f"🔴 [ERROR] {self._format_timestamp()}", flush=True)
            self._write_separator("-")

            if status_code:
                print(f"  Status Code: {status_code}", flush=True)

            print(f"  Error Message: {error_message}", flush=True)

            if response_text:
                print("  📦 Error Response:", flush=True)
                try:
                    parsed = json.loads(response_text)
                    body_str = json.dumps(parsed, indent=2, ensure_ascii=False)
                    print(f"    {body_str}", flush=True)
                except:
                    if len(response_text) > 2000:
                        print(f"    {response_text[:2000]}... (truncated)", flush=True)
                    else:
                        print(f"    {response_text}", flush=True)

            self._write_separator()
            sys.stdout.flush()

            details_parts = []
            if status_code:
                details_parts.append(f"Status: {status_code}")
            details_parts.append(f"Message: {error_message}")
            if response_text:
                details_parts.append(f"Response: {response_text[:2000]}")
            _save_to_db("ERROR", "API", error_message[:500], "\n".join(details_parts))

        except Exception as e:
            print(f"❌ Error logging error detail: {e}", flush=True)

    def log_info(self, message: str):
        """Log general info message to stdout"""
        if not config.debug_enabled:
            return
        print(f"ℹ️  [{self._format_timestamp()}] {message}", flush=True)
        _save_to_db("INFO", "GENERAL", message[:500])

    def log_warning(self, message: str):
        """Log warning message to stdout"""
        if not config.debug_enabled:
            return
        print(f"⚠️  [{self._format_timestamp()}] {message}", flush=True)
        _save_to_db("WARNING", "GENERAL", message[:500])

# Global debug logger instance
debug_logger = DebugLogger()
