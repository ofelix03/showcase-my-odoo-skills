from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_interest_id = fields.Many2one(
        comodel_name="account.invoice.interest", string="Invoice Interest"
    )
