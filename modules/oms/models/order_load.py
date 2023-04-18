from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class OrderLoad(models.Model):
    MODEL_ORDER_LOADING = "oms.order.load"
    MODEL_RES_USERS = "res.users"
    ACTION_WINDOW = "ir.actions.act_window"

    _name = MODEL_ORDER_LOADING
    _description = "Order Loading"
    _rec_name = "name"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        ondelete="cascade",
        string="Order Management",
    )
    order_type = fields.Selection(
        string="Order Type", related="order_management_id.order_type", readonly=True
    )
    order_state = fields.Selection(
        string="Order State", related="order_management_id.state", readonly=True
    )
    load_and_park = fields.Boolean(
        string="Load and Park",
        related="order_management_id.load_and_park",
        readonly=True,
    )
    sale_order_id = fields.Many2one(
        comodel_name="sale.order", string="Sale Order", readonly=True
    )
    sale_order_by = fields.Many2one(
        comodel_name=MODEL_RES_USERS, string="Sale Order By", readonly=True
    )
    hedged_by = fields.Many2one(
        comodel_name=MODEL_RES_USERS, string="Hedged By", readonly=True
    )
    hedge_id = fields.Many2one(
        comodel_name="account.hedge", string="Hedge", ondelete="restrict", readonly=True
    )
    name = fields.Char(string="Reference", readonly=True)
    load_date = fields.Datetime(string="Date", required=True)
    load_by = fields.Many2one(
        comodel_name=MODEL_RES_USERS, string="Load Created By", readonly=True
    )
    quantity = fields.Float(
        string="Loaded Quantity",
        digits=(12, 2),
        readonly=True,
        help="This is the outstanding quantity loaded from this order",
    )
    total_quantity = fields.Float(
        string="Total Quantity",
        help="This is total quantity as specified on the load sheet",
    )
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse", string="Warehouse", readonly=True
    )
    customer_order_number = fields.Char(string="Customer Order No.", readonly=True)
    truck_number = fields.Char(string="Truck No")
    waybill = fields.Binary(string="Waybill", attachment=False)
    waybill_number = fields.Char(string="Waybill Number")
    no_waybill_reason = fields.Char(string="Reason for Waybill Unavailable")
    order_sheet = fields.Binary(string="Order Sheet", attachment=False)
    hedge_status = fields.Selection(
        [("draft", "Draft"), ("hedge", "Hedged")],
        default="draft",
        string="Hedge Status",
    )
    related_load_ids = fields.Many2many(
        comodel_name=MODEL_ORDER_LOADING,
        relation="order_loading_main_other_rel",
        column1="load_id",
        column2="other_load_id",
        string="Related Loads",
        help="These are loads from different "
        "orders that together makes up a single load",
    )
    entry_order_id = fields.Many2one(
        comodel_name="oms.order",
        string="Entry Order",
        help="This is the entry order for loads that spans across multiple orders",
    )
    hide_related_loads_info = fields.Boolean(
        compute="_compute_hide_related_loads_info", default=True
    )
    so_state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("validated", "Validated SO"),
            ("invoiced", "Invoiced SO"),
        ],
        default="draft",
        string="SO State",
    )

    def mark_load_has_validated_so(self):
        self.write({"so_state": "validated"})
        self.order_management_id.update_sos_state()

    def mark_load_has_invoiced_so(self):
        self.write({"so_state": "invoiced"})
        self.order_management_id.update_sos_state()

    def has_validated_so(self):
        return self.so_state == "validated"

    def has_invoiced_so(self):
        return self.so_state == "invoiced"

    def has_draft_so(self):
        return self.so_state == "draft"

    @api.depends("order_type", "related_load_ids")
    def _compute_hide_related_loads_info(self):
        self.hide_related_loads_info = (
            self.order_type == "regular" or len(self.related_load_ids) == 0
        )

    def action_view_sale_order(self):
        sale_order_form_id = self.env.ref("sale.view_order_form").sudo().id
        active_id = self.sale_order_id.id
        return {
            "type": OrderLoad.ACTION_WINDOW,
            "res_model": "sale.order",
            "view_mode": "form",
            "views": [(sale_order_form_id, "form")],
            "name": "Sale Order",
            "res_id": active_id,
            "target": "current",
        }

    def action_view_hedge(self):
        hedge_form_id = self.env.ref("account_hedge.hedging_form").id
        active_id = self.hedge_id.id
        return {
            "type": OrderLoad.ACTION_WINDOW,
            "res_model": "account.hedge",
            "view_mode": "form",
            "views": [(hedge_form_id, "form")],
            "name": "Hedge",
            "res_id": active_id,
            "target": "current",
        }

    def btn_sale_order_wizard(self):
        order = self.order_management_id
        if order:
            return {
                "type": OrderLoad.ACTION_WINDOW,
                "res_model": "oms.generate.sale.order.wizard",
                "view_type": "form",
                "view_mode": "form",
                "target": "new",
                "context": {
                    "partner_id": order.partner_id.id,
                    "default_load_id": self.id,
                    "default_order_management_id": order.id,
                    "default_quantity": self.quantity,
                    "default_warehouse_id": self.warehouse_id.id,
                    "default_customer_order_number": self.customer_order_number,
                    "default_truck_number": self.truck_number,
                },
            }

    def action_edit_load(self):
        return {
            "type": OrderLoad.ACTION_WINDOW,
            "res_model": OrderLoad.MODEL_ORDER_LOADING,
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "res_id": self.id,
            "context": {
                "form_is_readonly": self.so_state == "validated",
                "form_is_readonly_waybill": self.so_state == "invoiced",
            },
        }

    def write(self, vals):
        waybill = ("waybill" in vals and vals["waybill"]) or self.waybill

        no_waybill_reason = (
            "no_waybill_reason" in vals and vals["no_waybill_reason"]
        ) or self.no_waybill_reason

        if not waybill and not no_waybill_reason:
            raise ValidationError(
                _(
                    "Waybill not found on load with reference %s."
                    "State the reason why" % (self.name)
                )
            )

        sale_order_updates = {}
        if "truck_number" in vals and vals["truck_number"]:
            sale_order_updates.update({"truck_no": vals["truck_number"]})

        if "customer_order_number" in vals and vals["customer_order_number"]:
            sale_order_updates.update({"cust_order_no": vals["customer_order_number"]})

        self.sale_order_id.write(sale_order_updates)

        if "quantity" in vals and vals["quantity"]:
            self.sale_order_id.update_sale_lines(product_uom_qty=vals["quantity"])
            self.sale_order_id.update_stock_delivery(product_uom_qty=vals["quantity"])

        return super(OrderLoad, self).write(vals)

    def stock_delivered(self):
        if self.sale_order_id:
            self.sale_order_id.stock_delivered()
        else:
            return False
