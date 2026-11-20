"""SQLite data layer and automotive-parts seed data for the mock ERP.

The mock keeps the HTTP contract used by ``src/mcp_server`` while adding
automotive domain data that the original motorcycle demo did not model:
vehicle fitment, OE numbers, supplier offers, warehouse bins, and batches.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "automotive_erp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS supplier (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_code     TEXT NOT NULL UNIQUE,
    name              TEXT NOT NULL,
    contact_person    TEXT,
    phone             TEXT,
    email             TEXT,
    address           TEXT,
    credit_rating     TEXT NOT NULL DEFAULT 'B',
    on_time_rate      REAL NOT NULL DEFAULT 95.0,
    quality_ppm       INTEGER NOT NULL DEFAULT 500,
    monthly_capacity  INTEGER NOT NULL DEFAULT 0,
    status            INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS vehicle_model (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    brand         TEXT NOT NULL,
    series        TEXT NOT NULL,
    model_name    TEXT NOT NULL,
    year_start    INTEGER NOT NULL,
    year_end      INTEGER NOT NULL,
    engine        TEXT NOT NULL,
    displacement  TEXT NOT NULL,
    market        TEXT NOT NULL DEFAULT '中国'
);

CREATE TABLE IF NOT EXISTS part (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    part_code              TEXT NOT NULL UNIQUE,
    name                   TEXT NOT NULL,
    category               TEXT NOT NULL,
    model                  TEXT,
    specification          TEXT,
    unit                   TEXT NOT NULL DEFAULT '件',
    purchase_price         REAL NOT NULL,
    suggested_retail_price REAL,
    stock_warning_value    INTEGER NOT NULL DEFAULT 0,
    supplier_id            INTEGER NOT NULL,
    brand                  TEXT,
    position               TEXT,
    origin_type            TEXT NOT NULL DEFAULT '品牌件',
    warranty_months        INTEGER NOT NULL DEFAULT 0,
    description            TEXT,
    FOREIGN KEY (supplier_id) REFERENCES supplier(id)
);

CREATE TABLE IF NOT EXISTS part_number (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id      INTEGER NOT NULL,
    number       TEXT NOT NULL,
    number_type  TEXT NOT NULL,
    brand        TEXT,
    UNIQUE(part_id, number, number_type),
    FOREIGN KEY (part_id) REFERENCES part(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS part_fitment (
    part_id           INTEGER NOT NULL,
    vehicle_model_id  INTEGER NOT NULL,
    position          TEXT,
    note              TEXT,
    PRIMARY KEY (part_id, vehicle_model_id),
    FOREIGN KEY (part_id) REFERENCES part(id) ON DELETE CASCADE,
    FOREIGN KEY (vehicle_model_id) REFERENCES vehicle_model(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS supplier_offer (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id        INTEGER NOT NULL,
    part_id            INTEGER NOT NULL,
    supplier_part_no   TEXT,
    purchase_price     REAL NOT NULL,
    currency           TEXT NOT NULL DEFAULT 'CNY',
    tax_included       INTEGER NOT NULL DEFAULT 1,
    moq                INTEGER NOT NULL DEFAULT 1,
    lead_time_days     INTEGER NOT NULL DEFAULT 7,
    valid_from         TEXT,
    valid_to           TEXT,
    UNIQUE(supplier_id, part_id),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id),
    FOREIGN KEY (part_id) REFERENCES part(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS inventory (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id           INTEGER NOT NULL,
    current_quantity  INTEGER NOT NULL,
    safety_stock      INTEGER NOT NULL,
    reserved_quantity INTEGER NOT NULL DEFAULT 0,
    warehouse_location TEXT NOT NULL DEFAULT '华东中心仓',
    bin_location      TEXT,
    batch_number      TEXT,
    updated_at        TEXT NOT NULL,
    UNIQUE(part_id, warehouse_location),
    FOREIGN KEY (part_id) REFERENCES part(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS purchase_order (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_number  TEXT NOT NULL UNIQUE,
    supplier_id   INTEGER NOT NULL,
    total_amount  REAL NOT NULL,
    status        INTEGER NOT NULL DEFAULT 0,
    currency      TEXT NOT NULL DEFAULT 'CNY',
    tax_included  INTEGER NOT NULL DEFAULT 1,
    expected_date TEXT,
    remark        TEXT,
    order_time    TEXT NOT NULL,
    FOREIGN KEY (supplier_id) REFERENCES supplier(id)
);

CREATE TABLE IF NOT EXISTS purchase_order_detail (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id       INTEGER NOT NULL,
    part_id        INTEGER NOT NULL,
    quantity       INTEGER NOT NULL,
    unit_price     REAL NOT NULL,
    required_date  TEXT,
    remark         TEXT,
    FOREIGN KEY (order_id) REFERENCES purchase_order(id) ON DELETE CASCADE,
    FOREIGN KEY (part_id) REFERENCES part(id)
);

CREATE TABLE IF NOT EXISTS finance_invoice (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      INTEGER NOT NULL UNIQUE,
    invoice_no    TEXT NOT NULL UNIQUE,
    supplier_id   INTEGER NOT NULL,
    invoice_date  TEXT NOT NULL,
    due_date      TEXT NOT NULL,
    amount        REAL NOT NULL,
    paid_amount   REAL NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT '未付款',
    FOREIGN KEY (order_id) REFERENCES purchase_order(id),
    FOREIGN KEY (supplier_id) REFERENCES supplier(id)
);

CREATE TABLE IF NOT EXISTS budget (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    period         TEXT NOT NULL,
    category       TEXT NOT NULL,
    budget_amount  REAL NOT NULL,
    UNIQUE(period, category)
);
"""

