from odoo import _, fields, models
from odoo.exceptions import ValidationError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        string="Order",
        readonly=True,
        help="This is references an order placed inside the Order Management",
    )
    load_id = fields.Many2one(
        comodel_name="oms.order.load", string="Load", readonly=True
    )

    def action_confirm(self):
        STATES = [
            "fully_validated_sos",
            "fully_invoiced_sos",
            "partially_invoiced_sos",
            "hedged",
            "cancelled",
            "declined",
        ]
        if self.order_management_id.state in STATES:
            raise ValidationError(_("You can not confirm this order at this stage"))

        is_confirmed = super(SaleOrder, self).action_confirm()
        if is_confirmed and self.load_id:
            self.load_id.mark_load_has_validated_so()
            self.order_line[0].waybill_no = (
                self.order_line[0].waybill_no or self.load_id.waybill_number
            )
        return is_confirmed

    def update_sale_lines(self, price_unit=None, product_uom_qty=None):
        for order in self:
            price_unit = (
                price_unit or order.order_line.mapped(lambda line: line.price_unit)[0]
            )
            product_uom_qty = product_uom_qty or self.load_id.quantity
            order.order_line.write(
                {"price_unit": price_unit, "product_uom_qty": product_uom_qty}
            )

    def get_stock_delivery(self):
        return self.env["stock.picking"].search([("sale_id", "=", self.id)], limit=1)

    def stock_delivered(self):
        return self.get_stock_delivery().state == "done"

    def update_stock_delivery(self, product_uom_qty):
        for order in self:
            if not order.stock_delivered():
                picking = order.get_stock_delivery()
                picking.move_line_ids.write({"product_uom_qty": product_uom_qty})

    def action_cancel(self):
        related_oms_load = self.env["oms.order.load"].search(
            [("sale_order_id", "=", self.id)]
        )
        is_cancelled = super(SaleOrder, self).action_cancel()

        if related_oms_load:
            related_oms_load.sale_order_id = None
            related_oms_load.so_state = "draft"
            related_oms_load.hedge_status = "draft"
            if related_oms_load.order_management_id.is_fully_loaded():
                related_oms_load.order_management_id.mark_as_fully_loaded()
            else:
                related_oms_load.order_management_id.mark_as_partially_loaded()
            message = (
                f"Sale Order {self.name}linked to OMS Load "
                f" {related_oms_load.order_management_id.reference} has been cancelled"
            )
            related_oms_load.order_management_id.message_post(body=_(message))

        return is_cancelled
