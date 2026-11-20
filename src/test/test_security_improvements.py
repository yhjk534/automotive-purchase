"""Regression tests for the first security-focused improvement iteration."""

from __future__ import annotations

import socket

import pytest

from src.agent.config import INTERRUPT_ON_TOOLS
from src.agent.tools.web_fetch import _extract_archive_to_memory
from src.security import (
    UnsafePathError,
    UnsafeUrlError,
    safe_archive_path,
    safe_join,
    validate_public_http_url,
)


def test_safe_join_allows_normal_and_unicode_names(tmp_path):
    base = tmp_path / "downloads"
    base.mkdir()

    assert safe_join(base, "report.md") == base / "report.md"
    assert safe_join(base, "库存报告.md") == base / "库存报告.md"


@pytest.mark.parametrize(
    "filename",
    ["../secret.txt", r"..\secret.txt", "/etc/passwd", r"C:\secret.txt", ".."],
)
def test_safe_join_rejects_path_traversal(tmp_path, filename):
    with pytest.raises(UnsafePathError):
        safe_join(tmp_path, filename)


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "http://localhost:8000",
        "http://127.0.0.1:9000",
        "http://10.0.0.1",
        "http://169.254.169.254/latest/meta-data",
        "http://user:password@example.com",
    ],
)
def test_url_validation_rejects_internal_or_unsafe_urls(url):
    with pytest.raises(UnsafeUrlError):
        validate_public_http_url(url)


def test_url_validation_accepts_public_host(monkeypatch):
    def public_dns(*_args, **_kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("93.184.216.34", 443),
            )
        ]

    monkeypatch.setattr("src.security.socket.getaddrinfo", public_dns)
    assert validate_public_http_url("https://example.com/docs")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("folder/file.txt", "folder/file.txt"),
        (r"folder\file.txt", "folder/file.txt"),
        ("../secret.txt", None),
        ("/absolute.txt", None),
        ("folder/../../secret.txt", None),
    ],
)
def test_safe_archive_path(name, expected):
    assert safe_archive_path(name) == expected


def test_archive_extraction_skips_traversal_entries():
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("skill/SKILL.md", "# safe")
        archive.writestr("skill/../../secret.txt", "secret")

    files = _extract_archive_to_memory(
        buffer.getvalue(),
        "https://example.com/skill.zip",
        "application/zip",
    )

    assert "SKILL.md" in files
    assert all(".." not in name for name in files)


def test_all_mutating_tools_require_approval():
    expected_write_tools = {
        "supplier_create",
        "supplier_update_status",
        "part_create",
        "order_create",
        "order_update",
        "order_update_status",
        "inventory_inbound",
        "inventory_outbound",
        "install_skill",
        "notification_publish",
    }
    assert expected_write_tools <= set(INTERRUPT_ON_TOOLS)
