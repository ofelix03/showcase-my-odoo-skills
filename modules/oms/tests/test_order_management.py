from datetime import date, datetime

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import Form, tagged

from ..models.order import Order
from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderTransactionCase(TestCommon):
    def test001_single_create_order(self):
        """Test asset creation.
        This test case confirms the creation of an order management record.
        """

        self.rec_order = self.model_order_management.create(
            {
                "datetime": datetime.today(),
                "partner_id": self.partner1.id,
                "order_type": "regular",
                "product_id": self.product_1.id,
                "warehouse_id": self.warehouse.id,
                "loading_truck_number": "TRUCK002",
                "quantity": 6.0,
                "product_uom_id": self.rec_product_uom.id,
                "currency_id": self.currency.id,
                "proposed_price": 120.0,
                "payment_term_id": self.payment_term.id,
                "state": "draft",
            }
        )

        self.assertIsInstance(
            self.rec_order,
            Order,
            "Object is not an instance of order management",
        )

        self.assertEqual(
            self.rec_order.loading_truck_number,
            "TRUCK002",
            "Order loading truck number does not match",
        )

        # onchange_sos_state method
        self.rec_order.onchange_sos_state()
        self.assertFalse(self.rec_order.state, "Order state is set")

        # mark_sos_as_fully_invoiced method
        self.rec_order.mark_sos_as_fully_invoiced()
        self.assertEqual(
            self.rec_order.state,
            "fully_invoiced_sos",
            "Order state is not in 'Fully Invoiced SOs'",
        )

        # mark_sos_as_partially_invoiced
        self.rec_order.mark_sos_as_partially_invoiced()
        self.assertEqual(
            self.rec_order.state,
            "partially_invoiced_sos",
            "Order state is not in 'Partially Invoiced SOs'",
        )

        # mark_sos_as_fully_validated
        self.rec_order.mark_sos_as_fully_validated()
        self.assertEqual(
            self.rec_order.state,
            "fully_validated_sos",
            "Order state is not in 'Fully Validated SOs'",
        )

        # mark_sos_as_partially_validated
        self.rec_order.mark_sos_as_partially_validated()
        self.assertEqual(
            self.rec_order.state,
            "partially_validated_sos",
            "Order state is not in 'Partially Validated SOs'",
        )

    def test002_single_create_order_with_form_obj(self):
        """Test to simulate user interaction."""
        # Add data to form
        with Form(self.model_order_management) as order_form:
            order_form.partner_id = self.partner1
            order_form.datetime = datetime.today()
            order_form.loading_truck_number = "TRUCK003"
            order_form.order_type = "regular"
            order_form.quantity = 130.0
            order_form.product_uom_id = self.rec_product_uom
            order_form.product_id = self.product_1
            order_form.warehouse_id = self.warehouse
            order_form.currency_id = self.currency
            order_form.proposed_price = 112.15
            order_form.payment_term_id = self.payment_term
            order_form.state = "draft"

            order_rec = order_form.save()

            self.assertEqual(
                order_rec.partner_id.name, "John Doe", "Vendor name mismatch"
            )
            partner_name = order_rec.partner_id.mapped("name")[0]
            self.assertEqual(partner_name, self.partner1.name, "Vendor name mismatch")

    def test003_order_with_future_date_time(self):
        with self.assertRaises(ValidationError):
            self.rec_order_1.with_user(self.res_users_marketing_user).write(
                {"datetime": datetime(2030, 5, 5, 12, 10, 10)}
            )

    def test004_order_with_quantity_as_zero(self):
        with self.assertRaises(ValidationError):
            self.rec_order_1.with_user(self.res_users_marketing_user).write(
                {"quantity": 0.0}
            )

    def test005_order_partner_name_has_lpg_word(self):
        order = self.model_order_management.create(
            {
                "datetime": datetime.today(),
                "partner_id": self.partner2.id,
                "order_type": "regular",
                "product_id": self.product_1.id,
                "warehouse_id": self.warehouse.id,
                "loading_truck_number": "TRUCK005",
                "quantity": 6.0,
                "product_uom_id": self.rec_product_uom.id,
                "currency_id": self.currency.id,
                "proposed_price": 120.0,
                "payment_term_id": self.payment_term.id,
                "state": "draft",
            }
        )
        order.onchange_partner()
        self.assertTrue(order.partner_id, "Order partner name does not contain LPG")

    def test006_get_order_form_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        order = self.rec_order_1
        form_url = order.get_form_url()
        self.assertEqual(
            form_url,
            (base_url + "/web#id=%d&view_type=form&model=%s" % (order.id, order._name)),
            "Order form url mismatch",
        )

    # def test007_name_get(self):
    #     order = self.rec_order_1
    #     order.name_get()
    #     self.assertEqual(
    #         order.name_get()[0][1],
    #         (order.reference + " (6.0, 0.0)"),
    #         "Order name mismatch",
    #     )

    def test008_order_in_draft_state_unlink(self):
        order = self.rec_order_1
        order.unlink()
        self.assertIsInstance(order, Order, "Order is an instance of order management")

    def test009_order_in_loaded_state_unlink(self):
        with self.assertRaises(UserError):
            self.rec_order_1.with_user(self.res_users_marketing_user).write(
                {"state": "load"}
            )
            self.rec_order_1.unlink()

    def test010_update_unexisting_order(self):
        order = self.rec_order_1
        order.with_user(self.res_users_marketing_user).write({})

    def test011_get_app_email(self):
        order = self.rec_order_1
        email = order._get_app_email()
        self.assertEqual(email, "apps@quantumgroupgh.com", "App email mismatch")

    def test012_order_loading(self):
        order = self.rec_order_1
        order.btn_do_loading()
        self.assertEqual(order.state, "loading", "Order state not in loading")
        self.assertEqual(
            order.loading_state, "loading", "Order loading state not loading"
        )

    def test013_order_with_unhedged_load(self):
        order = self.rec_order_1
        self.rec_order_load_1.with_user(self.res_users_accounting_user).write(
            {"hedge_id": self.rec_hedge_1.id}
        )
        order._all_have_hedge(order.order_loading_ids)

    def test014_order_with_all_hedged_load(self):
        order = self.rec_order_1
        self.rec_order_load_1.with_user(self.res_users_accounting_user).write(
            {"hedge_id": self.rec_hedge_1.id}
        )
        self.rec_order_load_2.with_user(self.res_users_accounting_user).write(
            {"hedge_id": self.rec_hedge_1.id, "hedge_status": "hedge"}
        )
        order._all_have_hedge(order.order_loading_ids)

    def test016_get_user_emails_with_group_name(self):
        order = self.rec_order_1
        order.get_user_emails(group_name="group_credit_control_user")

    def test017_get_user_emails_without_group_name(self):
        order = self.rec_order_1
        order.get_user_emails(group_name=None)

    def test018_run_recompute_orders_invoiced_amounts(self):
        order = self.rec_order_1
        order.with_user(self.res_users_accounting_user).write(
            {
                "order_hedge_ids": [self.rec_hedge_1.id],
                "sale_order_ids": [self.sale_order.id, self.sale_order_1.id],
            }
        )
        self.rec_order_load_2.with_user(self.res_users_accounting_user).write(
            {
                "sale_order_id": self.sale_order_line_1.id,
                "hedge_status": "hedge",
                "hedge_id": self.rec_hedge_1.id,
            }
        )
        order.run_recompute_orders_invoiced_amounts()

    def test020_update_state_of_order_with_all_loads_hedged(self):
        order = self.rec_order_1
        order.with_user(self.res_users_accounting_user).write(
            {
                "order_hedge_ids": [self.rec_hedge_1.id],
                "sale_order_ids": [self.sale_order.id],
            }
        )
        order.update_hedge_state()
        self.assertEqual(order.state, "hedge", "Order state is not hedge")

    def test021_update_state_of_order_without_all_loads_hedged(self):
        order = self.rec_order_1
        order.with_user(self.res_users_accounting_user).write(
            {
                "order_hedge_ids": [self.rec_hedge_1.id],
                "sale_order_ids": [self.sale_order.id, self.sale_order_1.id],
            }
        )
        order.update_hedge_state()
        self.assertEqual(
            order.state, "partially_hedged", "Order state is not partially hedge"
        )

    def test022_update_state_of_order_with_all_load_sos_invoiced(self):
        order = self.rec_order_1
        order_load_1 = self.rec_order_load_1
        order_load_2 = self.rec_order_load_2
        order_load_1.with_user(self.res_users_accounting_user).write(
            {"so_state": "invoiced"}
        )
        order_load_2.with_user(self.res_users_accounting_user).write(
            {"so_state": "invoiced"}
        )

        order.update_sos_state()
        self.assertEqual(
            order.state, "fully_invoiced_sos", "Order state in partially invoiced sos"
        )

    def test023_update_state_of_order_without_all_load_sos_invoiced(self):
        order = self.rec_order_1
        order_load_1 = self.rec_order_load_1
        order_load_1.with_user(self.res_users_accounting_user).write(
            {"so_state": "invoiced"}
        )

        order.update_sos_state()
        self.assertEqual(
            order.state, "partially_invoiced_sos", "Order state in fully invoiced sos"
        )

    def test024_order_with_all_load_sos_in_draft(self):
        order = self.rec_order_1
        order_load_1 = self.rec_order_load_1
        order_load_1.with_user(self.res_users_accounting_user).write(
            {"so_state": "draft"}
        )

        order.update_sos_state()
        self.assertEqual(order.state, "draft", "Order state not in draft")

    def test025_update_state_of_order_without_all_load_sos_validated(self):
        order = self.rec_order_1
        order_load_1 = self.rec_order_load_1
        order_load_1.with_user(self.res_users_accounting_user).write(
            {"so_state": "validated"}
        )

        order.update_sos_state()
        self.assertEqual(
            order.state, "partially_validated_sos", "Order state in fully validated sos"
        )

    def test026_update_state_of_order_with_all_load_sos_validated(self):
        order = self.rec_order_1
        order_load_1 = self.rec_order_load_1
        order_load_2 = self.rec_order_load_2
        order_load_1.with_user(self.res_users_accounting_user).write(
            {"so_state": "validated"}
        )
        order_load_2.with_user(self.res_users_accounting_user).write(
            {"so_state": "validated"}
        )

        order.update_sos_state()
        self.assertEqual(
            order.state, "fully_validated_sos", "Order state in partially validated sos"
        )

    def test027_order_with_proposed_price_as_zero(self):
        with self.assertRaises(ValidationError):
            self.rec_order_1.with_user(self.res_users_marketing_user).write(
                {"proposed_price": 0.0}
            )

    def test028_launch_reset_to_draft_wizard_on_order_in_loaded_state(self):
        with self.assertRaises(ValidationError):
            order = self.rec_order_1
            order.with_user(self.res_users_accounting_user).write({"state": "hedge"})
            order.btn_do_reset_to_draft()

    def test029_launch_reset_to_draft_wizard_on_order_in_proposed_state(self):
        order = self.rec_order_1
        order.with_user(self.res_users_credit_control_user).write({"state": "confirm"})
        order.btn_do_reset_to_draft()

    def test030_launch_order_cancel_wizard(self):
        order = self.rec_order_1
        order.btn_do_cancel()

    def test031_activate_load_park_on_load(self):
        order = self.rec_order_1
        order.btn_do_activate_load_park()

        self.assertTrue(order.load_and_park, "Load and park is False")

    def test032_release_loading_truck_on_order_with_state_in_load_truck(self):
        order = self.rec_order_1
        order.with_user(self.res_users_operations_user).write({"state": "lock_truck"})
        order.btn_do_release_truck()

        self.assertFalse(order.load_and_park, "Order load and park is True")
        self.assertEqual(
            order.state, "release_truck", "Order not in release truck state"
        )

    def test033_release_loading_truck_on_order_with_state_not_in_load_truck(self):
        order = self.rec_order_1
        order.with_user(self.res_users_operations_user).write({"state": "load"})

        order.btn_do_release_truck()
        self.assertEqual(order.state, "load", "Order in lock truck state")

    def test034_button_do_approve_order_with_true_credit_auto_approved(self):
        order = self.rec_order_1
        order.btn_do_approve()
        order.with_user(self.res_users_credit_control_user).write(
            {"credit_auto_approved": True}
        )

        self.assertTrue(
            order.credit_auto_approved, "Order credit auto approved is set to False"
        )

    def test035_notify_credit_control_of_auto_approval_email_on_order_with_partner_id(
        self,
    ):
        order = self.rec_order_1
        order.notify_credit_control_of_auto_approval_email()

    def test036_notify_credit_control_of_auto_approval_email_on_order_without_partner_id(
        self,
    ):
        order = self.rec_order_1
        order.with_user(self.res_users_credit_control_user).write({"partner_id": False})
        order.notify_credit_control_of_auto_approval_email()

    def test037_launch_load_wizard_for_order_in_loading_state(self):
        order = self.rec_order_1
        order.with_user(self.res_users_operations_user).write({"state": "loading"})
        order.with_user(self.res_users_operations_user).btn_do_load()

    def test037_launch_confirm_wizard_for_order_in_proposed_state(self):
        order = self.rec_order_1
        order.with_user(self.res_users_marketing_user).write({"state": "propose"})
        order.with_user(self.res_users_trading_user).btn_do_confirm()

    def test038_launch_create_sale_order_wizard_for_order_load(self):
        order = self.rec_order_1
        order.with_user(self.res_users_operations_user).write({"state": "loading"})
        order.with_user(self.res_users_accounting_user).btn_create_sale_order()

    def test039_action_view_sale_orders_created_from_order_loads(self):
        order = self.rec_order_1
        order.with_user(self.res_users_accounting_user).write(
            {"sale_order_ids": [self.sale_order.id, self.sale_order_1.id]}
        )
        order.action_view_sale_orders()

    def test040_action_view_hedge_created_from_order_loads(self):
        order = self.rec_order_1
        order.with_user(self.res_users_accounting_user).write(
            {"order_hedge_ids": [self.rec_hedge_1.id]}
        )
        order.action_view_hedges()

    def test041_launch_order_decline_wizard_by_trading_user(self):
        order = self.rec_order_1
        order.with_user(self.res_users_trading_user).btn_do_decline()

    def test042_is_auto_approvable_by_credit_control_for_partner_with_credit_blocked(
        self,
    ):
        order = self.rec_order_1
        order.partner_id.write({"credit_blocked": True})
        order.is_auto_approvable_by_credit_control()

    def test043_is_auto_approvable_by_credit_control_for_partner_with_zero_credit_limit(
        self,
    ):
        order = self.rec_order_1
        order.partner_id.write({"credit_limit": 0.0})
        order.is_auto_approvable_by_credit_control()

    def test044_reset_order_to_draft_with_wrong_price_reset_type_and_message(self):
        order = self.rec_order_1
        order.reset_to_draft(
            reset_type="wrong_price", message="Wrong price set for product"
        )
        self.assertEqual(order.state, "draft", "Order state is not draft")

    def test045_reset_order_to_draft_without_reset_type_but_message(self):
        order = self.rec_order_1
        order.reset_to_draft(reset_type="", message="Wrong price set for product")
        self.assertEqual(order.state, "draft", "Order state is not draft")

    def test046_propose_order_old_value_not_same_as_order_quantity_or_proposed_price(
        self,
    ):
        order = self.rec_order_1
        order.btn_do_propose()
        self.assertEqual(order.state, "propose", "Order state is not propose")

    def test046_propose_order_old_value_same_as_order_quantity_or_proposed_price(self):
        with self.assertRaises(ValidationError):
            order = self.rec_order_1
            self.rec_reset_to_draft_reason.with_user(
                self.res_users_marketing_user
            ).write({"old_value": 6.0})
            order.btn_do_propose()

    def test047_repropose_with_no_modifications_and_trading_decline_status(self):
        order = self.rec_order_1
        order.with_user(self.res_users_marketing_user).write(
            {"trading_decline_status": True}
        )
        order.btn_do_repropose()
        self.assertEqual(order.state, "propose", "Order state not in propose")
        self.assertFalse(
            order.trading_decline_status, "Order trading decline status is True"
        )

    def test048_repropose_with_no_modifications_and_true_credit_control_decline_status(
        self,
    ):
        order = self.rec_order_1
        order.with_user(self.res_users_marketing_user).write(
            {"credit_control_decline_status": True}
        )
        order.btn_do_repropose()
        self.assertEqual(order.state, "confirm", "Order state not in confirm")
        self.assertFalse(
            order.credit_control_decline_status,
            "Order credit control decline status is True",
        )

    def test049_repropose_with_modifications_log_and_true_credit_control_decline_status(
        self,
    ):
        self.model_oms_order_modification_log.create(
            {
                "order_management_id": self.rec_order_1.id,
                "currency_id": self.currency.id,
                "proposed_price": 110.0,
                "date": date.today(),
                "partner_id": self.partner2.id,
                "product_id": self.product_1.id,
                "quantity": 7.0,
                "product_uom_id": self.rec_product_uom.id,
                "payment_term_id": self.payment_term.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        order = self.rec_order_1
        order.with_user(self.res_users_marketing_user).write(
            {"credit_control_decline_status": True, "partner_id": self.partner1.id}
        )
        order.btn_do_repropose()
        self.assertEqual(order.state, "confirm", "Order state not in confirm")
        self.assertFalse(
            order.credit_control_decline_status,
            "Order credit control decline status is True",
        )

    def test050_repropose_with_modifications_and_false_credit_control_decline_status(
        self,
    ):
        self.model_oms_order_modification_log.create(
            {
                "order_management_id": self.rec_order_1.id,
                "currency_id": self.currency.id,
                "proposed_price": 120.0,
                "date": date.today(),
                "partner_id": self.partner2.id,
                "product_id": self.product_1.id,
                "quantity": 8.0,
                "product_uom_id": self.rec_product_uom.id,
                "payment_term_id": self.payment_term.id,
                "warehouse_id": self.warehouse.id,
            }
        )
        order = self.rec_order_1
        order.with_user(self.res_users_marketing_user).write(
            {"credit_control_decline_status": False, "partner_id": self.partner1.id}
        )
        order.btn_do_repropose()
        self.assertEqual(order.state, "propose", "Order state not in propose")
        self.assertFalse(
            order.trading_decline_status, "Order trading decline status is True"
        )

    def test051_run_unfulfilled_orders_cancellation_on_order_without_load(self):
        order = self.model_order_management.create(
            {
                "datetime": datetime.today(),
                "date": date(2021, 4, 21),
                "partner_id": self.partner1.id,
                "order_type": "regular",
                "product_id": self.product_1.id,
                "warehouse_id": self.warehouse.id,
                "loading_truck_number": "TRUCK-101",
                "quantity": 16.0,
                "product_uom_id": self.rec_product_uom.id,
                "currency_id": self.currency.id,
                "proposed_price": 120.0,
                "payment_term_id": self.payment_term.id,
                "state": "draft",
            }
        )

        order.run_unfulfilled_orders_cancellation()
        self.assertEqual(order.state, "cancel", "Order state not in cancel")

    def test052_parse_email(self):
        order = self.rec_order_1
        email = order._parse_email(order.partner_id.email)
        self.assertEqual(email, "john@company.com", "Partner email mismatch")

    def test053_run_inactivity_notification_cron(self):
        self.env["oms.escalated.notification"].create({"notify_after": 2})
        self.model_order_inactivity_monitor.with_user(
            self.res_users_marketing_user
        ).run_inactivity_notification_cron()

    def test054_order_decline_email(self):
        rec_order_management = self.rec_order_1
        rec_order_management.decline_email()
