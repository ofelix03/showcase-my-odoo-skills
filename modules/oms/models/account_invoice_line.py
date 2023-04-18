from odoo import models


class AccountInvoiceLine(models.Model):

    _inherit = "account.move.line"

    def attach_waybill_doc_to_invoice_line(self, load):
        waybill_name = f"{load.name}-{load.waybill_number}-Waybill.pdf"
        self.env["ir.attachment"].create(
            {
                "datas": load.waybill,
                "name": waybill_name,
                "res_id": self.move_id.id,
                "res_model": "account.move",
            }
        )

    def attach_order_sheet_to_invoice(self, load):
        if load.order_sheet:
            sheet_name = f"{load.name}-Order Sheet.pdf"
            self.env["ir.attachment"].create(
                {
                    "datas": load.order_sheet,
                    "name": sheet_name,
                    "res_id": self.move_id.id,
                    "res_model": "account.move",
                }
            )
