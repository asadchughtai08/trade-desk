import json  # result ko JSON string banane ke liye
import sys  # stderr mein log likhne ke liye
from mcp.server.fastmcp import FastMCP  # MCP server (mcp<2 wala)
import db  # database ka code
import tools  # business logic
from utils import mask_text  # private data chhupane ke liye

mcp = FastMCP("TradeDeskServer")  # server ka naam


def log(message):
    """Write a masked log line to stderr (stdout belongs to MCP)."""
    print(mask_text(message), file=sys.stderr, flush=True)  # sirf stderr


def run(function, *args):
    """Open DB, run one tool function, close DB, return JSON text."""
    conn = db.get_connection()  # database kholo
    try:  # error aaye to bhi band karna hai
        result = function(conn, *args)  # tool chalao
    finally:  # hamesha chalega
        conn.close()  # database band karo
    return json.dumps(result)  # JSON string wapas


@mcp.tool()
def search_products(query: str, limit: int = 5) -> str:
    """Search products by name or category (cable, inverter, breaker, solar panel). Never returns prices."""
    log(f"search_products query={query}")  # log likho
    return run(tools.search_products, query, limit)  # tool chalao


@mcp.tool()
def check_stock(sku: str, quantity: int = 1) -> str:
    """Check availability of one product by its SKU. Returns availability in words and lead time in days."""
    log(f"check_stock sku={sku} quantity={quantity}")  # log likho
    return run(tools.check_stock, sku, quantity)  # tool chalao


@mcp.tool()
def get_order_status(order_id: str, customer_email: str) -> str:
    """Get order status. Needs BOTH the order ID and the email registered on the order."""
    log(f"get_order_status order_id={order_id} email={customer_email}")  # log likho (email masked)
    return run(tools.get_order_status, order_id, customer_email)  # tool chalao


@mcp.tool()
def request_sales_rep(customer_name: str, contact: str, request_summary: str) -> str:
    """Hand the customer to a human sales rep (for quotes, prices, discounts, negotiation). Needs name, contact and a short summary."""
    log(f"request_sales_rep name={customer_name} contact={contact}")  # log likho (contact masked)
    return run(tools.request_sales_rep, customer_name, contact, request_summary)  # tool chalao


if __name__ == "__main__":  # direct chalane par
    _conn = db.get_connection()  # database kholo
    db.init_db(_conn)  # tables pakka bana do
    _conn.close()  # band karo
    mcp.run(transport="stdio")  # server chalao
