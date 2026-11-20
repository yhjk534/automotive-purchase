"""Mock automotive-parts ERP with the HTTP contract expected by the MCP server."""

from __future__ import annotations

import math
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from erp_mock.database import get_conn, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="汽车零部件 ERP 模拟服务",
    description="用于汽车零部件智能采购助手的本地可重复测试 ERP。",
    version="1.0.0",
    lifespan=lifespan,
)


def ok(data=None, message: str = "操作成功") -> dict:
    return {"code": 200, "message": message, "data": data}


def paged(records: list[dict], total: int, current: int, size: int) -> dict:
    return {
        "records": records,
        "total": total,
        "current": current,
        "size": size,
        "pages": math.ceil(total / size) if size else 0,
    }


def rows(rows_obj) -> list[dict]:
    return [dict(row) for row in rows_obj]


def page_args(current: int, size: int) -> tuple[int, int]:
    current = max(1, current)
    size = min(max(1, size), 100)
    return current, size


def part_payload(conn, part: dict) -> dict:
    part_id = part["id"]
    part["oeNumbers"] = rows(conn.execute(
        "SELECT number, number_type, brand FROM part_number WHERE part_id = ? ORDER BY id",
        (part_id,),
    ).fetchall())
    part["fitments"] = rows(conn.execute(
        """SELECT v.id AS vehicle_model_id, v.brand, v.series, v.model_name,
                  v.year_start, v.year_end, v.engine, v.displacement,
                  f.position, f.note
           FROM part_fitment f JOIN vehicle_model v ON v.id = f.vehicle_model_id
           WHERE f.part_id = ? ORDER BY v.brand, v.series, v.year_start""",
        (part_id,),
    ).fetchall())
    part["supplierOffers"] = rows(conn.execute(
        """SELECT o.supplier_id, s.name AS supplier_name, s.credit_rating,
                  s.on_time_rate, s.quality_ppm, o.supplier_part_no,
                  o.purchase_price, o.currency, o.tax_included, o.moq,
                  o.lead_time_days, o.valid_from, o.valid_to
           FROM supplier_offer o JOIN supplier s ON s.id = o.supplier_id
           WHERE o.part_id = ? AND s.status = 1
           ORDER BY o.purchase_price, o.lead_time_days""",
        (part_id,),
    ).fetchall())
    return part


# ============================ Supplier ============================

@app.get("/api/suppliers/page", summary="分页查询汽车零部件供应商")
def supplier_page(
    current: int = 1,
    size: int = 10,
    name: str | None = None,
    status: int | None = None,
    creditRating: str | None = None,
):
    current, size = page_args(current, size)
    where, params = ["1=1"], []
    if name:
        where.append("(name LIKE ? OR supplier_code LIKE ? OR contact_person LIKE ?)")
        params.extend([f"%{name}%"] * 3)
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if creditRating:
        where.append("credit_rating = ?")
        params.append(creditRating)
    clause = " AND ".join(where)
    conn = get_conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM supplier WHERE {clause}", params).fetchone()[0]
        data = rows(conn.execute(
            f"SELECT * FROM supplier WHERE {clause} ORDER BY id LIMIT ? OFFSET ?",
            [*params, size, (current - 1) * size],
        ).fetchall())
    finally:
        conn.close()
    return paged(data, total, current, size)


@app.get("/api/suppliers/search", summary="按名称搜索供应商")
def supplier_search(name: str):
    conn = get_conn()
    try:
        data = rows(conn.execute(
            """SELECT * FROM supplier
               WHERE name LIKE ? OR supplier_code LIKE ? OR contact_person LIKE ?
               ORDER BY credit_rating, on_time_rate DESC LIMIT 50""",
            (f"%{name}%", f"%{name}%", f"%{name}%"),
        ).fetchall())
    finally:
        conn.close()
    return data