SUPPLIERS = [
    ("AC-SUP-001", "上海安驰汽车制动系统有限公司", "周明", "13810001001",
     "sales@anchibrake.example", "上海市嘉定区汽车产业园", "A", 98.6, 120, 18000, 1),
    ("AC-SUP-002", "苏州恒擎动力科技有限公司", "王颖", "13810001002",
     "sales@hengqing.example", "苏州市工业园区星湖街", "A", 97.4, 85, 15000, 1),
    ("AC-SUP-003", "广州德驰汽车滤清系统有限公司", "陈杰", "13810001003",
     "sales@dechi.example", "广州市黄埔区汽车零部件基地", "B", 95.1, 210, 25000, 1),
    ("AC-SUP-004", "江苏联创底盘科技有限公司", "刘芳", "13810001004",
     "sales@lianchuang.example", "常州市新北区智造产业园", "B", 93.8, 320, 12000, 1),
    ("AC-SUP-005", "宁波启航汽车电气有限公司", "赵磊", "13810001005",
     "sales@qihang.example", "宁波市北仑区汽配园", "B", 92.5, 450, 9000, 1),
    ("AC-SUP-006", "北方动力汽车零部件集团", "孙涛", "13810001006",
     "sales@bfpower.example", "天津市滨海新区装备园", "C", 88.0, 800, 6000, 0),
]

# (part_code, name, category, compatible summary, specification, unit,
#  purchase_price, retail_price, safety_stock, primary_supplier_id, brand,
#  position, origin_type, warranty_months, description)
PARTS = [
    ("BRK-PAD-CAMRY-F", "前制动片", "制动系统", "凯美瑞/亚洲龙/ES", "前轴套装",
     "套", 268.5, 428.0, 80, 1, "ADVICS", "前", "OES", 12,
     "低粉尘陶瓷配方，适用于凯美瑞、亚洲龙及雷克萨斯 ES 前制动系统。"),
    ("BRK-PAD-ACCORD-F", "前制动片", "制动系统", "雅阁/英仕派", "前轴套装",
     "套", 238.0, 398.0, 60, 1, "NISSIN", "前", "OES", 12,
     "适配本田雅阁与英仕派前制动系统。"),
    ("OIL-FIL-M20A", "机油滤清器", "保养耗材", "凯美瑞/RAV4 2.0L", "M20A 发动机",
     "个", 32.8, 58.0, 200, 3, "DENSO", "发动机舱", "OES", 6,
     "高过滤效率机油滤清器，适用于丰田 M20A 2.0L 发动机。"),
    ("AIR-FIL-CAMRY", "空气滤清器", "过滤系统", "凯美瑞 2.0L", "高流量纸质滤芯",
     "个", 78.0, 128.0, 120, 3, "DENSO", "发动机舱", "OES", 6,
     "适配第八代丰田凯美瑞 2.0L 车型。"),
    ("CABIN-FIL-ACTIVE", "活性炭空调滤清器", "过滤系统", "中型轿车通用", "活性炭双层滤芯",
     "个", 96.0, 158.0, 100, 3, "MANN", "车内空调", "品牌件", 6,
     "过滤颗粒物及异味，适配多款中型轿车。"),
    ("SPARK-IRIDIUM-ILZKR7B11", "铱金火花塞", "点火系统", "2.0L/2.5L 自然吸气",
     "ILZKR7B11", "支", 68.0, 105.0, 300, 2, "NGK", "发动机", "OES", 12,
     "长寿命铱金火花塞，适用于指定丰田、本田及大众发动机。"),
    ("BAT-AGM-H6-70AH", "AGM 启停蓄电池", "电气系统", "H6 规格多车型",
     "12V 70Ah", "只", 680.0, 980.0, 20, 5, "VARTA", "发动机舱", "品牌件", 24,
     "支持启停系统的高循环寿命 AGM 蓄电池。"),
    ("SHOCK-RAV4-R", "后减震器", "悬挂系统", "RAV4荣放 2020-2024", "后轴单支",
     "支", 520.0, 760.0, 30, 4, "KYB", "后", "OES", 24,
     "适配丰田 RAV4 荣放后悬挂系统。"),
    ("ARM-CAMRY-LF", "左下控制臂", "底盘系统", "凯美瑞 2020-2024", "左前下摆臂总成",
     "件", 430.0, 680.0, 20, 4, "LEMFORDER", "左前", "品牌件", 24,
     "含衬套总成，适配第八代凯美瑞左前底盘。"),
    ("WIPER-24-18", "无骨雨刮片套装", "车身附件", "24/18 英寸多车型", "24英寸+18英寸",
     "套", 98.0, 168.0, 80, 5, "BOSCH", "前风挡", "品牌件", 6,
     "静音无骨雨刮片套装，覆盖主流轿车和 SUV。"),
    ("BELT-6PK-1830", "多楔带", "传动系统", "凯美瑞/RAV4 2.0L", "6PK1830",
     "条", 135.0, 218.0, 60, 2, "GATES", "发动机前端", "OEM", 12,
     "耐高温多楔带，适配指定丰田 2.0L 发动机附件系统。"),
    ("COOLANT-G12-4L", "长效冷却液", "保养耗材", "多品牌通用", "G12 -35℃ 4L",
     "桶", 88.0, 138.0, 120, 3, "BASF", "冷却系统", "品牌件", 36,
     "适用于符合 G12 规范的主流乘用车冷却系统。"),
]

