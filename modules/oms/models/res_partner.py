from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    credit_blocked = fields.Boolean(
        "Credit Blocked",
        help="When a partner's credit is block, it is required that"
        "Credit Control approves of any order they put in the OMS",
    )