@app.get("/api/suppliers/get/{supplier_id}", summary="获取供应商详情")
def supplier_get(supplier_id: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM supplier WHERE id = ?", (supplier_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "供应商不存在")
        data = dict(row)
        data["offeredParts"] = rows(conn.execute(
            """SELECT p.id AS part_id, p.part_code, p.name, p.category,
                      o.purchase_price, o.moq, o.lead_time_days
               FROM supplier_offer o JOIN part p ON p.id = o.part_id
               WHERE o.supplier_id = ? ORDER BY p.category, p.name""",
            (supplier_id,),
        ).fetchall())
    finally:
        conn.close()
    return data


class SupplierCreate(BaseModel):
    supplierCode: str
    name: str
    contactPerson: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    creditRating: str | None = "B"
    status: int = 1


@app.post("/api/suppliers/create", summary="创建供应商")
def supplier_create(body: SupplierCreate):
    conn = get_conn()
    try:
        try:
            cur = conn.execute(
                """INSERT INTO supplier
                   (supplier_code, name, contact_person, phone, email, address,
                    credit_rating, status)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (body.supplierCode, body.name, body.contactPerson, body.phone,
                 body.email, body.address, body.creditRating or "B", body.status),
            )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(400, f"供应商创建失败: {exc}") from exc
        return {"id": cur.lastrowid, **body.model_dump()}
    finally:
        conn.close()


@app.patch("/api/suppliers/update-status/{supplier_id}", summary="更新供应商状态")
def supplier_update_status(supplier_id: int, status: int):
    if status not in (0, 1):
        raise HTTPException(400, "status 只能为 0 或 1")
    conn = get_conn()
    try:
        cur = conn.execute("UPDATE supplier SET status = ? WHERE id = ?", (status, supplier_id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "供应商不存在")
    finally:
        conn.close()
    return {"id": supplier_id, "status": status}


# ============================ Vehicle ============================

@app.get("/api/vehicles/search", summary="按品牌、车系、车型或发动机搜索适配车型")
def vehicle_search(keyword: str):
    like = f"%{keyword}%"
    conn = get_conn()
    try:
        data = rows(conn.execute(
            """SELECT * FROM vehicle_model
               WHERE brand LIKE ? OR series LIKE ? OR model_name LIKE ?
                  OR engine LIKE ? OR displacement LIKE ?
               ORDER BY brand, series, year_start DESC LIMIT 50""",
            (like, like, like, like, like),
        ).fetchall())
    finally:
        conn.close()
    return data


@app.get("/api/vehicles/get/{vehicle_model_id}", summary="获取车型详情")
def vehicle_get(vehicle_model_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT * FROM vehicle_model WHERE id = ?", (vehicle_model_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(404, "车型不存在")
        data = dict(row)
        data["compatibleParts"] = rows(conn.execute(
            """SELECT p.id AS part_id, p.part_code, p.name, p.category,
                      f.position, f.note
               FROM part_fitment f JOIN part p ON p.id = f.part_id
               WHERE f.vehicle_model_id = ? ORDER BY p.category, p.name""",
            (vehicle_model_id,),
        ).fetchall())
    finally:
        conn.close()
    return data


# ============================ Parts ============================

def _part_filter(
    name: str | None,
    category: str | None,
    supplier_id: int | None,
    vehicle_model_id: int | None,
    oe_number: str | None,
    origin_type: str | None,
) -> tuple[str, list]:
    where, params = ["1=1"], []
    if name:
        where.append(
            "(p.name LIKE ? OR p.part_code LIKE ? OR p.model LIKE ? OR p.specification LIKE ? OR p.brand LIKE ?)"
        )
        params.extend([f"%{name}%"] * 5)
    if category:
        where.append("p.category = ?")
        params.append(category)
    if supplier_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM supplier_offer so WHERE so.part_id = p.id AND so.supplier_id = ?)"
        )
        params.append(supplier_id)
    if vehicle_model_id is not None:
        where.append(
            "EXISTS (SELECT 1 FROM part_fitment f WHERE f.part_id = p.id AND f.vehicle_model_id = ?)"
        )
        params.append(vehicle_model_id)
    if oe_number:
        where.append(
            "EXISTS (SELECT 1 FROM part_number n WHERE n.part_id = p.id AND n.number LIKE ?)"
        )
        params.append(f"%{oe_number}%")
    if origin_type:
        where.append("p.origin_type = ?")
        params.append(origin_type)
    return " AND ".join(where), params


@app.get("/api/parts/search", summary="搜索汽车零部件，可按车型、OE号和质量来源筛选")
def parts_search(
    name: str | None = None,
    category: str | None = None,
    supplier_id: int | None = None,
    vehicle_model_id: int | None = None,
    oe_number: str | None = None,
    origin_type: str | None = None,
):
    clause, params = _part_filter(name, category, supplier_id, vehicle_model_id, oe_number, origin_type)
    conn = get_conn()
    try:
        rows_obj = conn.execute(
            f"""SELECT p.*, s.name AS supplier_name
                FROM part p LEFT JOIN supplier s ON s.id = p.supplier_id
                WHERE {clause} ORDER BY p.category, p.name LIMIT 100""",
            params,
        ).fetchall()
        data = [part_payload(conn, dict(row)) for row in rows_obj]
    finally:
        conn.close()
    return data


@app.get("/api/parts/page", summary="分页查询汽车零部件")
def parts_page(
    current: int = 1,
    size: int = 10,
    name: str | None = None,
    category: str | None = None,
    supplierId: int | None = None,
    vehicleModelId: int | None = None,
    oeNumber: str | None = None,
    originType: str | None = None,
):
    current, size = page_args(current, size)
    clause, params = _part_filter(name, category, supplierId, vehicleModelId, oeNumber, originType)
    conn = get_conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM part p WHERE {clause}", params).fetchone()[0]
        rows_obj = conn.execute(
            f"""SELECT p.*, s.name AS supplier_name
                FROM part p LEFT JOIN supplier s ON s.id = p.supplier_id
                WHERE {clause} ORDER BY p.id LIMIT ? OFFSET ?""",
            [*params, size, (current - 1) * size],
        ).fetchall()
        data = [part_payload(conn, dict(row)) for row in rows_obj]
    finally:
        conn.close()
    return paged(data, total, current, size)


@app.get("/api/parts/get/{part_id}", summary="获取零部件详情、车型适配和供应商报价")
def parts_get(part_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT p.*, s.name AS supplier_name
               FROM part p LEFT JOIN supplier s ON s.id = p.supplier_id
               WHERE p.id = ?""",
            (part_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "零部件不存在")
        data = part_payload(conn, dict(row))
        data["inventory"] = rows(conn.execute(
            "SELECT * FROM inventory WHERE part_id = ? ORDER BY warehouse_location",
            (part_id,),
        ).fetchall())
    finally:
        conn.close()
    return data


@app.get("/api/parts/supplier/{supplier_id}", summary="获取供应商可供汽车零部件")
def parts_by_supplier(supplier_id: int):
    conn = get_conn()
    try:
        data = rows(conn.execute(
            """SELECT p.*, o.supplier_part_no, o.purchase_price AS offer_price,
                      o.moq, o.lead_time_days
               FROM supplier_offer o JOIN part p ON p.id = o.part_id
               WHERE o.supplier_id = ? ORDER BY p.category, p.name""",
            (supplier_id,),
        ).fetchall())
    finally:
        conn.close()
    return data


class PartCreate(BaseModel):
    partCode: str
    name: str
    purchasePrice: float = Field(ge=0)
    model: str | None = None
    specification: str | None = None
    unit: str | None = "件"
    suggestedRetailPrice: float | None = None
    stockWarningValue: int | None = 0
    supplierId: int | None = None
    category: str = "其他"
    description: str | None = None
    brand: str | None = None
    position: str | None = None
    originType: str = "品牌件"
    warrantyMonths: int = 0


@app.post("/api/parts/create", summary="创建汽车零部件")
def parts_create(body: PartCreate):
    if body.supplierId is None:
        raise HTTPException(400, "supplierId 必填")
    conn = get_conn()
    try:
        supplier = conn.execute("SELECT id FROM supplier WHERE id = ?", (body.supplierId,)).fetchone()
        if supplier is None:
            raise HTTPException(404, "供应商不存在")
        cur = conn.execute(
            """INSERT INTO part
               (part_code, name, category, model, specification, unit, purchase_price,
                suggested_retail_price, stock_warning_value, supplier_id, brand,
                position, origin_type, warranty_months, description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (body.partCode, body.name, body.category, body.model, body.specification,
             body.unit, body.purchasePrice, body.suggestedRetailPrice,
             body.stockWarningValue, body.supplierId, body.brand, body.position,
             body.originType, body.warrantyMonths, body.description),
        )
        conn.commit()
        return {"id": cur.lastrowid, **body.model_dump()}
    finally:
        conn.close()


# ============================ Orders ============================

ORDER_STATUS = {
    0: "待审核", 1: "已审核", 2: "已发货", 3: "已收货", 4: "已完成"
}


def _order_payload(conn, order: dict) -> dict:
    order["statusName"] = ORDER_STATUS.get(order["status"], "未知")
    order["supplier"] = dict(conn.execute(
        "SELECT id, supplier_code, name, credit_rating FROM supplier WHERE id = ?",
        (order["supplier_id"],),
    ).fetchone())
    order["orderDetail"] = rows(conn.execute(
        """SELECT d.*, p.part_code, p.name AS part_name, p.brand, p.origin_type
           FROM purchase_order_detail d JOIN part p ON p.id = d.part_id
           WHERE d.order_id = ? ORDER BY d.id""",
        (order["id"],),
    ).fetchall())
    return order


@app.post("/api/orders/create", summary="创建汽车零部件采购订单")
def order_create(order_data: dict):
    details = order_data.get("orderDetail") or []
    if not details:
        raise HTTPException(400, "orderDetail 至少需要一条明细")
    conn = get_conn()
    try:
        total = 0.0
        first_supplier = order_data.get("supplierId")
        for detail in details:
            quantity = int(detail.get("quantity", 0))
            price = float(detail.get("unitPrice", 0))
            if quantity < 1 or price <= 0:
                raise HTTPException(400, "quantity 必须 >= 1 且 unitPrice 必须 > 0")
            part = conn.execute("SELECT id, supplier_id FROM part WHERE id = ?", (detail.get("partId"),)).fetchone()
            if part is None:
                raise HTTPException(404, f"零部件不存在: {detail.get('partId')}")
            first_supplier = first_supplier or part["supplier_id"]
            total += quantity * price
        supplier = conn.execute("SELECT * FROM supplier WHERE id = ?", (first_supplier,)).fetchone()
        if supplier is None:
            raise HTTPException(404, "供应商不存在")
        if supplier["status"] != 1:
            raise HTTPException(400, "供应商已停用，不能创建订单")
        number = order_data.get("orderNumber") or ("PO" + datetime.now().strftime("%Y%m%d%H%M%S"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute(
            """INSERT INTO purchase_order
               (order_number, supplier_id, total_amount, status, currency,
                tax_included, expected_date, remark, order_time)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (number, first_supplier, round(total, 2), int(order_data.get("status", 0)),
             order_data.get("currency", "CNY"), int(order_data.get("taxIncluded", 1)),
             order_data.get("expectedDate"), order_data.get("remark"), now),
        )
        for detail in details:
            conn.execute(
                """INSERT INTO purchase_order_detail
                   (order_id, part_id, quantity, unit_price, required_date, remark)
                   VALUES (?,?,?,?,?,?)""",
                (cur.lastrowid, detail["partId"], detail["quantity"], detail["unitPrice"],
                 detail.get("requiredDate"), detail.get("remark")),
            )
        conn.commit()
        row = conn.execute("SELECT * FROM purchase_order WHERE id = ?", (cur.lastrowid,)).fetchone()
        data = _order_payload(conn, dict(row))
    finally:
        conn.close()
    return data


@app.put("/api/orders/update/{order_id}", summary="更新采购订单")
def order_update(order_id: int, order_data: dict):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM purchase_order WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "订单不存在")
        supplier_id = order_data.get("supplierId", row["supplier_id"])
        conn.execute(
            """UPDATE purchase_order
               SET supplier_id = ?, total_amount = ?, status = ?, currency = ?,
                   tax_included = ?, expected_date = ?, remark = ?
               WHERE id = ?""",
            (supplier_id, order_data.get("totalAmount", row["total_amount"]),
             order_data.get("status", row["status"]), order_data.get("currency", row["currency"]),
             int(order_data.get("taxIncluded", row["tax_included"])),
             order_data.get("expectedDate", row["expected_date"]),
             order_data.get("remark", row["remark"]), order_id),
        )
        if order_data.get("orderDetail"):
            conn.execute("DELETE FROM purchase_order_detail WHERE order_id = ?", (order_id,))
            for detail in order_data["orderDetail"]:
                conn.execute(
                    """INSERT INTO purchase_order_detail
                       (order_id, part_id, quantity, unit_price, required_date, remark)
                       VALUES (?,?,?,?,?,?)""",
                    (order_id, detail["partId"], detail["quantity"], detail["unitPrice"],
                     detail.get("requiredDate"), detail.get("remark")),
                )
        conn.commit()
        updated = conn.execute("SELECT * FROM purchase_order WHERE id = ?", (order_id,)).fetchone()
        data = _order_payload(conn, dict(updated))
    finally:
        conn.close()
    return data


@app.get("/api/orders/page", summary="分页查询采购订单")
def order_page(
    current: int = 1,
    size: int = 10,
    orderNumber: str | None = None,
    status: int | None = None,
    startDate: str | None = None,
    endDate: str | None = None,
):
    current, size = page_args(current, size)
    where, params = ["1=1"], []
    if orderNumber:
        where.append("order_number LIKE ?")
        params.append(f"%{orderNumber}%")
    if status is not None:
        where.append("status = ?")
        params.append(status)
    if startDate:
        where.append("date(order_time) >= date(?)")
        params.append(startDate)
    if endDate:
        where.append("date(order_time) <= date(?)")
        params.append(endDate)
    clause = " AND ".join(where)
    conn = get_conn()
    try:
        total = conn.execute(f"SELECT COUNT(*) FROM purchase_order WHERE {clause}", params).fetchone()[0]
        data = rows(conn.execute(
            f"SELECT * FROM purchase_order WHERE {clause} ORDER BY id DESC LIMIT ? OFFSET ?",
            [*params, size, (current - 1) * size],
        ).fetchall())
        for order in data:
            order["statusName"] = ORDER_STATUS.get(order["status"], "未知")
    finally:
        conn.close()
    return paged(data, total, current, size)


@app.get("/api/orders/get/{order_id}", summary="获取采购订单详情")
def order_get(order_id: int):
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM purchase_order WHERE id = ?", (order_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "订单不存在")
        data = _order_payload(conn, dict(row))
    finally:
        conn.close()
    return data


@app.get("/api/orders/search-details", summary="搜索订单明细")
def order_search_details(
    partName: str | None = None,
    startDate: str | None = None,
    endDate: str | None = None,
):
    where, params = ["1=1"], []
    if partName:
        where.append("(p.name LIKE ? OR p.part_code LIKE ? OR p.brand LIKE ?)")
        params.extend([f"%{partName}%"] * 3)
    if startDate:
        where.append("date(o.order_time) >= date(?)")
        params.append(startDate)
    if endDate:
        where.append("date(o.order_time) <= date(?)")
        params.append(endDate)
    conn = get_conn()
    try:
        data = rows(conn.execute(
            f"""SELECT d.*, o.order_number, o.status, o.status AS status_code,
                       o.order_time, p.part_code, p.name AS part_name,
                       p.category, p.brand, p.origin_type, s.name AS supplier_name
                FROM purchase_order_detail d
                JOIN purchase_order o ON o.id = d.order_id
                JOIN part p ON p.id = d.part_id
                JOIN supplier s ON s.id = o.supplier_id
                WHERE {' AND '.join(where)}
                ORDER BY o.order_time DESC, d.id""",
            params,
        ).fetchall())
        for item in data:
            item["statusName"] = ORDER_STATUS.get(item["status"], "未知")
    finally:
        conn.close()
    return data


@app.get("/api/orders/statistics", summary="汽车零部件采购统计")
def order_statistics(startDate: str | None = None, endDate: str | None = None):
    where, params = ["1=1"], []
    if startDate:
        where.append("date(order_time) >= date(?)")
        params.append(startDate)
    if endDate:
        where.append("date(order_time) <= date(?)")
        params.append(endDate)
    conn = get_conn()
    try:
        summary = dict(conn.execute(
            f"""SELECT COUNT(*) AS order_count, COALESCE(SUM(total_amount),0) AS total_amount,
                       COALESCE(AVG(total_amount),0) AS average_amount
                FROM purchase_order WHERE {' AND '.join(where)}""",
            params,
        ).fetchone())
        summary["statusCounts"] = rows(conn.execute(
            f"""SELECT status, COUNT(*) AS count FROM purchase_order
                WHERE {' AND '.join(where)} GROUP BY status ORDER BY status""",
            params,
        ).fetchall())
        summary["categoryAmounts"] = rows(conn.execute(
            f"""SELECT p.category, ROUND(SUM(d.quantity * d.unit_price), 2) AS amount
                FROM purchase_order_detail d
                JOIN purchase_order o ON o.id = d.order_id
                JOIN part p ON p.id = d.part_id
                WHERE {' AND '.join('o.' + x if x.startswith(('date(', 'order_time')) else x for x in where)}
                GROUP BY p.category ORDER BY amount DESC""",
            params,
        ).fetchall())
    finally:
        conn.close()
    return summary


@app.patch("/api/orders/update-status/{order_id}", summary="更新订单状态")
def order_update_status(order_id: int, status: int):
    if status not in ORDER_STATUS:
        raise HTTPException(400, "status 必须在 0-4 之间")
    conn = get_conn()
    try:
        cur = conn.execute("UPDATE purchase_order SET status = ? WHERE id = ?", (status, order_id))
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "订单不存在")
    finally:
        conn.close()
    return {"id": order_id, "status": status, "statusName": ORDER_STATUS[status]}


