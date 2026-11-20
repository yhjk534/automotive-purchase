"""Regression tests for the automotive ERP mock and domain profile."""

from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.messages import HumanMessage

import erp_mock.database as database
from src.agent.harness import is_simple_interaction
from erp_mock.main import app


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "automotive_erp.db")
    database.init_db(force=True)
    return TestClient(app)


def test_automotive_seed_contains_fitments_and_oe_numbers(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        health = client.get("/health").json()["data"]
        assert health["suppliers"] >= 6
        assert health["parts"] >= 10
        assert health["vehicle_models"] >= 5
        assert health["fitments"] >= 20


def test_vehicle_search_can_resolve_camry_then_find_brake_pads(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        vehicles = client.get("/api/vehicles/search", params={"keyword": "凯美瑞"}).json()
        camry = next(item for item in vehicles if item["series"] == "凯美瑞")

        parts = client.get(
            "/api/parts/search",
            params={
                "name": "前制动片",
                "vehicle_model_id": camry["id"],
            },
        ).json()

    assert parts
    brake_pad = parts[0]
    assert brake_pad["category"] == "制动系统"
    assert brake_pad["oeNumbers"]
    assert any(item["series"] == "凯美瑞" for item in brake_pad["fitments"])
    assert len(brake_pad["supplierOffers"]) >= 2


def test_oe_number_search_returns_matching_part(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        parts = client.get(
            "/api/parts/search", params={"oe_number": "04465-06120"}
        ).json()
    assert len(parts) == 1
    assert parts[0]["name"] == "前制动片"


def test_order_statistics_work_with_seed_data(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        stats = client.get("/api/orders/statistics").json()
    assert stats["order_count"] >= 5
    assert stats["total_amount"] > 0
    assert stats["categoryAmounts"]


def test_finance_summary_and_invoices(tmp_path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        summary = client.get("/api/finance/summary").json()
        invoices = client.get("/api/finance/invoices").json()
    assert summary["order_amount"] > 0
    assert summary["invoiced_amount"] > 0
    assert summary["outstanding_amount"] > 0
    assert summary["budget_amount"] > 0
    assert len(invoices) >= 4


def test_active_domain_files_do_not_contain_motorcycle_terms():
    root = Path(__file__).resolve().parents[2]
    files = [
        root / "src/agent/memory/prompts.py",
        root / "src/agent/memory/AGENTS.md",
        root / "src/agent/subagents/configs/procurement_analyst.yaml",
        root / "src/agent/subagents/configs/procurement_order.yaml",
        root / "frontend/src/components/chat/WelcomeScreen.tsx",
    ]
    forbidden = ("摩托车", "化油器", "摩托配")
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        assert not any(term in content for term in forbidden), file_path


def test_capability_introduction_is_not_treated_as_order_task():
    messages = [HumanMessage(content="你好，请用一句话介绍你能处理的汽车零部件采购任务")]
    assert is_simple_interaction(messages)
