from odoo import api, fields, models


class PaymentPlanDeclineHistory(models.Model):
    _name = "account.payment.plan.decline.history"
    _description = "Account Payment Plan Decline History"
    _desc = "id desc, declined_at desc"

    payment_plan_id = fields.Many2one(
        comodel_name="account.payment.plan", string="Payment Plan"
    )
    declined_at = fields.Datetime(string="Datetime", readonly=True)
    reason = fields.Text(readonly=True)
    declined_by_id = fields.Many2one(comodel_name="res.users", readonly=True)
    declined_at_state = fields.Selection(
        selection=[
            ("waiting_review", "Waiting Review"),
            ("waiting_approval", "Waiting Approval"),
            ("customer_approval", "Customer Approval"),
            ("draft_dsa_waiting_approval", "Draft DSA Waiting Approval"),
        ],
        default="waiting_review",
        string="Declined At",
    )
    document = fields.Binary(string="Document")
    document_ir_attachment = fields.Many2one(
        "ir.attachment", compute="_compute_ir_attachment"
    )

    api.depends("document")

    def _compute_ir_attachment(self):
        if not self.document_ir_attachment:
            declined_at_state = self.declined_at_state.replace("_", " ").upper()
            filename = f"Declined At {declined_at_state}".upper()
            self.document_ir_attachment = self.env["ir.attachment"].create(
                {
                    "datas": self.document,
                    "name": filename,
                    "store_fname": filename,
                    "res_id": self.id,
                    "res_model": "account.decline.payment.plan",
                }
            )