VEHICLES = [
    ("丰田", "凯美瑞", "第八代凯美瑞", 2020, 2024, "M20A", "2.0L"),
    ("丰田", "亚洲龙", "AVALON", 2019, 2023, "A25A", "2.5L"),
    ("丰田", "RAV4", "荣放", 2020, 2024, "M20A", "2.0L"),
    ("本田", "雅阁", "第十代雅阁", 2018, 2022, "L15BN", "1.5T"),
    ("大众", "帕萨特", "MQB 帕萨特", 2019, 2023, "EA888", "2.0T"),
    ("雷克萨斯", "ES", "ES200", 2021, 2024, "M20A", "2.0L"),
]

FITMENTS = [
    (1, 1, "前", "前轴套装"), (1, 2, "前", "前轴套装"), (1, 6, "前", "前轴套装"),
    (2, 4, "前", "前轴套装"),
    (3, 1, "发动机舱", "M20A"), (3, 3, "发动机舱", "M20A"),
    (4, 1, "发动机舱", "2.0L"),
    (5, 1, "车内", ""), (5, 2, "车内", ""), (5, 4, "车内", ""), (5, 5, "车内", ""),
    (6, 1, "发动机", ""), (6, 3, "发动机", ""), (6, 4, "发动机", ""), (6, 5, "发动机", ""),
    (7, 1, "发动机舱", ""), (7, 3, "发动机舱", ""), (7, 4, "发动机舱", ""), (7, 5, "发动机舱", ""),
    (8, 3, "后", "后轴左右通用"),
    (9, 1, "左前", "含衬套"),
    (10, 1, "前风挡", ""), (10, 2, "前风挡", ""), (10, 3, "前风挡", ""),
    (10, 4, "前风挡", ""), (10, 5, "前风挡", ""), (10, 6, "前风挡", ""),
    (11, 1, "发动机前端", ""), (11, 3, "发动机前端", ""),
    (12, 1, "冷却系统", ""), (12, 2, "冷却系统", ""), (12, 3, "冷却系统", ""),
    (12, 4, "冷却系统", ""), (12, 5, "冷却系统", ""),
]

PART_NUMBERS = [
    (1, "04465-06120", "OE", "丰田"),
    (1, "04465-06121", "替代号", "丰田"),
    (1, "AN-BP-CAM-F", "供应商编号", "ADVICS"),
    (2, "45022-TVA-A01", "OE", "本田"),
    (3, "04152-31090", "OE", "丰田"),
    (4, "17801-0P050", "OE", "丰田"),
    (5, "CUK-2939", "供应商编号", "MANN"),
    (6, "90919-01253", "OE", "丰田"),
    (7, "570-901-076", "供应商编号", "VARTA"),
    (8, "48530-0R050", "OE", "丰田"),
    (9, "48069-06100", "OE", "丰田"),
    (10, "AeroTwin-A297S", "供应商编号", "BOSCH"),
    (11, "6PK1830", "规格号", "GATES"),
    (12, "G12-4L", "规格号", "BASF"),
]

