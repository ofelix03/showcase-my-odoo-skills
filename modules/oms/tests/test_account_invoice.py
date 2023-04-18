from datetime import date

from odoo.tests.common import tagged

from ..models.account_invoice import AccountInvoice
from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class AccountInvoiceTransactionCase(TestCommon):
    def create_account_invoice_record(self):
        rec_account_invoice = self.model_account_invoice.create(
            {
                "move_type": "out_invoice",
                "state": "draft",
                "date": date.today(),
                "journal_id": self.account_journal.id,
                "currency_id": self.currency.id,
                "invoice_origin": "ORIGIN001",
                "partner_id": self.partner1.id,
            }
        )
        return rec_account_invoice

    def test001_single_create_account_invoice(self):
        """Test asset creation.
        This test case confirms the creation of an account invoice record.
        """

        rec_account_invoice = self.model_account_invoice.create(
            {
                "move_type": "out_invoice",
                "state": "draft",
                "date": date.today(),
                "journal_id": self.account_journal.id,
                "currency_id": self.currency.id,
                "invoice_origin": "ORIGIN001",
                "partner_id": self.partner1.id,
            }
        )

        self.assertIsInstance(
            rec_account_invoice,
            AccountInvoice,
            "Object is not an instance of account invoice",
        )

    def test003_invoice_post(self):
        rec_account_invoice = self.create_account_invoice_record()

        # Create invoice line
        self.model_account_invoice_line.with_context(check_move_validity=False).create(
            {
                "move_id": rec_account_invoice.id,
                "name": "LINE",
                "product_id": self.product_1.id,
                "price_unit": 4.2,
                "quantity": 1000,
                "account_id": self.account.id,
                "waybill_no": "BILL/20",
                "truck_no": "TRUCK001",
            }
        )
        self.sale_order.with_user(self.res_users_accounting_user).write(
            {"load_id": self.rec_order_load_1.id, "name": "ORIGIN001"}
        )

        rec_account_invoice._post()

    def test004_invoice_has_oms_origin(self):
        rec_account_invoice = self.create_account_invoice_record()
        self.model_account_invoice_line.with_context(check_move_validity=False).create(
            {
                "move_id": rec_account_invoice.id,
                "name": "LINE",
                "product_id": self.product_1.id,
                "price_unit": 4.2,
                "quantity": 1000,
                "account_id": self.account.id,
                "waybill_no": "BILL/20",
                "truck_no": "TRUCK001",
            }
        )

        rec_account_invoice.has_oms_origin()
