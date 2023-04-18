from datetime import date

from odoo.exceptions import ValidationError
from odoo.tests.common import tagged

from ..models.order_load import OrderLoad
from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderLoadTransactionCase(TestCommon):
    def create_single_order_load(self, has_waybill=True):
        rec_order_load = self.model_oms_order_load.with_user(
            self.res_users_operations_user
        ).create(
            {
                "load_date": date.today(),
                "warehouse_id": self.warehouse.id,
                "customer_order_number": "ORDER001",
                "truck_number": "TRUCK-01",
                "quantity": 7.0,
                "waybill": has_waybill and self.get_sample_waybill_bs64encoded(),
                "waybill_number": "WAYBILL601",
                "no_waybill_reason": not has_waybill and "Waybill is not ready",
                "order_sheet": self.get_sample_waybill_bs64encoded(),
                "hedge_status": "draft",
                "so_state": "draft",
                "order_management_id": self.rec_order_1.id,
            }
        )
        return rec_order_load

    def test001_single_create_order_load(self):
        """Test asset creation.
        This test case confirms the creation of an order load record.
        """

        rec_order_load = self.model_oms_order_load.with_user(
            self.res_users_operations_user
        ).create(
            {
                "load_date": date.today(),
                "warehouse_id": self.warehouse.id,
                "customer_order_number": "ORDER001",
                "truck_number": "TRUCK-01",
                "quantity": 4.0,
                "waybill": self.get_sample_waybill_bs64encoded(),
                "waybill_number": "WAYBILL601",
                "order_sheet": self.get_sample_waybill_bs64encoded(),
                "hedge_status": "draft",
                "so_state": "draft",
                "order_management_id": self.rec_order_1.id,
            }
        )

        self.assertIsInstance(
            rec_order_load, OrderLoad, "Object is not an instance of order load"
        )

    def test002_mark_load_has_validated_so(self):
        rec_order_load = self.create_single_order_load()

        rec_order_load.with_user(
            self.res_users_accounting_user
        ).mark_load_has_validated_so()
        self.assertEqual(
            rec_order_load.so_state, "validated", "Load sale order not validated"
        )

    def test003_mark_load_has_invoiced_so(self):
        rec_order_load = self.create_single_order_load()
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"so_state": "validated"}
        )

        rec_order_load.with_user(
            self.res_users_accounting_user
        ).mark_load_has_invoiced_so()
        self.assertEqual(
            rec_order_load.so_state, "invoiced", "Load sale order not invoiced"
        )

    def test004_compute_hide_related_loads_info(self):
        rec_order_load = self.create_single_order_load()

        rec_order_load.with_user(
            self.res_users_accounting_user
        )._compute_hide_related_loads_info()
        self.assertTrue(
            rec_order_load.hide_related_loads_info, "Hide related loads info is False"
        )

    def test005_launch_wizard_for_load_values_editing(self):
        rec_order_load = self.create_single_order_load()

        rec_order_load.with_user(self.res_users_operations_user).action_edit_load()

    def test006_launch_wizard_for_sale_order_creation(self):
        rec_order_load = self.create_single_order_load()

        rec_order_load.with_user(self.res_users_accounting_user).btn_sale_order_wizard()

    def test007_action_view_created_hedge(self):
        rec_order_load = self.create_single_order_load()

        rec_order_load.with_user(self.res_users_finance_user).write(
            {"hedge_id": self.rec_hedge_1.id}
        )
        rec_order_load.with_user(self.res_users_finance_user).action_view_hedge()

    def test008_action_view_created_sale_order(self):
        rec_order_load = self.create_single_order_load()

        rec_order_load.with_user(self.res_users_accounting_user).write(
            {"sale_order_id": self.sale_order.id}
        )
        rec_order_load.with_user(
            self.res_users_accounting_user
        ).action_view_sale_order()

    def test009_update_order_load_without_waybill_and_no_waybill_reason(self):
        with self.assertRaises(ValidationError):
            rec_order_load = self.create_single_order_load(has_waybill=False)
            rec_order_load.with_user(self.res_users_operations_user).write(
                {"no_waybill_reason": False}
            )

    def test010_update_order_load_with_waybill(self):
        rec_order_load = self.create_single_order_load()

        self.assertEqual(
            rec_order_load.waybill,
            self.get_sample_waybill_bs64encoded(),
            "Waybill is not provided",
        )

    def test010_update_order_load_with_no_waybill_reason(self):
        rec_order_load = self.create_single_order_load(has_waybill=False)

        self.assertEqual(
            rec_order_load.no_waybill_reason,
            "Waybill is not ready",
            "No waybill reason mismatch",
        )
        self.assertFalse(rec_order_load.waybill, "Waybill is provided")

    def test011_update_order_load_with_new_customer_order_number(self):
        rec_order_load = self.create_single_order_load()
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"customer_order_number": "ORDER002"}
        )
        self.assertEqual(
            rec_order_load.customer_order_number,
            "ORDER002",
            "Customer order number mismatch",
        )

    def test012_update_order_load_with_new_truck_number(self):
        rec_order_load = self.create_single_order_load()
        rec_order_load.with_user(self.res_users_operations_user).write(
            {"truck_number": "TRUCK003"}
        )
        self.assertEqual(
            rec_order_load.truck_number,
            "TRUCK003",
            "Truck number mismatch",
        )

    def test013_update_load(self):
        rec_order_load = self.create_single_order_load()
        rec_order_load.write({"so_state": "invoiced"})
