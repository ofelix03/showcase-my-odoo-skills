from odoo import fields, models


class Hedge(models.Model):
    _inherit = "account.hedge"

    order_loading_ids = fields.One2many(
        comodel_name="oms.order.load", inverse_name="hedge_id", string="Hedged Invoices"
    )
    show_order = fields.Boolean(default=False)
