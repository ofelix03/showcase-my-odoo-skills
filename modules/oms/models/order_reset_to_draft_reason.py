from odoo import fields, models


class ResetOrderToDraftReason(models.Model):
    _name = "oms.order.reset.to.draft.reason"
    _description = "Order Reset To Draft Reason"
    _order = "id desc"

    message = fields.Char(string="Message")
    reset_type = fields.Char(string="Reason")
    order_id = fields.Many2one(comodel_name="oms.order", string="OMS Order")
    old_value = fields.Float(string="Old Value")

    def get_order_issue(self, order):
        return self.search([("order_id", "=", order.id)], limit=1, order="id desc")

    def get_latest_reason(self):
        return self.search(
            [("order_id", "=", self.order_id.id)], order="id desc", limit=1
        )

    def is_wrong_price(self):
        return self.reset_type == "wrong_price"

    def is_wrong_quantity(self):
        return self.reset_type == "wrong_quantity"
