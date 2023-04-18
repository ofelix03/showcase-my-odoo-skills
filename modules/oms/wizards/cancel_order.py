from odoo import fields, models


class CancelOrderWizard(models.TransientModel):
    _name = "oms.cancel.order.wizard"
    _description = "Cancel Order"

    reason = fields.Char(string="Reason", required=True)
    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        readonly=True,
        default=lambda self: self.env.context.get("order_management_id", False),
    )

    def btn_do_cancel_order(self):
        order = self.order_management_id

        if order:
            order.write(
                {
                    "state": "cancel",
                    "cancel_reason": self.reason,
                    "cancelled_by": order.env.user.id,
                }
            )
