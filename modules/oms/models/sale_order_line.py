from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    load_id = fields.Many2one(related="order_id.load_id", readonly=True)