# ============================ Inventory ============================

@app.get("/api/inventory/page", summary="分页查询汽车零部件库存")
def inventory_page(
    current: int = 1,
    size: int = 10,
    partName: str | None = None,
    warehouseLocation: str | None = None,
):
    current, size = page_args(current, size)
    where, params = ["1=1"], []
    if partName:
        where.append("(p.name LIKE ? OR p.part_code LIKE ? OR p.brand LIKE ?)")
        params.extend([f"%{partName}%"] * 3)
    if warehouseLocation:
        where.append("i.warehouse_location = ?")
        params.append(warehouseLocation)
    clause = " AND ".join(where)
    conn = get_conn()
    try:
        total = conn.execute(
            f"SELECT COUNT(*) FROM inventory i JOIN part p ON p.id = i.part_id WHERE {clause}",
            params,
        ).fetchone()[0]
        data = rows(conn.execute(
            f"""SELECT i.*, i.current_quantity AS currentQuantity,
                       p.part_code, p.name AS part_name, p.category, p.brand,
                       p.origin_type, p.unit,
                       i.current_quantity - i.reserved_quantity AS available_quantity
                FROM inventory i JOIN part p ON p.id = i.part_id
                WHERE {clause} ORDER BY i.id LIMIT ? OFFSET ?""",
            [*params, size, (current - 1) * size],
        ).fetchall())
    finally:
        conn.close()
    return paged(data, total, current, size)


