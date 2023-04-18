from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class DeclineOrderWizard(models.TransientModel):
    _name = "oms.decline.order.wizard"
    _description = "Decline Order Wizard"

    comment = fields.Char(string="Comment", required=True)
    counter_price = fields.Float(string="Counter Price", digits=(12, 4))
    payment_term_id = fields.Many2one(
        comodel_name="account.payment.term", string="Payment Term"
    )
    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        readonly=True,
        default=lambda self: self.env.context.get("order_management_id", False),
    )
    order_state = fields.Selection(
        readonly=True,
        related="order_management_id.state",
    )
    document = fields.Binary(string="Document", attachment=False)

    def btn_do_decline_order(self):
        order = self.order_management_id
        if order:
            self.env["oms.order.decline.history"].create(
                {
                    "comment": self.comment,
                    "counter_price": self.counter_price,
                    "payment_term_id": self.payment_term_id.id,
                    "declined_by": order.env.user.id,
                    "order_management_id": order.id,
                    "document": self.document,
                }
            )
            if order.state == "propose":
                order.trading_decline_status = True
            elif order.state == "confirm":
                order.credit_control_decline_status = True
            elif order.state in ("approve", "loading"):
                order.operations_decline_status = True
            order.state = "draft"
            order.decline_email()

    @api.constrains("counter_price")
    def _check_counter_price_validity_with_exception(self):
        is_group_trading_user = self.env.user.has_group("oms.group_trading_user")
        if is_group_trading_user and (
            not self.counter_price or self.counter_price <= 0.00
        ):
            raise ValidationError(
                _(
                    "Proposed Price: {} cannot be a zero or less.".format(
                        self.counter_price
                    )
                )
            )
