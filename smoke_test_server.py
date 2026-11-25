import asyncio  # async main ke liye
import os  # path ke liye
import sys  # python path ke liye
import db  # database
from agents import load_tools  # MCP tools load karne wala function


async def main():
    path = os.path.abspath("smoke_test.db")  # temporary database
    conn = db.get_connection(path)  # kholo
    db.init_db(conn)  # tables
    db.seed_db(conn)  # sample data
    conn.close()  # band karo
    tools = await load_tools(path)  # MCP server chalao aur tools lo
    print("Tools:", [t.name for t in tools])  # tools ke naam
    by_name = {t.name: t for t in tools}  # naam se dhoondo
    print(await by_name["search_products"].ainvoke({"query": "cable"}))  # test 1
    print(await by_name["check_stock"].ainvoke({"sku": "CAB-4MM"}))  # test 2
    print(await by_name["get_order_status"].ainvoke({"order_id": "PO-1001", "customer_email": "ali@example.com"}))  # test 3
    os.remove(path)  # temporary file hatao


asyncio.run(main())  # chalao