@app.get("/api/inventory/warning", summary="库存预警")
def inventory_warning():
    conn = get_conn()
    try:
        data = rows(conn.execute(
            """SELECT p.id AS part_id, p.part_code, p.name AS part_name,
                      p.category, p.brand, p.origin_type,
                      i.current_quantity, i.current_quantity AS quantity,
                      i.reserved_quantity, i.safety_stock, i.warehouse_location,
                      i.bin_location, i.batch_number,
                      i.safety_stock - i.current_quantity AS shortage,
                      s.name AS supplier_name, s.credit_rating
               FROM inventory i JOIN part p ON p.id = i.part_id
               LEFT JOIN supplier s ON s.id = p.supplier_id
               WHERE i.current_quantity < i.safety_stock
               ORDER BY shortage DESC, p.name""",
        ).fetchall())
    finally:
        conn.close()
    return data


@app.get("/api/inventory/check", summary="库存盘点统计")
def inventory_check():
    conn = get_conn()
    try:
        data = dict(conn.execute(
            """SELECT COUNT(*) AS sku_count,
                      SUM(CASE WHEN i.current_quantity < i.safety_stock THEN 1 ELSE 0 END) AS warning_count,
                      SUM(i.current_quantity) AS total_quantity,
                      SUM(i.current_quantity * p.purchase_price) AS total_value
               FROM inventory i JOIN part p ON p.id = i.part_id"""
        ).fetchone())
        data["warehouses"] = rows(conn.execute(
            """SELECT warehouse_location, COUNT(*) AS sku_count,
                      SUM(current_quantity) AS total_quantity
               FROM inventory GROUP BY warehouse_location ORDER BY warehouse_location"""
        ).fetchall())
    finally:
        conn.close()
    return data


