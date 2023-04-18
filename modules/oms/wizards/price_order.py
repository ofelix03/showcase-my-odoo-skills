from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PriceOrderWizard(models.TransientModel):
    _name = "oms.price.order.wizard"
    _description = "Price Order"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        readonly=True,
        default=lambda self: self.env.context.get("order_management_id", False),
    )
    spot_rate = fields.Float(string="Spot Rate", required=True, digits=(4, 4))
    final_price = fields.Float(string="Final Price", required=True, digits=(12, 4))
    quantity = fields.Float(string="Quantity", required=True, digits=(12, 2))
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom", string="Unit of Measure", required=True
    )
    maturity_period = fields.Integer(string="Maturity Period", required=True)
    forward_rate = fields.Float(string="Forward Rate", digits=(4, 4), required=True)
    margin = fields.Float(string="Margin", digits=(12, 2), required=True)
    margin_uom_id = fields.Many2one(
        comodel_name="uom.uom", string="Margin UoM", required=True, default=20
    )

    @api.onchange("order_management_id")
    def _confirm_wizard(self):
        order = self.order_management_id
        if order:
            self.quantity = order.quantity
            self.final_price = order.proposed_price
            self.product_uom_id = order.product_uom_id.id

    def btn_do_submit(self):
        order = self.order_management_id

        price = self.final_price
        quantity = self.quantity
        if price and quantity:
            invoice_amount = price * quantity

        model_oms_order_pricing = self.env["oms.order.pricing"]
        order_pricing = model_oms_order_pricing.search(
            [("order_management_id", "=", order.id)], order="id desc", limit=1
        )
        if not order_pricing:
            model_oms_order_pricing.create(
                {
                    "order_management_id": order.id,
                    "spot_rate": self.spot_rate,
                    "final_price": self.final_price,
                    "quantity": self.quantity,
                    "product_uom_id": self.product_uom_id.id,
                    "forward_rate": self.forward_rate,
                    "maturity_period": self.maturity_period,
                    "margin": self.margin,
                    "margin_uom_id": self.margin_uom_id.id,
                    "invoice_amount": invoice_amount,
                    "trader_id": order.env.user.id,
                }
            )
        else:
            order_pricing.write(
                {
                    "spot_rate": self.spot_rate,
                    "final_price": self.final_price,
                    "quantity": self.quantity,
                    "product_uom_id": self.product_uom_id.id,
                    "forward_rate": self.forward_rate,
                    "maturity_period": self.maturity_period,
                    "margin": self.margin,
                    "margin_uom_id": self.margin_uom_id.id,
                    "invoice_amount": invoice_amount,
                    "trader_id": order.env.user.id,
                }
            )
        order.write({"state": "confirm", "confirmed_by": order.env.user.id})
        # check and auto approve for credit control
        if order.is_auto_approvable_by_credit_control():
            order = order.with_context(is_auto_approved=True)
            order.sudo().btn_do_approve()
        else:
            order.send_email_confirm_order()
            # order.send_email()

    @api.constrains(
        "quantity",
        "spot_rate",
        "final_price",
        "forward_rate",
        "margin",
        "maturity_period",
    )
    def _check_fields_validity_with_exception(self):
        if not self.final_price or self.final_price <= 0:
            raise ValidationError(
                _("Final Price: {} cannot be a zero or less.".format(self.final_price))
            )

        if not self.quantity or self.quantity <= 0.00:
            raise ValidationError(
                _("Quantity: {} cannot be a zero or less.".format(self.quantity))
            )

        if self.maturity_period < 0.00:
            raise ValidationError(
                _(
                    "Maturity Period: {} cannot be less than zero.".format(
                        self.maturity_period
                    )
                )
            )

        if not self.spot_rate or self.spot_rate <= 0.00:
            raise ValidationError(
                _("Spot Rate: {} cannot be a zero or less.".format(self.spot_rate))
            )

        if not self.forward_rate or self.forward_rate <= 0.00:
            raise ValidationError(
                _(
                    "Forward Rate: {} cannot be a zero or less.".format(
                        self.forward_rate
                    )
                )
            )
