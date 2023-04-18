from odoo import fields, models


class GenerateSaleOrderWizard(models.TransientModel):
    _name = "oms.generate.sale.order.wizard"
    _description = "Generate Sale Order"

    order_partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Order Partner",
        default=lambda self: self.env["oms.order"].browse(
            self._context.get("partner_id", False)
        ),
        readonly=True,
    )
    order_management_id = fields.Many2one(comodel_name="oms.order", readonly=True)
    sale_order_id = fields.Many2one(comodel_name="sale.order", string="Sale Order")
    sale_order_analytic_id = fields.Many2one(
        comodel_name="account.analytic.account",
        string="Sale Order Analytic",
        required=True,
    )
    quantity = fields.Float(string="Quantity", digits=(12, 2))
    warehouse_id = fields.Many2one(comodel_name="stock.warehouse", string="Warehouse")
    customer_order_number = fields.Char(string="Customer Order No.")
    truck_number = fields.Char(string="Truck No")
    load_id = fields.Many2one(
        comodel_name="oms.order.load", string="Loads", readonly=True
    )

    def btn_create_sale_order(self):
        order = self.order_management_id
        load = self.load_id
        if order:
            so_order_line_list = []
            so_order_line_list.append(
                (
                    0,
                    0,
                    {
                        "product_id": order.product_id.id,
                        "name": order.product_id.name,
                        "product_uom_qty": self.quantity,
                        "product_uom": order.product_uom_id.id,
                        "price_unit": order.order_pricing_ids[-1].final_price,
                        "waybill_no": self.load_id.waybill_number,
                    },
                )
            )
            sale_order = self.env["sale.order"].create(
                {
                    "order_management_id": order.id,
                    "partner_id": order.partner_id.id,
                    "date_order": order.datetime,
                    "warehouse_id": self.warehouse_id.id,
                    "cust_order_no": self.customer_order_number,
                    "truck_no": self.truck_number,
                    "payment_term_id": order.payment_term_id.id,
                    "order_line": so_order_line_list,
                    "analytic_account_id": self.sale_order_analytic_id.id,
                }
            )
            load.write({"sale_order_by": self.env.user.id})
            load.write(
                {
                    "sale_order_id": sale_order.id,
                    "sale_order_by": order.env.user.id,
                }
            )
