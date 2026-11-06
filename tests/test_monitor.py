import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from monitor import interpret_html, evaluate, StockSignal

P = {"id": "test", "name": "Pokemon test ETB", "url": "https://example.org/products/test"}

class MonitorTests(unittest.TestCase):
    def test_purchase_button_in_product_form(self):
        html = '<main><h1>Pokemon test ETB</h1><form action="/cart/add"><button>Add to cart</button></form></main>'
        self.assertEqual(interpret_html(html).state, "IN_STOCK")

    def test_sold_out(self):
        self.assertEqual(interpret_html('<main><h1>ETB</h1><p>Out of stock</p></main>').state, "OUT_OF_STOCK")

    def test_gate_takes_priority(self):
        html = '<main><p>Bot Protected By Gate Keeper</p><form action="/cart/add"><button>Add to cart</button></form></main>'
        self.assertEqual(interpret_html(html).state, "ACCESS_RESTRICTED")

    def test_no_product_form_means_unknown(self):
        self.assertEqual(interpret_html('<main><button>Add to cart</button></main>').state, "UNKNOWN")

    def test_two_confirmations_then_urgent_once(self):
        e = {}
        now = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)
        with patch("monitor.send", return_value=True) as fake_send:
            evaluate(P, e, StockSignal("IN_STOCK", "button"), now)
            self.assertEqual(fake_send.call_count, 0)
            evaluate(P, e, StockSignal("IN_STOCK", "button"), now)
            self.assertEqual(fake_send.call_count, 1)
            self.assertIn("URGENT", str(fake_send.call_args[0][0]["Subject"]))
            evaluate(P, e, StockSignal("IN_STOCK", "button"), now)
            self.assertEqual(fake_send.call_count, 1)

    def test_restock_triggers_again_after_two_outages(self):
        e = {}
        now = datetime(2026, 11, 6, 20, 0, tzinfo=timezone.utc)
        with patch("monitor.send", return_value=True) as fake_send:
            evaluate(P, e, StockSignal("IN_STOCK", ""), now)
            evaluate(P, e, StockSignal("IN_STOCK", ""), now)
            evaluate(P, e, StockSignal("OUT_OF_STOCK", ""), now)
            evaluate(P, e, StockSignal("OUT_OF_STOCK", ""), now)
            later = datetime(2026, 11, 6, 21, 0, tzinfo=timezone.utc)
            evaluate(P, e, StockSignal("IN_STOCK", ""), later)
            evaluate(P, e, StockSignal("IN_STOCK", ""), later)
            self.assertEqual(fake_send.call_count, 2)

    def test_access_error_does_not_reset_stock(self):
        e = {"known_stock": True}
        evaluate(P, e, StockSignal("ACCESS_RESTRICTED", "403"), datetime.now(timezone.utc))
        self.assertIs(e["known_stock"], True)

if __name__ == "__main__":
    unittest.main()
