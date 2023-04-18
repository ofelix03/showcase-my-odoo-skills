from odoo import fields, models

MODEL_PAYMENT_PLAN = "account.payment.plan"


class DeclinePaymentPlan(models.TransientModel):
    _name = "account.decline.payment.plan"
    _description = "Account Payment Plan Decline"

    payment_plan_id = fields.Many2one(
        comodel_name="account.payment.plan", string="Payment Plan"
    )
    reason = fields.Text()
    document = fields.Binary(
        string="Document",
        help="A document containing any " "additional information, " "annotations etc",
    )
    document_filename = fields.Char(default="Document")

    def action_decline_plan(self):
        self.payment_plan_id.decline(self.reason, self.document)
        self.payment_plan_id.send_email_notification_declined_at_approval_stage(
            self.reason, self.document
        )

    def action_decline_draft_dsa(self):
        self.payment_plan_id.decline(self.reason, self.document)
        self.payment_plan_id.send_email_notification_declined_at_dsa_approval_stage(
            self.reason, self.document
        )

    def action_customer_decline_draft_dsa(self):
        self.payment_plan_id.customer_declined_draft_dsa(self.reason, self.document)
        self.payment_plan_id.send_email_notification_customer_declined_draft_dsa(
            self.reason, self.document
        )
