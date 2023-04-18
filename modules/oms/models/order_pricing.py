from odoo import fields, models


class OrderPricing(models.Model):
    _name = "oms.order.pricing"
    _description = "Order Pricing"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        readonly=True,
        ondelete="cascade",
        string="Order Management",
    )
    spot_rate = fields.Float(
        string="Spot Rate", required=True, readonly=True, digits=(4, 4)
    )
    final_price = fields.Float(string="Final Price", digits=(12, 4), readonly=True)
    quantity = fields.Float(string="Quantity", readonly=True, digits=(12, 2))
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom", string="Unit of Measure", readonly=True
    )
    maturity_period = fields.Integer(string="Maturity Period", readonly=True)
    forward_rate = fields.Float(string="Forward Rate", digits=(4, 4), readonly=True)
    margin = fields.Float(string="Margin", digits=(12, 2), readonly=True)
    margin_uom_id = fields.Many2one(comodel_name="uom.uom", string="UoM", readonly=True)
    invoice_amount = fields.Float(
        string="Invoice Amount", readonly=True, digits=(12, 2)
    )
    trader_id = fields.Many2one(comodel_name="res.users", readonly=True)
    order_state = fields.Selection(
        string="Order State", related="order_management_id.state", readonly=True
    )

    form_is_editable = fields.Boolean(compute="_compute_check_is_form_editable")

    def _compute_check_is_form_editable(self):
        self.form_is_editable = self.env.user.has_group(
            "oms.group_trading_user"
        ) and self.order_state not in [
            "partially_validated_sos",
            "fully_validated_sos",
            "partially_invoiced_sos",
            "fully_invoiced_sos",
            "hedge",
            "partially_hedged",
            "cancel",
        ]
