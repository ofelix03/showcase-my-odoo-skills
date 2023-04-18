from odoo.tests.common import tagged

from ..models.account_invoice_line import AccountInvoiceLine
from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class AccountInvoiceLineTransactionCase(TestCommon):
    def test001_single_create_account_invoice_line(self):
        """Test asset creation.
        This test case confirms the creation of an invoice line record.
        """

        rec_account_invoice_line = self.model_account_invoice_line.create(
            {
                "move_id": self.account_invoice_1.id,
                "currency_id": self.currency.id,
                "account_id": self.account.id,
                "product_id": self.product_1.id,
                "waybill_no": "WAYBILL-1",
            }
        )

        self.assertIsInstance(
            rec_account_invoice_line,
            AccountInvoiceLine,
            "Object is not an instance of account invoice line",
        )

    def test002_onchange_product_id_on_invoice_line(self):
        rec_account_invoice_line = self.model_account_invoice_line.create(
            {
                "move_id": self.account_invoice_1.id,
                "currency_id": self.currency.id,
                "account_id": self.account.id,
                "product_id": self.product_1.id,
                "waybill_no": "WAYBILL-006",
            }
        )
        rec_account_invoice_line.with_user(self.res_users_account_manager).write(
            {"product_id": self.product_2.id}
        )

        rec_account_invoice_line._onchange_product_id()
        self.assertEqual(
            rec_account_invoice_line.waybill_no, "WAYBILL001", "Waybill number mismatch"
        )

    def test003_attach_waybill_doc_to_invoice(self):
        rec_account_invoice_line = self.model_account_invoice_line.create(
            {
                "move_id": self.account_invoice_1.id,
                "currency_id": self.currency.id,
                "account_id": self.account.id,
                "product_id": self.product_1.id,
                "waybill_no": "WAYBILL-1",
            }
        )
        rec_account_invoice_line.move_id.write({"move_type": "entry"})

        rec_account_invoice_line.attach_waybill_doc_to_invoice()
