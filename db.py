import os  # environment variable parhne ke liye
import sqlite3  # python ka built-in database

DEFAULT_PATH = "trade_desk.db"  # default database file ka naam


def get_connection(path=None):
    """Open a SQLite connection. Path comes from argument or DB_PATH env."""
    path = path or os.getenv("DB_PATH", DEFAULT_PATH)  # path chuno
    conn = sqlite3.connect(path)  # database kholo
    conn.row_factory = sqlite3.Row  # rows ko dict jaisa banao
    return conn  # connection wapas karo


def init_db(conn):
    """Create all tables if they do not exist."""
    conn.executescript(  # kai SQL commands ek sath
        """
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY, name TEXT, category TEXT, unit TEXT,
            price REAL, stock INTEGER, lead_time_days INTEGER);
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY, name TEXT, company TEXT,
            email TEXT UNIQUE, phone TEXT);
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY, customer_id INTEGER,
            status TEXT, eta TEXT);
        CREATE TABLE IF NOT EXISTS handoffs (
            id INTEGER PRIMARY KEY AUTOINCREMENT, customer_name TEXT,
            contact TEXT, request_summary TEXT,
            status TEXT DEFAULT 'open', created_at TEXT);
        """
    )
    conn.commit()  # tabdeeli save karo


def seed_db(conn):
    """Insert SAMPLE data (replace with real company data later)."""
    count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]  # kitne products hain
    if count > 0:  # agar pehle se data hai
        return  # dobara seed mat karo
    products = [  # sample products: sku, name, category, unit, price, stock, lead_time
        ("CAB-4MM", "Solar DC Cable 4mm", "cable", "meter", 0.9, 5000, 3),
        ("CAB-6MM", "Solar DC Cable 6mm", "cable", "meter", 1.4, 12, 7),
        ("INV-5K", "Hybrid Inverter 5kW", "inverter", "piece", 650, 25, 5),
        ("INV-10K", "Hybrid Inverter 10kW", "inverter", "piece", 1100, 0, 14),
        ("BRK-32A", "MCB Breaker 32A", "breaker", "piece", 6, 300, 2),
        ("BRK-63A", "MCB Breaker 63A", "breaker", "piece", 9, 8, 2),
        ("PNL-550", "Solar Panel 550W", "solar panel", "piece", 110, 400, 4),
        ("PNL-600", "Solar Panel 600W", "solar panel", "piece", 125, 150, 4),
    ]
    conn.executemany("INSERT INTO products VALUES (?,?,?,?,?,?,?)", products)  # products daalo
    customers = [  # sample customers
        (1, "Ali", "Ali Traders", "ali@example.com", "03001234567"),
        (2, "Sara", "Sara Solar", "sara@example.com", "03007654321"),
        (3, "Usman", "Usman EPC", "usman@example.com", "03111234567"),
    ]
    conn.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)  # customers daalo
    orders = [  # sample orders
        ("PO-1001", 1, "Shipped", "2026-12-01"),
        ("PO-1002", 2, "Processing", "2026-12-10"),
        ("PO-1003", 3, "Delivered", "2026-11-15"),
    ]
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?)", orders)  # orders daalo
    conn.commit()  # sab save karo
