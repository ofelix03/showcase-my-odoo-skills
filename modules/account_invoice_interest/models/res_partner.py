from odoo import fields, models


class PartnerInterestTag(models.Model):
    _name = "partner.interest.tag"
    _description = "Partner Interest Tag"

    name = fields.Char(string="Name")


class ResPartner(models.Model):
    _inherit = "res.partner"

    # interest_tag_ids = fields.Many2many('partner.interest.tag', string="Interest Tags")
    interest_accrued_collected = fields.Boolean(
        "Invoice Interest Accrued And Collected",
        help="Interest accrued on all invoices belonging"
        " to this customer must be collected",
    )
