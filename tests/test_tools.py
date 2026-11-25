import json  # result check karne ke liye
import unittest  # python ka test framework
import db  # database
import tools  # business logic
from utils import mask_text  # masking


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.get_connection(":memory:")  # har test ke liye naya khali database
        db.init_db(self.conn)  # tables banao
        db.seed_db(self.conn)  # sample data daalo

    def test_seed_runs_once(self):
        db.seed_db(self.conn)  # dobara seed
        count = self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]  # gino
        self.assertEqual(count, 8)  # ab bhi 8 hone chahiye

    def test_search_finds_cable(self):
        result = tools.search_products(self.conn, "cable")  # cable dhoondo
        self.assertEqual(result["count"], 2)  # 4mm aur 6mm

    def test_search_plural_and_two_words(self):
        result = tools.search_products(self.conn, "6mm cables")  # plural aur 2 lafz
        self.assertEqual(result["products"][0]["sku"], "CAB-6MM")  # 6mm cable mile

    def test_search_no_match(self):
        self.assertIn("error", tools.search_products(self.conn, "laptop"))  # error aaye

    def test_search_empty_query(self):
        self.assertIn("error", tools.search_products(self.conn, "   "))  # error aaye

    def test_search_never_shows_price_or_number(self):
        text = json.dumps(tools.search_products(self.conn, "panel"))  # result text
        self.assertNotIn("price", text)  # price nahi
        self.assertNotIn('"stock"', text)  # stock number nahi

    def test_stock_words(self):
        self.assertEqual(tools.stock_words(0), "Out of stock")  # zero
        self.assertEqual(tools.stock_words(10), "Limited stock")  # thora
        self.assertEqual(tools.stock_words(500), "In stock")  # bohat
        self.assertEqual(tools.stock_words(10, 50), "Partly available")  # quantity zyada

    def test_check_stock_ok(self):
        result = tools.check_stock(self.conn, "inv-10k")  # chhote harf bhi chalen
        self.assertEqual(result["availability"], "Out of stock")  # stock 0 hai
        self.assertNotIn("stock", result)  # number wali key nahi

    def test_check_stock_quantity(self):
        result = tools.check_stock(self.conn, "BRK-63A", 50)  # 8 hain, 50 chahiye
        self.assertEqual(result["availability"], "Partly available")  # lafz

    def test_check_stock_errors(self):
        self.assertIn("error", tools.check_stock(self.conn, "NOPE"))  # galat sku
        self.assertIn("error", tools.check_stock(self.conn, "CAB-4MM", 0))  # zero quantity
        self.assertIn("error", tools.check_stock(self.conn, "CAB-4MM", "abc"))  # text quantity

    def test_order_ok(self):
        result = tools.get_order_status(self.conn, "po-1001", "ALI@example.com")  # case ka farq nahi
        self.assertEqual(result["status"], "Shipped")  # sahi status

    def test_order_wrong_email_and_missing_order_same_error(self):
        wrong_email = tools.get_order_status(self.conn, "PO-1001", "sara@example.com")  # galat email
        missing = tools.get_order_status(self.conn, "PO-9999", "ali@example.com")  # order hai hi nahi
        self.assertEqual(wrong_email, missing)  # bilkul same error

    def test_handoff_creates(self):
        result = tools.request_sales_rep(self.conn, "Ali", "0300", "Quote for 100 panels")  # nayi request
        self.assertEqual(result["reference"], "HO-1")  # pehla reference

    def test_handoff_idempotent(self):
        a = tools.request_sales_rep(self.conn, "Ali", "0300", "Quote")  # pehli baar
        b = tools.request_sales_rep(self.conn, "Ali", "0300", "Quote")  # dobara wohi
        self.assertEqual(a["reference"], b["reference"])  # same reference
        self.assertTrue(b["already_open"])  # batao ke pehle se open hai

    def test_handoff_new_after_close(self):
        a = tools.request_sales_rep(self.conn, "Ali", "0300", "Quote")  # pehli
        tools.close_handoff(self.conn, 1)  # band karo
        b = tools.request_sales_rep(self.conn, "Ali", "0300", "Quote")  # wohi dobara
        self.assertNotEqual(a["reference"], b["reference"])  # ab nayi bani

    def test_handoff_needs_all_fields(self):
        self.assertIn("error", tools.request_sales_rep(self.conn, "Ali", "", "Quote"))  # contact khali

    def test_claim_and_close_flow(self):
        tools.request_sales_rep(self.conn, "Ali", "0300", "Quote")  # request banao
        self.assertEqual(tools.claim_handoff(self.conn, 1)["status"], "claimed")  # claim
        self.assertIn("error", tools.claim_handoff(self.conn, 1))  # dobara claim nahi
        self.assertEqual(tools.close_handoff(self.conn, 1)["status"], "closed")  # close
        self.assertIn("error", tools.close_handoff(self.conn, 99))  # nahi mila

    def test_list_handoffs(self):
        tools.request_sales_rep(self.conn, "Ali", "0300", "Quote")  # request banao
        self.assertEqual(len(tools.list_handoffs(self.conn)["handoffs"]), 1)  # 1 open
        self.assertIn("error", tools.list_handoffs(self.conn, "bad"))  # galat status

    def test_mask_text(self):
        masked = mask_text("mail ali@example.com phone 03001234567")  # masking
        self.assertNotIn("ali@", masked)  # email chhup gayi
        self.assertNotIn("0300123", masked)  # phone chhup gaya


if __name__ == "__main__":  # direct chalane par
    unittest.main()  # tests chalao
