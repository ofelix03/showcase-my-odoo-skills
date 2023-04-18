from datetime import date

from odoo.tests.common import tagged

from ..models.sale_order import SaleOrder
from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class SaleOrderTransactionCase(TestCommon):
    def test001_sale_order_confirm(self):
        """Test asset creation.
        This tests the creation and confirmation of a sale order record.
        """

        rec_sale_order = self.model_sale_order.create(
            {
                "partner_id": self.partner1.id,
                "company_id": self.env.company.id,
                "date_order": date(2021, 4, 21),
                "payment_term_id": self.payment_term.id,
                "cust_order_no": "ORDER001",
                "truck_no": "TRUCK-001",
                "amount_total": 500.0,
                "state": "draft",
                "origin": "ORIGIN001",
                "load_id": self.rec_order_load_1.id,
            }
        )

        self.assertIsInstance(
            rec_sale_order, SaleOrder, "Object is not an instance of sale order"
        )

        # confirmation of sale order
        rec_sale_order.action_confirm()

        self.assertEqual(
            rec_sale_order.state, "sale", "Sale order not confirmed to sale state"
        )
