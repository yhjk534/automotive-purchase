"""Shared security helpers for files, URLs, and network boundaries."""

from __future__ import annotations

import ipaddress
import socket
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


class UnsafePathError(ValueError):
    """Raised when a requested path can escape its allowed base directory."""


class UnsafeUrlError(ValueError):
    """Raised when a URL points to an unsupported or internal network target."""


def safe_join(base_dir: str | Path, filename: str) -> Path:
    """Join a filename to a base directory without allowing path traversal."""
    if not filename or "\x00" in filename:
        raise UnsafePathError("文件名不能为空")
    if filename in {".", ".."} or "/" in filename or "\\" in filename:
        raise UnsafePathError("文件名不能包含路径分隔符")

    base = Path(base_dir).resolve()
    candidate = (base / filename).resolve()
    if not candidate.is_relative_to(base):
        raise UnsafePathError("文件路径超出了允许的下载目录")
    return candidate


def safe_archive_path(name: str) -> str | None:
    """Normalize an archive member path and reject absolute or parent paths."""
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute() or ".." in path.parts:
        return None
    return path.as_posix()


def validate_public_http_url(url: str, *, resolve_dns: bool = True) -> str:
    """Validate an HTTP(S) URL and reject private or local network targets.

    DNS is resolved before the request. The caller should validate every
    redirect target as well because DNS rebinding cannot be fully prevented by
    this helper alone.
    """
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("只允许 http:// 或 https:// 地址")
    if not parsed.hostname:
        raise UnsafeUrlError("URL 缺少主机名")
    if parsed.username or parsed.password:
        raise UnsafeUrlError("URL 不能包含用户名或密码")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeUrlError("不允许访问本机地址")

    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None

    if literal is not None:
        _ensure_global_ip(literal)
        return url

    if not resolve_dns:
        return url

    try:
        addresses = socket.getaddrinfo(
            hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"无法解析主机名: {hostname}") from exc

    if not addresses:
        raise UnsafeUrlError(f"无法解析主机名: {hostname}")

    for address in addresses:
        _ensure_global_ip(ipaddress.ip_address(address[4][0]))
    return url


def _ensure_global_ip(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if not address.is_global:
        raise UnsafeUrlError(f"不允许访问内网或保留地址: {address}")