SUPPLIER_OFFERS = [
    (1, 1, "AN-BP-CAM-F", 268.5, "CNY", 1, 20, 7),
    (2, 1, "HQ-CAM-BRK-01", 255.0, "CNY", 1, 50, 10),
    (3, 1, "DC-BRK-04465", 279.0, "CNY", 1, 10, 5),
    (1, 2, "AN-BP-ACC-F", 238.0, "CNY", 1, 20, 7),
    (4, 2, "LC-ACC-BRK", 229.0, "CNY", 1, 30, 9),
    (3, 3, "DC-OF-M20A", 32.8, "CNY", 1, 100, 4),
    (2, 3, "HQ-OIL-31090", 35.6, "CNY", 1, 80, 6),
    (3, 4, "DC-AF-CAMRY", 78.0, "CNY", 1, 50, 5),
    (3, 5, "DC-CABIN-2939", 96.0, "CNY", 1, 30, 6),
    (2, 6, "HQ-NGK-ILZKR", 68.0, "CNY", 1, 100, 8),
    (5, 6, "QH-SPARK-ILZKR", 65.5, "CNY", 1, 80, 10),
    (5, 7, "QH-VARTA-H6", 680.0, "CNY", 1, 5, 12),
    (4, 8, "LC-KYB-RAV4-R", 520.0, "CNY", 1, 10, 14),
    (4, 9, "LC-ARM-CAM-LF", 430.0, "CNY", 1, 10, 15),
    (5, 10, "QH-BOSCH-2418", 98.0, "CNY", 1, 20, 7),
    (2, 11, "HQ-GATES-6PK", 135.0, "CNY", 1, 30, 10),
    (3, 12, "DC-G12-4L", 88.0, "CNY", 1, 40, 6),
]

# (part_id, current, safety, reserved, warehouse, bin, batch)
INVENTORY = [
    (1, 45, 80, 12, "华东中心仓", "A-01-03", "BP20261101"),
    (2, 24, 60, 8, "华南区域仓", "B-02-01", "BP20261103"),
    (3, 260, 200, 30, "华东中心仓", "F-01-08", "OF20261102"),
    (4, 96, 120, 15, "华东中心仓", "F-02-01", "AF20261028"),
    (5, 42, 100, 6, "华南区域仓", "C-01-05", "CF20261101"),
    (6, 520, 300, 50, "华东中心仓", "E-03-02", "SP20261020"),
    (7, 18, 20, 2, "华北区域仓", "BAT-01", "BT20261101"),
    (8, 36, 30, 4, "华东中心仓", "S-04-01", "SH20261025"),
    (9, 12, 20, 3, "华东中心仓", "A-06-04", "ARM20261101"),
    (10, 140, 80, 10, "华南区域仓", "W-01-02", "WP20261102"),
    (11, 72, 60, 8, "华东中心仓", "E-02-06", "BLT20261030"),
    (12, 210, 120, 20, "华北区域仓", "L-01-03", "CL20261101"),
]

# (order_number, supplier_id, total, status, currency, tax, expected, remark,
#  order_time, [(part_id, quantity, unit_price, required_date, remark)])
ORDERS = [
    ("PO20261110001", 1, 5360.0, 1, "CNY", 1, "2026-11-20", "制动系统月度补货",
     "2026-11-10 09:20:00", [(1, 20, 268.0, "2026-11-20", "")]),
    ("PO20261112002", 3, 6560.0, 0, "CNY", 1, "2026-11-24", "保养耗材安全库存补充",
     "2026-11-12 14:10:00", [(3, 100, 32.8, "2026-11-24", ""), (4, 50, 65.6, "2026-11-24", "")]),
    ("PO20261113003", 4, 5200.0, 2, "CNY", 1, "2026-11-18", "RAV4 后减震器补货",
     "2026-11-13 10:30:00", [(8, 10, 520.0, "2026-11-18", "")]),
    ("PO20261114004", 2, 4080.0, 3, "CNY", 1, "2026-11-16", "点火系统备货",
     "2026-11-14 16:45:00", [(6, 60, 68.0, "2026-11-16", "")]),
    ("PO20261115005", 5, 3400.0, 0, "CNY", 1, "2026-11-26", "AGM 蓄电池采购",
     "2026-11-15 11:15:00", [(7, 5, 680.0, "2026-11-26", "")]),
]