@app.post("/api/inventory/inbound", summary="库存入库")
def inventory_inbound(
    partId: int,
    quantity: int,
    warehouseLocation: str | None = None,
):
    if quantity <= 0:
        raise HTTPException(400, "quantity 必须大于 0")
    warehouse = warehouseLocation or "华东中心仓"
    conn = get_conn()
    try:
        part = conn.execute("SELECT id FROM part WHERE id = ?", (partId,)).fetchone()
        if part is None:
            raise HTTPException(404, "零部件不存在")
        row = conn.execute(
            "SELECT * FROM inventory WHERE part_id = ? AND warehouse_location = ?",
            (partId, warehouse),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE inventory SET current_quantity = current_quantity + ?, updated_at = ? WHERE id = ?",
                (quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
            )
        else:
            safety = conn.execute("SELECT stock_warning_value FROM part WHERE id = ?", (partId,)).fetchone()[0]
            conn.execute(
                """INSERT INTO inventory
                   (part_id, current_quantity, safety_stock, warehouse_location, updated_at)
                   VALUES (?,?,?,?,?)""",
                (partId, quantity, safety, warehouse, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
        conn.commit()
        current = conn.execute(
            "SELECT current_quantity FROM inventory WHERE part_id = ? AND warehouse_location = ?",
            (partId, warehouse),
        ).fetchone()[0]
    finally:
        conn.close()
    return {"partId": partId, "quantity": quantity, "currentQuantity": current, "warehouseLocation": warehouse}


@app.post("/api/inventory/outbound", summary="库存出库")
def inventory_outbound(partId: int, quantity: int):
    if quantity <= 0:
        raise HTTPException(400, "quantity 必须大于 0")
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT * FROM inventory WHERE part_id = ?
               ORDER BY (current_quantity - reserved_quantity) DESC LIMIT 1""",
            (partId,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "零部件库存记录不存在")
        available = row["current_quantity"] - row["reserved_quantity"]
        if quantity > available:
            raise HTTPException(400, f"可用库存不足，当前可用 {available}")
        conn.execute(
            "UPDATE inventory SET current_quantity = current_quantity - ?, updated_at = ? WHERE id = ?",
            (quantity, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), row["id"]),
        )
        conn.commit()
        current = row["current_quantity"] - quantity
    finally:
        conn.close()
    return {"partId": partId, "quantity": quantity, "currentQuantity": current}


@app.get("/api/inventory/get/{inventory_id}", summary="获取库存记录")
def inventory_get(inventory_id: int):
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT i.*, p.name AS part_name, p.part_code
               FROM inventory i JOIN part p ON p.id = i.part_id WHERE i.id = ?""",
            (inventory_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(404, "库存记录不存在")
        data = dict(row)
    finally:
        conn.close()
    return data


# ============================ Finance ============================

def _finance_where(
    start_date: str | None,
    end_date: str | None,
    supplier_id: int | None,
    category: str | None,
) -> tuple[str, list]:
    where, params = ["1=1"], []
    if start_date:
        where.append("date(o.order_time) >= date(?)")
        params.append(start_date)
    if end_date:
        where.append("date(o.order_time) <= date(?)")
        params.append(end_date)
    if supplier_id is not None:
        where.append("o.supplier_id = ?")
        params.append(supplier_id)
    if category:
        where.append(
            """EXISTS (
                SELECT 1 FROM purchase_order_detail d
                JOIN part p ON p.id = d.part_id
                WHERE d.order_id = o.id AND p.category = ?
            )"""
        )
        params.append(category)
    return " AND ".join(where), params


@app.get("/api/finance/summary", summary="统一财务查询")
def finance_summary(
    startDate: str | None = None,
    endDate: str | None = None,
    supplierId: int | None = None,
    category: str | None = None,
):
    clause, params = _finance_where(startDate, endDate, supplierId, category)
    conn = get_conn()
    try:
        orders = dict(conn.execute(
            f"""SELECT COUNT(*) AS order_count,
                       COALESCE(SUM(o.total_amount), 0) AS order_amount,
                       COALESCE(SUM(CASE WHEN o.status = 0 THEN o.total_amount ELSE 0 END), 0)
                           AS pending_approval_amount,
                       COALESCE(SUM(CASE WHEN o.status = 2 THEN o.total_amount ELSE 0 END), 0)
                           AS in_transit_amount
                FROM purchase_order o WHERE {clause}""",
            params,
        ).fetchone())
        invoice = dict(conn.execute(
            f"""SELECT COALESCE(SUM(i.amount), 0) AS invoiced_amount,
                       COALESCE(SUM(i.paid_amount), 0) AS paid_amount,
                       COALESCE(SUM(i.amount - i.paid_amount), 0) AS outstanding_amount,
                       SUM(CASE WHEN i.due_date < date('now') AND i.amount > i.paid_amount
                                THEN 1 ELSE 0 END) AS overdue_invoice_count
                FROM finance_invoice i
                JOIN purchase_order o ON o.id = i.order_id
                WHERE {clause}""",
            params,
        ).fetchone())
        category_rows = rows(conn.execute(
            f"""SELECT p.category,
                       ROUND(SUM(d.quantity * d.unit_price), 2) AS amount
                FROM purchase_order_detail d
                JOIN purchase_order o ON o.id = d.order_id
                JOIN part p ON p.id = d.part_id
                WHERE {clause}
                GROUP BY p.category ORDER BY amount DESC""",
            params,
        ).fetchall())
        supplier_rows = rows(conn.execute(
            f"""SELECT s.id AS supplier_id, s.name AS supplier_name,
                       COUNT(o.id) AS order_count,
                       ROUND(SUM(o.total_amount), 2) AS amount
                FROM purchase_order o JOIN supplier s ON s.id = o.supplier_id
                WHERE {clause}
                GROUP BY s.id, s.name ORDER BY amount DESC""",
            params,
        ).fetchall())
        period = (startDate or datetime.now().strftime("%Y-%m"))[:7]
        budget_where = "period = ?"
        budget_params: list = [period]
        if category:
            budget_where += " AND category = ?"
            budget_params.append(category)
        budget_rows = rows(conn.execute(
            f"SELECT period, category, budget_amount FROM budget WHERE {budget_where}",
            budget_params,
        ).fetchall())
        budget_total = sum(item["budget_amount"] for item in budget_rows)
        used_amount = sum(
            item["amount"]
            for item in category_rows
            if any(b["category"] == item["category"] for b in budget_rows)
        )
    finally:
        conn.close()

    return {
        **orders,
        **invoice,
        "budget_amount": round(budget_total, 2),
        "budget_used_amount": round(used_amount, 2),
        "budget_utilization": round(used_amount / budget_total, 4) if budget_total else 0,
        "categoryBreakdown": category_rows,
        "supplierBreakdown": supplier_rows,
        "budgetBreakdown": budget_rows,
        "period": period,
    }


@app.get("/api/finance/invoices", summary="查询财务发票和应付状态")
def finance_invoices(
    startDate: str | None = None,
    endDate: str | None = None,
    supplierId: int | None = None,
):
    where, params = ["1=1"], []
    if startDate:
        where.append("date(i.invoice_date) >= date(?)")
        params.append(startDate)
    if endDate:
        where.append("date(i.invoice_date) <= date(?)")
        params.append(endDate)
    if supplierId is not None:
        where.append("i.supplier_id = ?")
        params.append(supplierId)
    conn = get_conn()
    try:
        data = rows(conn.execute(
            f"""SELECT i.*, o.order_number, s.name AS supplier_name
                FROM finance_invoice i
                JOIN purchase_order o ON o.id = i.order_id
                JOIN supplier s ON s.id = i.supplier_id
                WHERE {' AND '.join(where)}
                ORDER BY i.invoice_date DESC""",
            params,
        ).fetchall())
    finally:
        conn.close()
    return data


@app.get("/api/finance/budgets", summary="查询采购预算")
def finance_budgets(period: str | None = None):
    period = period or datetime.now().strftime("%Y-%m")
    conn = get_conn()
    try:
        data = rows(conn.execute(
            "SELECT * FROM budget WHERE period = ? ORDER BY category",
            (period,),
        ).fetchall())
    finally:
        conn.close()
    return data


@app.get("/health", summary="健康检查")
def health():
    conn = get_conn()
    try:
        counts = dict(conn.execute(
            """SELECT
                 (SELECT COUNT(*) FROM supplier) AS suppliers,
                 (SELECT COUNT(*) FROM part) AS parts,
                 (SELECT COUNT(*) FROM vehicle_model) AS vehicle_models,
                 (SELECT COUNT(*) FROM part_fitment) AS fitments,
                 (SELECT COUNT(*) FROM purchase_order) AS orders,
                 (SELECT COUNT(*) FROM finance_invoice) AS invoices"""
        ).fetchone())
    finally:
        conn.close()
    return ok({"status": "up", **counts})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8081)
