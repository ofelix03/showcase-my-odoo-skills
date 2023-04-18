from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoadOrderWizard(models.TransientModel):
    _name = "oms.load.order.wizard"
    _description = "Load Order"

    order_management_id = fields.Many2one(
        comodel_name="oms.order",
        readonly=True,
        default=lambda self: self.env.context.get("order_management_id", False),
    )
    load_datetime = fields.Datetime(default=lambda self: datetime.now(), required=True)
    loaded_quantity = fields.Float(
        string="Loaded Quantity", required=True, digits=(12, 2)
    )
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse", string="Warehouse", required=True
    )
    customer_order_number = fields.Char(string="Customer Order No.", required=True)
    truck_number = fields.Char(string="Truck No", required=True)
    waybill = fields.Binary(string="Waybill", attachment=False)
    waybill_number = fields.Char(string="Waybill Number")
    no_waybill_reason = fields.Char(string="Reason for Waybill Unavailable")
    order_sheet = fields.Binary(string="Order Sheet", attachment=False)
    order_ids = fields.Many2many(comodel_name="oms.order", string="Other Orders")
    show_child_orders = fields.Boolean(string="Top Orders", default=False)
    quantity_is_available = fields.Boolean(default=False)
    quantity_is_available_message = fields.Char(
        compute="_compute_validation_checks", store=False
    )
    quantity_is_unavailable_message = fields.Char(
        compute="_compute_validation_checks", store=False
    )
    order_type = fields.Selection(related="order_management_id.order_type", store=True)

    def _create_load_history(self, order=None, loaded_quantity=None):
        if not order or not loaded_quantity:
            raise ValidationError(
                _(
                    "_create_load_history(...) function requires all of "
                    "these arguments: order, loaded_quantity"
                )
            )

        if not self.waybill and not self.no_waybill_reason:
            raise ValidationError(
                _(
                    "Please upload a waybill / if waybill isn't available, enter the "
                    "reason in the field: Reason for Waybill Unavailable"
                )
            )

        if self.waybill and not self.waybill_number:
            raise ValidationError(_("Please enter waybill number"))

        if self.order_management_id.datetime.date() < self.load_datetime.date():
            raise ValidationError(
                _(
                    "The load date is different from the order date. "
                    "Please select the date when the physical load happened\n"
                    "NB: Physical load date must be the same day the order was created"
                )
            )

        load = self.env["oms.order.load"].create(
            {
                "order_management_id": order.id,
                "warehouse_id": self.warehouse_id.id,
                "quantity": loaded_quantity,
                "total_quantity": self.loaded_quantity,
                "truck_number": self.truck_number,
                "customer_order_number": self.customer_order_number,
                "waybill": self.waybill,
                "waybill_number": self.waybill_number,
                "no_waybill_reason": self.no_waybill_reason,
                "order_sheet": self.order_sheet,
                "load_by": order.env.user.id,
                "name": self._generate_load_name(),
                "load_date": self.load_datetime,
                "entry_order_id": self.order_management_id.id,
            }
        )

        if load.truck_number != order.loading_truck_number:
            order.write({"loading_truck_number": load.truck_number})
        return load

    def _update_order(self, loaded_quantity):
        order = self.order_management_id
        loaded_qty = loaded_quantity + order.loaded_quantity
        if loaded_qty < order.quantity:
            loading_state = "loading"
        else:
            loading_state = "loaded"
        outstanding_qty = order.outstanding_quantity - loaded_quantity
        if order.state == "approve":
            order.write(
                {
                    "loading_state": loading_state,
                    "state": "loading",
                    "loaded_quantity": loaded_qty,
                    "outstanding_quantity": outstanding_qty,
                }
            )
        else:
            order.write(
                {
                    "loading_state": loading_state,
                    "loaded_quantity": loaded_qty,
                    "outstanding_quantity": outstanding_qty,
                }
            )

    @api.onchange("order_management_id")
    def onchange_order_management(self):
        if self.order_management_id:
            self.warehouse_id = self.order_management_id.warehouse_id.id
            if self.order_management_id.order_type == "regular":
                self.loaded_quantity = self.order_management_id.outstanding_quantity

    @api.onchange("loaded_quantity")
    def _filter_order_ids(self):
        order = self.order_management_id
        if (
            self.loaded_quantity > 0
            and self.loaded_quantity > order.outstanding_quantity
        ):
            if (
                order.order_type == "bulk"
                and self.loaded_quantity > order.outstanding_quantity
            ):
                self.show_child_orders = True
                return {
                    "domain": {
                        "order_ids": [
                            ("partner_id", "=", order.partner_id.id),
                            ("warehouse_id", "=", order.warehouse_id.id),
                            ("state", "in", ("loading", "approve")),
                            ("id", "!=", order.id),
                            ("product_id", "=", order.product_id.id),
                            ("order_type", "=", "bulk"),
                        ]
                    }
                }
        else:
            self.show_child_orders = False

    @api.depends("order_ids", "loaded_quantity")
    @api.onchange("order_ids", "loaded_quantity")
    def _compute_validation_checks(self):
        self.quantity_is_unavailable_message = ""
        self.quantity_is_available_message = ""
        available_orders = self._check_quantity_overage_shortage()
        available_quantities = sum(list(map(lambda order: order[1], available_orders)))

        if self.loaded_quantity > available_quantities:
            self.quantity_is_available = False
            remaining_quantity = self.loaded_quantity - available_quantities
            self.quantity_is_unavailable_message = (
                "You do not have enough stock to fulfill this load."
                " You need %s more stocks. "
                "Draw more stocks from other orders of the same OMC."
                % remaining_quantity
            )

        if self.loaded_quantity <= available_quantities:
            self.quantity_is_available = True
            self.quantity_is_available_message = (
                "You have enough stocks to fulfill this load. You can proceed."
            )

    def _check_quantity_overage_shortage(self):
        if self.loaded_quantity <= self.order_management_id.outstanding_quantity:
            return [[self.order_management_id, self.loaded_quantity]]

        needed_quantity = (
            self.loaded_quantity - self.order_management_id.outstanding_quantity
        )
        available_orders = [
            [self.order_management_id, self.order_management_id.outstanding_quantity]
        ]
        available_quantity = self.order_management_id.outstanding_quantity
        for order in self.order_ids:
            if self.loaded_quantity == available_quantity or needed_quantity <= 0:
                raise ValidationError(_("Order has enough outstanding quantity."))
            if needed_quantity > order.outstanding_quantity:
                available_quantity += order.outstanding_quantity
                available_orders.append([order, order.outstanding_quantity])
            elif needed_quantity <= order.outstanding_quantity:
                available_quantity += needed_quantity
                available_orders.append([order, needed_quantity])
            needed_quantity = self.loaded_quantity - available_quantity
        return available_orders

    def _generate_load_name(self):
        order = self.order_management_id
        reference = order.reference
        name_index = len(order.order_loading_ids) + 1
        load_name = "{}/L{}".format(reference, name_index)
        return load_name

    def _raise_invalid_loaded_quantity_exception(self):
        if (
            self.order_management_id.order_type == "regular"
            and self.loaded_quantity > self.order_management_id.outstanding_quantity
        ):
            raise ValidationError(
                _(
                    "Loaded Quantity: {} cannot be more than Outstanding "
                    "Quantity: {}.".format(
                        self.loaded_quantity,
                        self.order_management_id.outstanding_quantity,
                    )
                )
            )
        elif (
            self.order_management_id.order_type == "regular"
            and self.loaded_quantity <= 0
        ):
            raise ValidationError(
                _(
                    "Loaded Quantity: {} cannot be zero or less.".format(
                        self.loaded_quantity
                    )
                )
            )

        self._compute_validation_checks()
        if not self.quantity_is_available:
            raise ValidationError(
                _(
                    "Load quantity can not be fulfilled. Please select "
                    "other OMC's orders with outstanding quantities."
                )
            )

    def btn_do_loaded(self):
        self._raise_invalid_loaded_quantity_exception()

        orders = (
            self._check_quantity_overage_shortage()
        )  # returns [[order, loaded_quantity], [..], ...]

        created_loads = []
        for order in orders:
            [order, loaded_quantity] = order
            if order.state == "approve":
                order.state = "loading"

            created_load = self._create_load_history(order, loaded_quantity)
            created_loads.append(created_load)
            self._update_order(loaded_quantity)

            order.check_and_mark_as_load_and_park()

            if order.state == "fully_validated_sos":
                order.state = "partially_validated_sos"
            elif order.state in ("fully_invoiced_sos", "hedge"):
                order.state = "partially_invoiced_sos"
            self.send_email()

        created_load = None
        for created_load in created_loads:
            related_loads = filter(
                lambda load, _created_load=created_load.id: load.id != _created_load,
                created_loads,
            )
            related_loads = list(map(lambda load: (4, load.id, False), related_loads))
            created_load.write({"related_load_ids": related_loads})

    def send_email(self):
        order = self.order_management_id
        if order:
            customer = order.partner_id.name

            additional_values = {
                "customer": customer,
                "product": order.product_id.name,
                "quantity": str(self.loaded_quantity),
                "uom": order.product_uom_id.name,
                "warehouse": self.warehouse_id.name,
                "access_link": order.get_form_url(),
            }
            apps_email = "apps@quantumgroupgh.com"
            to_emails, not_configured_email_users = order.get_user_emails(
                group_name="group_finance_user"
            )

            email_values = {
                "email_to": to_emails,
                "email_from": apps_email,
                "subject":  "Order Management (Load)"
            }

            mail_template = self.env.ref(
                "oms.order_management_load_mail_template"
            ).with_context(additional_values)

            mail_template.with_context(additional_values).send_mail(
                self.id, email_values=email_values, force_send=True
            )

    @api.constrains("loaded_quantity")
    def _check_loaded_quantity_validity_with_exception(self):
        if not self.loaded_quantity or self.loaded_quantity <= 0.00:
            raise ValidationError(
                _(
                    "Loaded Quantity: {} cannot be a zero or less.".format(
                        self.loaded_quantity
                    )
                )
            )
