from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderPricingWizardTransactionCase(TestCommon):
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

    def single_create_price_order_wizard_record(self):
        rec_order_pricing = self.model_oms_price_order_wizard.create(
            {
                "spot_rate": 2.30,
                "forward_rate": 2.50,
                "final_price": 100.0,
                "quantity": 5.0,
                "product_uom_id": self.rec_product_uom.id,
                "maturity_period": 10,
                "margin": 3.0,
                "margin_uom_id": self.rec_product_uom.id,
                "order_management_id": self.single_create_order_management_record().id,
            }
        )
        return rec_order_pricing

    def test001_confirm_wizard(self):
        rec_price_order_wizard = self.single_create_price_order_wizard_record()

        rec_price_order_wizard.with_user(self.res_users_trading_user)._confirm_wizard()
        self.assertEqual(rec_price_order_wizard.quantity, 6.0, "Quantity mismatch")

    def test002_submit_order_pricing_without_existing_order_pricing_record(self):
        rec_price_order_wizard = self.single_create_price_order_wizard_record()

        rec_price_order_wizard.btn_do_submit()
        self.assertEqual(
            rec_price_order_wizard.forward_rate, 2.50, "Forward rate mismatch"
        )

    def test003_submit_order_pricing_with_existing_order_pricing_record(self):
        rec_price_order_wizard = self.single_create_price_order_wizard_record()
        rec_price_order_wizard.with_user(self.res_users_trading_user).write(
            {"order_management_id": self.rec_order_1.id}
        )
        rec_order_pricing = self.rec_order_pricing
        rec_price_order_wizard.btn_do_submit()
        self.assertEqual(rec_order_pricing.forward_rate, 2.50, "Forward rate mismatch")

    def test005_price_order_wizard_with_negative_final_price_value(self):
        with self.assertRaises(ValidationError):
            rec_price_order_wizard = self.single_create_price_order_wizard_record()
            rec_price_order_wizard.with_user(self.res_users_trading_user).write(
                {"final_price": -100.0}
            )

    def test006_price_order_wizard_with_negative_quantity_value(self):
        with self.assertRaises(ValidationError):
            rec_price_order_wizard = self.single_create_price_order_wizard_record()
            rec_price_order_wizard.with_user(self.res_users_trading_user).write(
                {"quantity": -5.0}
            )

    def test007_price_order_wizard_with_negative_maturity_period_value(self):
        with self.assertRaises(ValidationError):
            rec_price_order_wizard = self.single_create_price_order_wizard_record()
            rec_price_order_wizard.with_user(self.res_users_trading_user).write(
                {"maturity_period": -21.0}
            )

    def test008_price_order_wizard_with_negative_spot_rate_value(self):
        with self.assertRaises(ValidationError):
            rec_price_order_wizard = self.single_create_price_order_wizard_record()
            rec_price_order_wizard.with_user(self.res_users_trading_user).write(
                {"spot_rate": -2.4}
            )

    def test009_price_order_wizard_with_negative_forward_rate_value(self):
        with self.assertRaises(ValidationError):
            rec_price_order_wizard = self.single_create_price_order_wizard_record()
            rec_price_order_wizard.with_user(self.res_users_trading_user).write(
                {"forward_rate": -2.6}
            )
