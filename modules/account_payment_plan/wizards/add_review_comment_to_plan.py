from odoo import fields, models


class AddReviewCommentToPlan(models.TransientModel):
    _name = "account.payment.plan.add.review.comment"
    _description = "Add Review Comment To Payment Plan"

    payment_plan_id = fields.Many2one(
        comodel_name="account.payment.plan", string="Payment Plan"
    )
    comment = fields.Text()

    def action_submit_plan_for_approval(self):
        self.payment_plan_id.submit_for_approval(self.comment)
