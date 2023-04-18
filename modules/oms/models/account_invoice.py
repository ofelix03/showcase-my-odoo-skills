from odoo import api, models

SALE_ORDER = "sale.order"


class AccountInvoice(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        """
        Override the method to check if sale order was generated
        through the Order Management module.
        And if check is true, mark the SO associated to the load as invoiced
        """
        invoice = super(AccountInvoice, self)._post(soft)
        if invoice and isinstance(self.invoice_origin, str):
            origins = list(
                map(lambda origin: origin.strip(" "), self.invoice_origin.split(","))
            )
            orders = self.env[SALE_ORDER].search([("name", "in", origins)])
            for order in orders:
                if order and order.load_id:
                    order.load_id.mark_load_has_invoiced_so()
                    order.order_management_id._compute_invoiced_amount()
        return invoice

    def has_oms_origin(self):
        has_oms_origin = False
        invoice = super(AccountInvoice, self)._post()
        if invoice and isinstance(self.invoice_origin, str):
            origins = list(
                map(lambda origin: origin.strip(" "), self.invoice_origin.split(","))
            )
            orders = self.env[SALE_ORDER].search([("name", "in", origins)])
            has_oms_origin = any(orders.mapped("load_id"))
        return has_oms_origin

    def attach_waybill_number_and_doc(self):
        """
        Attach OMS waybill number, attachment and order sheet if any to invoice
        """
        for invoice in self:
            if all([invoice.move_type == "out_invoice", invoice.invoice_origin]):
                so_numbers = list(
                    map(lambda num: num.strip(), invoice.invoice_origin.split(","))
                )
                sale_orders = self.env["sale.order"].search(
                    [("name", "in", so_numbers)], order="name desc"
                )

                for inv_line in invoice.invoice_line_ids:
                    _sale_orders = sale_orders.filtered(
                        lambda o: o.order_line[0].product_uom_qty
                        == round(inv_line.quantity, 4)
                        and o.order_line[0].price_subtotal
                        == round(inv_line.price_subtotal, 2)
                        and o.cust_order_no == inv_line.cust_order_no
                    )
                    if _sale_orders:
                        sale_order = _sale_orders[0]
                        load = self.env["oms.order.load"].search(
                            [("sale_order_id", "=", sale_order.id)], limit=1
                        )
                    inv_line.waybill_no = load.waybill_number if load else None
                    inv_line.attach_waybill_doc_to_invoice_line(load)
                    inv_line.attach_order_sheet_to_invoice(load)

    @api.model_create_multi
    def create(self, vals_list):
        invoices = super(AccountInvoice, self).create(vals_list)
        invoices.attach_waybill_number_and_doc()
        return invoices
