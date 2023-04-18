from datetime import datetime

from odoo.tests.common import Form, tagged

from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderResetToDraftTransactionCase(TestCommon):
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

    def single_create_order_reset_to_draft_record(self):
        rec_order_reset_to_draft = self.model_oms_reset_order_to_draft_wizard.create(
            {
                "reset_type": "wrong_quantity",
                "message": "Wrong product quantity",
                "order_id": self.single_create_order_management_record().id,
            }
        )
        return rec_order_reset_to_draft

    def test001_single_create_order_reset_to_draft_with_form_obj(self):
        """Test to simulate user interaction."""
        # Add data to form
        with Form(
            self.model_oms_reset_order_to_draft_wizard
        ) as order_reset_to_draft_form:
            order_reset_to_draft_form.reset_type = "wrong_price"
            order_reset_to_draft_form.message = "Wrong price input"

            rec_order_reset_to_draft = order_reset_to_draft_form.save()
            self.assertEqual(
                rec_order_reset_to_draft.reset_type,
                "wrong_price",
                "Reset type mismatch",
            )
            self.assertEqual(
                rec_order_reset_to_draft.message,
                "Wrong price input",
                "Message  mismatch",
            )

    def test002_reset_order_to_draft(self):
        rec_order_reset_to_draft = self.single_create_order_reset_to_draft_record()

        # Reset order to draft
        rec_order_reset_to_draft.reset_to_draft()
        self.assertEqual(
            rec_order_reset_to_draft.reset_type, "wrong_quantity", "Reset type mismatch"
        )