# (order_id, invoice_no, supplier_id, invoice_date, due_date, amount, paid_amount, status)
FINANCE_INVOICES = [
    (1, "INV-2026-11001", 1, "2026-11-11", "2026-12-11", 5360.0, 5360.0, "已付款"),
    (2, "INV-2026-11002", 3, "2026-11-13", "2026-12-13", 6560.0, 2000.0, "部分付款"),
    (3, "INV-2026-11003", 4, "2026-11-14", "2026-12-14", 5200.0, 0.0, "未付款"),
    (4, "INV-2026-11004", 2, "2026-11-15", "2026-12-15", 4080.0, 4080.0, "已付款"),
]

# (period, category, budget_amount)
BUDGETS = [
    ("2026-11", "制动系统", 12000.0),
    ("2026-11", "保养耗材", 15000.0),
    ("2026-11", "点火系统", 10000.0),
    ("2026-11", "悬挂系统", 8000.0),
    ("2026-11", "电气系统", 10000.0),
    ("2026-11", "过滤系统", 9000.0),
]


def _seed_finance_data(conn: sqlite3.Connection) -> None:
    if conn.execute("SELECT COUNT(*) FROM finance_invoice").fetchone()[0] == 0:
        conn.executemany(
            """INSERT INTO finance_invoice
               (order_id, invoice_no, supplier_id, invoice_date, due_date,
                amount, paid_amount, status)
               VALUES (?,?,?,?,?,?,?,?)""",
            FINANCE_INVOICES,
        )
    if conn.execute("SELECT COUNT(*) FROM budget").fetchone()[0] == 0:
        conn.executemany(
            "INSERT INTO budget (period, category, budget_amount) VALUES (?,?,?)",
            BUDGETS,
        )


def get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(force: bool = False) -> str:
    """Create the schema and seed the automotive demo data."""
    if force and DB_PATH.exists():
        DB_PATH.unlink()

    conn = get_conn()
    try:
        conn.executescript(SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM supplier").fetchone()[0] != 0:
            _seed_finance_data(conn)
            conn.commit()
            return str(DB_PATH)

        conn.executemany(
            """INSERT INTO supplier
               (supplier_code, name, contact_person, phone, email, address,
                credit_rating, on_time_rate, quality_ppm, monthly_capacity, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            SUPPLIERS,
        )
        conn.executemany(
            """INSERT INTO part
               (part_code, name, category, model, specification, unit,
                purchase_price, suggested_retail_price, stock_warning_value,
                supplier_id, brand, position, origin_type, warranty_months, description)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            PARTS,
        )
        conn.executemany(
            """INSERT INTO vehicle_model
               (brand, series, model_name, year_start, year_end, engine, displacement)
               VALUES (?,?,?,?,?,?,?)""",
            VEHICLES,
        )
        conn.executemany(
            "INSERT INTO part_fitment (part_id, vehicle_model_id, position, note) VALUES (?,?,?,?)",
            FITMENTS,
        )
        conn.executemany(
            """INSERT INTO part_number (part_id, number, number_type, brand)
               VALUES (?,?,?,?)""",
            PART_NUMBERS,
        )
        conn.executemany(
            """INSERT INTO supplier_offer
               (supplier_id, part_id, supplier_part_no, purchase_price, currency,
                tax_included, moq, lead_time_days, valid_from)
               VALUES (?,?,?,?,?,?,?,?,'2026-01-01')""",
            SUPPLIER_OFFERS,
        )
        conn.executemany(
            """INSERT INTO inventory
               (part_id, current_quantity, safety_stock, reserved_quantity,
                warehouse_location, bin_location, batch_number, updated_at)
               VALUES (?,?,?,?,?,?,?,'2026-11-18 08:00:00')""",
            INVENTORY,
        )
        for order in ORDERS:
            order_no, supplier_id, total, status, currency, tax, expected, remark, order_time, details = order
            cur = conn.execute(
                """INSERT INTO purchase_order
                   (order_number, supplier_id, total_amount, status, currency,
                    tax_included, expected_date, remark, order_time)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (order_no, supplier_id, total, status, currency, tax, expected, remark, order_time),
            )
            conn.executemany(
                """INSERT INTO purchase_order_detail
                   (order_id, part_id, quantity, unit_price, required_date, remark)
                   VALUES (?,?,?,?,?,?)""",
                [(cur.lastrowid, *detail) for detail in details],
            )
        _seed_finance_data(conn)
        conn.commit()
    finally:
        conn.close()
    return str(DB_PATH)


if __name__ == "__main__":
    print("Automotive ERP database initialized:", init_db(force=True))
