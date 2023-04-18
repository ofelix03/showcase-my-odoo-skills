from odoo import fields, models


class OrderModificationLog(models.Model):
    _name = "oms.order.modification.log"
    _description = "Modificatltion Log"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        ondelete="cascade",
        string="Order Management",
    )
    marketer_id = fields.Many2one(comodel_name="res.users", string="User")
    currency_id = fields.Many2one(comodel_name="res.currency", string="Currency")
    proposed_price = fields.Float(string="Proposed Price", digits=(12, 4))
    date = fields.Datetime(string="Date")
    partner_id = fields.Many2one(comodel_name="res.partner", string="Customer")
    product_id = fields.Many2one(comodel_name="product.product", string="Product")
    quantity = fields.Float(string="Quantity")
    product_uom_id = fields.Many2one(comodel_name="uom.uom", string="Unit of Measure")
    payment_term_id = fields.Many2one(
        comodel_name="account.payment.term", string="Payment Term"
    )
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse", string="Proposed Warehouse"
    )
