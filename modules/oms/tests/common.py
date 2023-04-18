import base64
from datetime import date, datetime
from pathlib import Path

from odoo.tests.common import SavepointCase


class TestCommon(SavepointCase):
    """Shared base class for test cases.
    This bootstraps most of the records needed by the test cases.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Models
        cls.model_res_users = cls.env["res.users"]
        cls.model_res_partner = cls.env["res.partner"]
        cls.model_order_management = cls.env["oms.order"]
        cls.model_product_product = cls.env["product.product"]
        cls.model_product_uom = cls.env["uom.uom"]
        cls.model_product_uom_category = cls.env["uom.category"]
        cls.model_payment_term = cls.env["account.payment.term"]
        cls.model_warehouse = cls.env["stock.warehouse"]
        cls.model_sale_order = cls.env["sale.order"]
        cls.model_sale_order_line = cls.env["sale.order.line"]
        cls.model_hedging = cls.env["account.hedge"]
        cls.model_oms_order_decline_history = cls.env["oms.order.decline.history"]
        cls.model_oms_order_load = cls.env["oms.order.load"]
        cls.model_oms_order_pricing = cls.env["oms.order.pricing"]
        cls.model_reset_to_draft_reason = cls.env["oms.order.reset.to.draft.reason"]
        cls.model_order_inactivity_monitor = cls.env["oms.inactivity.monitor"]
        cls.model_oms_order_modification_log = cls.env["oms.order.modification.log"]
        cls.model_product_category = cls.env["product.category"]
        cls.model_account_invoice = cls.env["account.move"]
        cls.model_account_invoice_line = cls.env["account.move.line"]
        cls.model_account_journal = cls.env["account.journal"]
        cls.model_res_currency = cls.env["res.currency"]
        cls.model_res_company = cls.env["res.company"]
        cls.model_account = cls.env["account.account"]
        cls.model_account_type = cls.env["account.account.type"]
        cls.model_res_bank = cls.env["res.bank"]
        cls.model_oms_reset_order_to_draft_wizard = cls.env[
            "oms.reset.order.to.draft.wizard"
        ]
        cls.model_oms_cancel_order_wizard = cls.env["oms.cancel.order.wizard"]
        cls.model_oms_price_order_wizard = cls.env["oms.price.order.wizard"]
        cls.model_oms_load_order_wizard = cls.env["oms.load.order.wizard"]
        cls.model_oms_cancel_expired_order_wizard = cls.env[
            "oms.cancel.expired.order.wizard"
        ]
        cls.model_oms_hedge_order_wizard = cls.env["oms.hedge.order.wizard"]

        # Module User Roles
        cls.group_marketing_user = cls.env.ref("oms.group_marketing_user")
        cls.group_trading_user = cls.env.ref("oms.group_trading_user")
        cls.group_credit_control_user = cls.env.ref("oms.group_credit_control_user")
        cls.group_operations_user = cls.env.ref("oms.group_operations_user")
        cls.group_accounting_user = cls.env.ref("oms.group_accounting_user")
        cls.group_audit_user = cls.env.ref("oms.group_audit_user")
        cls.group_finance_user = cls.env.ref("oms.group_finance_user")
        cls.group_account_manager = cls.env.ref("account.group_account_manager")
        cls.group_sale_manager = cls.env.ref("sales_team.group_sale_manager")
        cls.group_account_invoice_billing = cls.env.ref("account.group_account_invoice")

        # Create Company
        cls.company = cls.model_res_company.create(
            {"name": "Company", "website": "www.company.com"}
        )

        # Create Bank
        cls.rec_bank = cls.model_res_bank.create({"name": "Inter Bank", "active": True})

        # Users
        cls.res_users_marketing_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Marketing User",
                "email": "marketing-user",
                "login": "marketing-user",
                "groups_id": [(6, 0, [cls.group_marketing_user.id])],
            }
        )

        cls.res_users_trading_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Trading User",
                "email": "trading-user",
                "login": "trading-user",
                "groups_id": [(6, 0, [cls.group_trading_user.id])],
            }
        )

        cls.res_users_credit_control_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Credit Control User",
                "email": "credit_control-user",
                "login": "credit-control-user",
                "groups_id": [(6, 0, [cls.group_credit_control_user.id])],
            }
        )

        cls.res_users_operations_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Operations User",
                "email": "operations-user",
                "login": "operations-user",
                "groups_id": [(6, 0, [cls.group_operations_user.id])],
            }
        )

        cls.res_users_audit_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Audit User",
                "email": "audit-user",
                "login": "audit-user",
                "groups_id": [(6, 0, [cls.group_audit_user.id])],
            }
        )

        cls.res_users_accounting_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Accounting User",
                "email": "accounting-user",
                "login": "accounting-user",
                "groups_id": [(6, 0, [cls.group_accounting_user.id])],
            }
        )

        cls.res_users_finance_user = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Finance User",
                "email": "finance-user",
                "login": "finance-user",
                "groups_id": [(6, 0, [cls.group_finance_user.id])],
            }
        )

        cls.res_users_account_manager = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Account Manager",
                "email": "account-manager",
                "login": "account-manager",
                "groups_id": [(6, 0, [cls.group_account_manager.id])],
            }
        )

        cls.res_users_account_invoice_billing = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Invoice Billing",
                "email": "account-invoice-billing",
                "login": "account-invoice-billing",
                "groups_id": [(6, 0, [cls.group_account_invoice_billing.id])],
            }
        )

        cls.res_users_sale_manager = cls.model_res_users.with_context(
            {"no_reset_password": True}
        ).create(
            {
                "name": "Sale Manager",
                "email": "sale-manager",
                "login": "sale-manager",
                "groups_id": [(6, 0, [cls.group_sale_manager.id])],
            }
        )

        # Create Account Type
        cls.account_type = cls.model_account_type.create(
            {"name": "Bank and Cash", "type": "liquidity", "internal_group": "asset"}
        )

        # Create Accounts
        cls.account = cls.model_account.create(
            {
                "name": "Expense Account",
                "code": "EA",
                "user_type_id": cls.account_type.id,
            }
        )

        # Create Currency
        cls.currency = cls.model_res_currency.create({"name": "Gold", "symbol": "G"})

        #  Create Partner
        cls.partner1 = cls.model_res_partner.create(
            {
                "name": "John Doe",
                "email": "john@company.com",
                "company_id": cls.env.company.id,
            }
        )

        cls.partner2 = cls.model_res_partner.create({"name": "Sam Smith LPG"})

        # Create Product Category
        cls.category_1 = cls.model_product_category.create({"name": "Consumable"})

        # Create Payment Term
        cls.payment_term = cls.model_payment_term.create({"name": "Immediate"})

        # Create Warehouse
        cls.warehouse = cls.model_warehouse.create(
            {"name": "Warehouse", "code": "WH", "company_id": cls.company.id}
        )

        # Create Account Journal
        cls.account_journal = cls.model_account_journal.create(
            {"name": "Account Journal", "type": "sale", "code": "AJ"}
        )

        # Create Unit of Measure Category
        cls.rec_product_uom_category = cls.model_product_uom_category.create(
            {"name": "Unit"}
        )

        # Create Unit of Measure
        cls.rec_product_uom = cls.model_product_uom.create(
            {
                "name": "Units",
                "uom_type": "reference",
                "factor": 1,
                "category_id": cls.rec_product_uom_category.id,
            }
        )

        # Create Products
        cls.product_1 = cls.model_product_product.create(
            {
                "name": "Product 1",
                "sale_ok": True,
                "purchase_ok": True,
                "type": "consu",
                "categ_id": cls.category_1.id,
            }
        )

        cls.product_2 = cls.model_product_product.create(
            {
                "name": "Product 2",
                "sale_ok": True,
                "purchase_ok": True,
                "type": "service",
                "categ_id": cls.category_1.id,
            }
        )

        # Create Sale Order
        cls.sale_order = cls.model_sale_order.create(
            {
                "partner_id": cls.partner1.id,
                "company_id": cls.env.company.id,
                "date_order": date(2021, 4, 21),
                "payment_term_id": cls.payment_term.id,
                "cust_order_no": "ORDER001",
                "truck_no": "TRUCK-001",
                "amount_total": 500.0,
                "state": "sale",
                "origin": "ORIGIN001",
            }
        )

        cls.sale_order_1 = cls.model_sale_order.create(
            {
                "partner_id": cls.partner1.id,
                "company_id": cls.env.company.id,
                "date_order": date(2021, 4, 21),
                "payment_term_id": cls.payment_term.id,
                "cust_order_no": "ORDER002",
                "truck_no": "TRUCK-001",
                "amount_total": 400.0,
                "state": "sale",
            }
        )

        # Create Sale Order Line
        cls.sale_order_line_1 = cls.model_sale_order_line.create(
            {
                "order_id": cls.sale_order.id,
                "product_id": cls.product_1.id,
                "name": "Product 1",
                "product_uom_qty": 5,
                "price_unit": 100.0,
                "price_subtotal": 500.0,
            }
        )

        # Create Account Invoice
        cls.account_invoice_1 = cls.model_account_invoice.create(
            {
                "move_type": "out_invoice",
                "state": "draft",
                "date": date.today(),
                "journal_id": cls.account_journal.id,
                "currency_id": cls.currency.id,
                "invoice_origin": "ORIGIN001",
            }
        )

        cls.account_invoice_2 = cls.model_account_invoice.create(
            {
                "move_type": "out_invoice",
                "state": "draft",
                "date": date.today(),
                "journal_id": cls.account_journal.id,
                "currency_id": cls.currency.id,
                "invoice_origin": "ORIGIN002",
            }
        )

        # Create Account Invoice Lines
        cls.account_invoice_line_1 = cls.model_account_invoice_line.create(
            {
                "move_id": cls.account_invoice_1.id,
                "currency_id": cls.currency.id,
                "account_id": cls.account.id,
                "product_id": cls.product_1.id,
            }
        )

        cls.account_invoice_line_2 = cls.model_account_invoice_line.create(
            {
                "move_id": cls.account_invoice_1.id,
                "currency_id": cls.currency.id,
                "account_id": cls.account.id,
                "product_id": cls.product_2.id,
            }
        )

        cls.account_invoice_line_3 = cls.model_account_invoice_line.create(
            {
                "move_id": cls.account_invoice_2.id,
                "currency_id": cls.currency.id,
                "account_id": cls.account.id,
                "product_id": cls.product_1.id,
            }
        )

        # Create Order Management
        cls.rec_order_1 = cls.model_order_management.create(
            {
                "datetime": datetime.today(),
                "partner_id": cls.partner1.id,
                "order_type": "regular",
                "product_id": cls.product_1.id,
                "warehouse_id": cls.warehouse.id,
                "loading_truck_number": "TRUCK001",
                "quantity": 6.0,
                "product_uom_id": cls.rec_product_uom.id,
                "currency_id": cls.currency.id,
                "proposed_price": 120.0,
                "payment_term_id": cls.payment_term.id,
                "state": "draft",
            }
        )

        cls.rec_order_load_1 = cls.model_oms_order_load.with_user(
            cls.res_users_operations_user
        ).create(
            {
                "load_date": date.today(),
                "warehouse_id": cls.warehouse.id,
                "customer_order_number": "ORDER001",
                "truck_number": "TRUCK-1",
                "quantity": 4.0,
                "waybill": cls.get_sample_waybill_bs64encoded(),
                "waybill_number": "WAYBILL001",
                "order_sheet": cls.get_sample_waybill_bs64encoded(),
                "hedge_status": "hedge",
                "so_state": "validated",
                "order_management_id": cls.rec_order_1.id,
                "sale_order_id": cls.sale_order.id,
            }
        )

        cls.rec_order_load_2 = cls.model_oms_order_load.with_user(
            cls.res_users_operations_user
        ).create(
            {
                "load_date": date.today(),
                "warehouse_id": cls.warehouse.id,
                "customer_order_number": "ORDER002",
                "truck_number": "TRUCK-2",
                "quantity": 2.0,
                "waybill": cls.get_sample_waybill_bs64encoded(),
                "waybill_number": "WAYBILL002",
                "order_sheet": cls.get_sample_waybill_bs64encoded(),
                "hedge_status": "draft",
                "order_management_id": cls.rec_order_1.id,
            }
        )

        cls.rec_hedge_1 = cls.model_hedging.create(
            {
                "show_order": True,
                "deal_date": date(2021, 4, 21),
                "bank_id": cls.rec_bank.id,
                "trade_number": "TRADE001",
                "spot_rate": 4.2,
                "forward_rate": 4.3,
                "usd_amount": 120.0,
                "maturity_period": 10,
                "order_loading_ids": [(6, False, [cls.rec_order_load_1.id])],
            }
        )

        cls.rec_hedge_2 = cls.model_hedging.create(
            {
                "show_order": True,
                "deal_date": date(2021, 4, 21),
                "bank_id": cls.rec_bank.id,
                "trade_number": "TRADE002",
                "spot_rate": 4.2,
                "forward_rate": 4.3,
                "usd_amount": 120.0,
                "maturity_period": 10,
                "order_loading_ids": [(6, False, [cls.rec_order_load_2.id])],
            }
        )

        # Create reset to draft reason
        cls.rec_reset_to_draft_reason = cls.model_reset_to_draft_reason.create(
            {
                "order_id": cls.rec_order_1.id,
                "message": "This reason",
                "old_value": 6.7,
                "reset_type": "",
            }
        )

        # Create order pricing
        cls.rec_order_pricing = cls.model_oms_order_pricing.create(
            {
                "spot_rate": 2.10,
                "forward_rate": 2.20,
                "final_price": 110.0,
                "quantity": 7.0,
                "product_uom_id": cls.rec_product_uom.id,
                "maturity_period": 11,
                "margin": 3.0,
                "margin_uom_id": cls.rec_product_uom.id,
                "order_management_id": cls.rec_order_1.id,
            }
        )

    @classmethod
    def get_sample_waybill_bs64encoded(cls):
        doc_path = Path(__file__).parent / "assets/sample_waybill.pdf"
        doc = base64.b64encode(doc_path.read_bytes())
        return doc
