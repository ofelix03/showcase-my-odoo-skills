from datetime import datetime

from odoo.tests.common import Form, tagged

from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderCancelWizardTransactionCase(TestCommon):
    def single_create_order_management_record(self):
        rec_order = self.model_order_management.create(
            {
                "datetime": datetime.today(),
                "partner_id": self.partner1.id,
                "order_type": "regular",
                "product_id": self.product_1.id,
                "warehouse_id": self.warehouse.id,
                "loading_truck_number": "TRUCK001",
                "quantity": 6.0,
                "product_uom_id": self.rec_product_uom.id,
                "currency_id": self.currency.id,
                "proposed_price": 120.0,
                "payment_term_id": self.payment_term.id,
                "state": "draft",
            }
        )
        return rec_order

    def single_create_order_cancel_wizard_record(self):
        rec_order_cancel = self.model_oms_cancel_order_wizard.create(
            {
                "reason": "Customer cancelled order",
                "order_management_id": self.single_create_order_management_record().id,
            }
        )
        return rec_order_cancel

    def test001_single_create_order_cancel_with_form_obj(self):
        """Test to simulate user interaction."""
        # Add data to form
        with Form(self.model_oms_cancel_order_wizard) as order_cancel_form:
            order_cancel_form.reason = "Customer exceeds credit limit"

            order_cancel_form = order_cancel_form.save()
            self.assertEqual(
                order_cancel_form.reason,
                "Customer exceeds credit limit",
                "Reason mismatch",
            )

    def test002_btn_cancel_order(self):
        rec_order_cancel_wizard = self.single_create_order_cancel_wizard_record()

        rec_order_cancel_wizard.with_user(
            self.res_users_marketing_user
        ).btn_do_cancel_order()
        self.assertEqual(
            rec_order_cancel_wizard.order_management_id.state,
            "cancel",
            "Order state mismatch",
        )
