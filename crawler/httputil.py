from __future__ import annotations

import json
import os
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional
from urllib.parse import urlparse

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 D-Ai-ly/1.0"
)


def _ctx() -> ssl.SSLContext:
    return ssl.create_default_context()


def cookie_from_env(env_name: str | None) -> str | None:
    """Load a session cookie from environment. Never log the value."""
    if not env_name:
        return None
    val = (os.environ.get(env_name) or "").strip()
    return val or None


def headers_with_cookie(
    cookie: str | None,
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    hdrs = dict(base or {})
    if cookie:
        hdrs["Cookie"] = cookie
    return hdrs


def fetch_bytes(
    url: str,
    *,
    timeout: float = 25.0,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    hdrs = {
        "User-Agent": DEFAULT_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as resp:
        raw = resp.read()
        meta = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, meta, raw


def fetch_text(
    url: str,
    timeout: float = 25.0,
    encoding: Optional[str] = None,
    *,
    headers: dict[str, str] | None = None,
) -> str:
    status, meta, raw = fetch_bytes(url, timeout=timeout, headers=headers)
    if encoding:
        return raw.decode(encoding, errors="replace")
    charset = "utf-8"
    ctype = meta.get("content-type", "")
    if "charset=" in ctype:
        charset = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
    return raw.decode(charset, errors="replace")


def fetch_json(
    url: str,
    *,
    timeout: float = 25.0,
    method: str = "GET",
    form: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    data = None
    hdrs = {"Accept": "application/json,text/plain,*/*"}
    if headers:
        hdrs.update(headers)
    if form is not None:
        data = urllib.parse.urlencode(form).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded")
        method = method if method != "GET" else "POST"
    _status, _meta, raw = fetch_bytes(
        url, timeout=timeout, method=method, data=data, headers=hdrs
    )
    return json.loads(raw.decode("utf-8", errors="replace"))


def host_reachable(url: str, timeout: float = 3.0) -> bool:
    """DNS + best-effort TCP probe.

    Returns True on DNS success even if TCP probe fails — some networks
    drop connect probes while still allowing HTTPS (or vice versa). Callers
    should still catch fetch errors.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        ip = socket.gethostbyname(host)
    except OSError:
        return False
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect((ip, port))
        return True
    except OSError:
        # DNS worked; let the real HTTPS fetch decide
        return True
    finally:
        s.close()


def url_ok(url: str, timeout: float = 15.0) -> tuple[bool, str]:
    """Deterministic link check: GET/HEAD returns 2xx/3xx and non-empty body for GET."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, "invalid url"
    try:
        status, _meta, raw = fetch_bytes(url, timeout=timeout, method="GET")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    if status >= 400:
        return False, f"http {status}"
    if len(raw) < 32:
        return False, "body too small"
    # Detect soft-404 / login walls that still return 200
    head = raw[:4000].decode("utf-8", errors="ignore")
    head_l = head.lower()
    if "jiqizhixin.com" in url and (
        "数据服务已上线" in head or "机器之心·数据服务" in head
    ):
        return False, "jiqizhixin data-service wall"
    if status == 200 and len(raw) < 80:
        return False, "body too small for homepage"
    if "just a moment" in head_l and "cloudflare" in head_l:
        return False, "cloudflare challenge"
    return True, f"http {status} bytes={len(raw)}"


def looks_like_xml(text: str) -> bool:
    s = text.lstrip()[:200].lower()
    return s.startswith("<?xml") or s.startswith("<rss") or s.startswith("<feed")
