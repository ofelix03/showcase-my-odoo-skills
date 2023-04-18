from datetime import datetime

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderLoadWizardTransactionCase(TestCommon):
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

    def single_create_order_load_wizard_record(self):
        rec_order_load = self.model_oms_load_order_wizard.create(
            {
                "load_datetime": datetime.now(),
                "loaded_quantity": 16.0,
                "warehouse_id": self.warehouse.id,
                "customer_order_number": "ORDER-10",
                "truck_number": "GR 12 Y",
                "waybill": self.get_sample_waybill_bs64encoded(),
                "waybill_number": "WAYBILL-001",
                "order_sheet": self.get_sample_waybill_bs64encoded(),
                "order_type": "regular",
                "order_management_id": self.single_create_order_management_record().id,
            }
        )
        return rec_order_load

    def test001_order_load_wizard_with_negative_loaded_quantity_value(self):
        with self.assertRaises(ValidationError):
            rec_order_load_wizard = self.single_create_order_load_wizard_record()
            rec_order_load_wizard.with_user(self.res_users_operations_user).write(
                {"loaded_quantity": -140.0}
            )

    def test002_submit_regular_load_with_loaded_quantity_gt_order_outstanding_quantity(
        self,
    ):
        with self.assertRaises(ValidationError):
            rec_order_load = self.single_create_order_load_wizard_record()

            rec_order_load.order_management_id.with_user(
                self.res_users_operations_user
            ).write({"outstanding_quantity": 10.0})
            rec_order_load.with_user(self.res_users_operations_user).btn_do_loaded()

    def test003_generate_load_name(self):
        rec_order_load = self.single_create_order_load_wizard_record()

        rec_order_load.with_user(self.res_users_operations_user)._generate_load_name()

    def test004_onchange_order_management(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"outstanding_quantity": 12.0})

        rec_order_load.with_user(
            self.res_users_operations_user
        ).onchange_order_management()
        self.assertEqual(
            rec_order_load.loaded_quantity, 12.0, "Loaded quantity mismatch"
        )

    def test006_update_order_in_approved_state(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        order = rec_order_load.order_management_id
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"state": "approve"})

        rec_order_load.with_user(self.res_users_operations_user)._update_order(
            order.loaded_quantity
        )
        self.assertEqual(order.state, "loading", "Related order state not in loading")
        self.assertEqual(
            order.loading_state, "loading", "Related order loading state not in loading"
        )

    def test007_update_order_in_loading_state(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        order = rec_order_load.order_management_id
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"state": "loading"})

        rec_order_load.with_user(self.res_users_operations_user)._update_order(
            order.loaded_quantity
        )
        self.assertEqual(order.state, "loading", "Related order state not in loading")
        self.assertEqual(
            order.loading_state, "loading", "Related order loading state not in loading"
        )

    def test009_order_with_bulk_order_type_and_loaded_quantity_gt_outstanding_quantity(
        self,
    ):
        rec_order_load = self.single_create_order_load_wizard_record()
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"outstanding_quantity": 10.0, "order_type": "bulk"})

        rec_order_load.with_user(self.res_users_operations_user)._filter_order_ids()
        self.assertTrue(rec_order_load.show_child_orders, "Show child orders is False")

    def test010_order_with_bulk_order_type_and_zero_loaded_quantity_value(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"order_type": "bulk", "outstanding_quantity": 20.0})

        rec_order_load.with_user(self.res_users_operations_user)._filter_order_ids()
        self.assertFalse(rec_order_load.show_child_orders, "Show child orders is True")

    def test011_compute_validation_checks_on_load_with_greater_loaded_quantity(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"loaded_quantity": 20.0}
        )

        rec_order_load.with_user(
            self.res_users_operations_user
        )._compute_validation_checks()
        self.assertFalse(rec_order_load.quantity_is_available, "Quantity is available")

    def test012_compute_validation_checks_on_load_with_loaded_quantity_equal_outstanding(
        self,
    ):
        rec_order_load = self.single_create_order_load_wizard_record()
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"outstanding_quantity": 16.0})

        rec_order_load.with_user(
            self.res_users_operations_user
        )._compute_validation_checks()
        self.assertEqual(
            rec_order_load.quantity_is_available_message,
            "You have enough stocks to fulfill this load. You can proceed.",
            "Message mismatch",
        )

    def test013_check_quantity_overage_shortage_lesser_outstanding_quantity(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"order_ids": [self.rec_order_1.id]}
        )

        rec_order_load.with_user(
            self.res_users_operations_user
        )._check_quantity_overage_shortage()

    def test014_check_quantity_overage_shortage_greater_outstanding_quantity(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        order_id = self.rec_order_1
        order_id.with_user(self.res_users_operations_user).write(
            {"outstanding_quantity": 15.0}
        )
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"order_ids": [self.rec_order_1.id]}
        )
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"outstanding_quantity": 15.0})

        available_order_outstanding_quantity = (
            rec_order_load._check_quantity_overage_shortage()[1][1]
        )
        rec_order_load.with_user(
            self.res_users_operations_user
        )._check_quantity_overage_shortage()
        self.assertEqual(
            available_order_outstanding_quantity, 1.0, "Outstanding quantity mismatch"
        )

    def test015_btn_do_loaded(self):
        rec_order_load = self.single_create_order_load_wizard_record()
        order_id = self.rec_order_1
        order_id.with_user(self.res_users_operations_user).write(
            {"outstanding_quantity": 15.0}
        )
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"order_ids": [order_id.id]}
        )
        rec_order_load.order_management_id.with_user(
            self.res_users_operations_user
        ).write({"outstanding_quantity": 20.0})

        rec_order_load.btn_do_loaded()
