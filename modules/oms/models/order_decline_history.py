from odoo import fields, models


class OrderDeclineHistory(models.Model):
    _name = "oms.order.decline.history"
    _description = "Decline History"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        ondelete="cascade",
        string="Order Management",
    )
    declined_by = fields.Many2one(
        comodel_name="res.users", string="Declined By", readonly=True
    )
    comment = fields.Char(string="Comment", readonly=True)
    payment_term_id = fields.Many2one(
        comodel_name="account.payment.term", string="Payment Term", readonly=True
    )
    counter_price = fields.Float(string="Counter Price", digits=(12, 4), readonly=True)
    document = fields.Binary(string="Document", attachment=False)
