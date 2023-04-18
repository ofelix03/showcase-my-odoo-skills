from odoo import fields, models


class OrderResetToDraft(models.TransientModel):
    _name = "oms.reset.order.to.draft.wizard"
    _description = "Order Reset To Draft"

    reset_type = fields.Selection(
        [("wrong_price", "Wrong Price"), ("wrong_quantity", "Wrong Quantity")],
        string="Reason",
        required=True,
    )
    message = fields.Char(string="Message", required=True)
    order_id = fields.Many2one(comodel_name="oms.order")

    def reset_to_draft(self):
        message = (
            f"Order reset to draft. {self.reset_type.upper()}. "
            f"Reason: {self.message}"
        )
        self.order_id.reset_to_draft(reset_type=self.reset_type, message=message)
