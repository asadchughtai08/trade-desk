from datetime import datetime, timezone  # handoff ka waqt likhne ke liye

LIMITED_STOCK_AT = 20  # is se kam ya barabar stock = "Limited"
ORDER_ERROR = "Order not found or email does not match"  # dono galtiyon ka ek hi message (no leak)


def stock_words(stock, quantity=1):
    """Convert a stock number into words. Exact numbers are never shown."""
    if stock <= 0:  # stock khatam
        return "Out of stock"  # lafz mein batao
    if stock < quantity:  # maangi hui quantity se kam hai
        return "Partly available"  # lafz mein batao
    if stock <= LIMITED_STOCK_AT:  # thora stock
        return "Limited stock"  # lafz mein batao
    return "In stock"  # warna theek hai


def search_products(conn, query, limit=5):
    """Search products by name or category. No prices, stock only in words."""
    query = str(query).strip().lower()[:100]  # query saaf karo aur chhota rakho
    words = [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in query.split()]  # plural hatao: cables -> cable
    if not words:  # agar kuch nahi likha
        return {"error": "Please tell me which product you are looking for"}  # error wapas
    limit = max(1, min(int(limit), 10))  # limit 1 se 10 ke beech rakho
    sql = "SELECT sku, name, category, unit, stock FROM products WHERE 1=1"  # base query
    params = []  # values yahan jayengi (SQL injection se bachao)
    for w in words:  # har lafz ke liye
        sql += " AND (lower(name) LIKE ? OR lower(category) LIKE ?)"  # name ya category mein dhoondo
        params += [f"%{w}%", f"%{w}%"]  # dono jagah wohi lafz
    sql += " LIMIT ?"  # limit lagao
    params.append(limit)  # limit ki value
    rows = conn.execute(sql, params).fetchall()  # query chalao
    if not rows:  # kuch nahi mila
        return {"error": "No matching products found"}  # error wapas
    products = []  # result list
    for r in rows:  # har row ke liye
        products.append({"sku": r["sku"], "name": r["name"], "category": r["category"],
                         "unit": r["unit"], "availability": stock_words(r["stock"])})  # price aur number nahi
    return {"count": len(products), "products": products}  # result wapas


def check_stock(conn, sku, quantity=1):
    """Check availability of one product by SKU. Returns words, not numbers."""
    try:  # quantity number honi chahiye
        quantity = int(quantity)  # number banao
    except (TypeError, ValueError):  # agar number nahi
        return {"error": "Quantity must be a number"}  # error wapas
    if quantity < 1:  # 0 ya minus quantity
        return {"error": "Quantity must be at least 1"}  # error wapas
    row = conn.execute("SELECT * FROM products WHERE sku = ?", (str(sku).strip().upper(),)).fetchone()  # product dhoondo
    if row is None:  # product nahi mila
        return {"error": "Product not found"}  # error wapas
    return {"sku": row["sku"], "name": row["name"], "unit": row["unit"],
            "availability": stock_words(row["stock"], quantity),
            "lead_time_days": row["lead_time_days"]}  # lafzon mein jawab


def get_order_status(conn, order_id, customer_email):
    """Return order status only if order ID and registered email both match."""
    order_id = str(order_id).strip().upper()  # order id saaf karo
    email = str(customer_email).strip().lower()  # email saaf karo
    row = conn.execute(
        "SELECT o.order_id, o.status, o.eta FROM orders o "
        "JOIN customers c ON c.id = o.customer_id "
        "WHERE o.order_id = ? AND lower(c.email) = ?", (order_id, email)).fetchone()  # dono match hon
    if row is None:  # galat order ya galat email
        return {"error": ORDER_ERROR}  # ek hi error (koi information leak nahi)
    return {"order_id": row["order_id"], "status": row["status"], "eta": row["eta"]}  # status wapas


def request_sales_rep(conn, customer_name, contact, request_summary):
    """Create a handoff for a human sales rep. Same open request returns same reference."""
    name = str(customer_name).strip()  # naam saaf karo
    contact = str(contact).strip()  # contact saaf karo
    summary = str(request_summary).strip()  # summary saaf karo
    if not name or not contact or not summary:  # koi cheez khali hai
        return {"error": "Name, contact and request summary are all required"}  # error wapas
    old = conn.execute(
        "SELECT id FROM handoffs WHERE contact = ? AND request_summary = ? AND status = 'open'",
        (contact, summary)).fetchone()  # kya pehle se open request hai
    if old:  # haan hai
        return {"reference": f"HO-{old['id']}", "status": "open", "already_open": True,
                "message": "A sales rep request is already open for this"}  # wohi reference
    now = datetime.now(timezone.utc).isoformat()  # abhi ka waqt
    cur = conn.execute(
        "INSERT INTO handoffs (customer_name, contact, request_summary, created_at) VALUES (?,?,?,?)",
        (name, contact, summary, now))  # nayi request likho
    conn.commit()  # save karo
    return {"reference": f"HO-{cur.lastrowid}", "status": "open", "already_open": False,
            "message": "A sales rep will contact you soon"}  # naya reference


# ---- neeche ke functions sirf sales reps ke liye hain (API se), agent ke tools nahi ----

def list_handoffs(conn, status="open"):
    """List handoffs for sales reps. status: open, claimed, closed or all."""
    if status not in ("open", "claimed", "closed", "all"):  # galat status
        return {"error": "Invalid status"}  # error wapas
    if status == "all":  # sab chahiye
        rows = conn.execute("SELECT * FROM handoffs ORDER BY id").fetchall()  # sab lo
    else:  # ek status chahiye
        rows = conn.execute("SELECT * FROM handoffs WHERE status = ? ORDER BY id", (status,)).fetchall()  # filter
    return {"handoffs": [dict(r) for r in rows]}  # dict mein badal kar do


def _change_status(conn, handoff_id, allowed_from, new_status):
    """Move a handoff to a new status if its current status is allowed."""
    row = conn.execute("SELECT status FROM handoffs WHERE id = ?", (handoff_id,)).fetchone()  # handoff dhoondo
    if row is None:  # nahi mila
        return {"error": "Handoff not found"}  # error wapas
    if row["status"] not in allowed_from:  # status ijazat wala nahi
        return {"error": f"Handoff is already {row['status']}"}  # error wapas
    conn.execute("UPDATE handoffs SET status = ? WHERE id = ?", (new_status, handoff_id))  # status badlo
    conn.commit()  # save karo
    return {"reference": f"HO-{handoff_id}", "status": new_status}  # naya status batao


def claim_handoff(conn, handoff_id):
    """Sales rep takes an open handoff."""
    return _change_status(conn, handoff_id, ("open",), "claimed")  # open se claimed


def close_handoff(conn, handoff_id):
    """Sales rep closes a handoff."""
    return _change_status(conn, handoff_id, ("open", "claimed"), "closed")  # open ya claimed se closed
