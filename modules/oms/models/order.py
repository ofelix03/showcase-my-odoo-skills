from datetime import datetime
from email.utils import formataddr

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class Order(models.Model):
    MODEL_RES_USERS = "res.users"
    MODEL_ORDER_MODIFICATION_LOG = "oms.order.modification.log"
    MODEL_MAIL_TEMPLATE = "mail.template"
    MODEL_MAIL_MAIL = "mail.mail"
    ACTION_WINDOW = "ir.actions.act_window"
    MARKETING_DEPARTMENT = "Marketing Department"
    TRADING_DEPARTMENT = "Trading Department"
    OMS_ORDER_MAIL_TEMPLATE = "oms.order_management_mail_template"

    _name = "oms.order"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Order"
    _rec_name = "reference"
    _order = "date desc, partner_id asc"

    cancelled_by = fields.Many2one(comodel_name=MODEL_RES_USERS, readonly=True)
    proposed_by = fields.Many2one(comodel_name=MODEL_RES_USERS, readonly=True)
    reproposed_by = fields.Many2one(comodel_name=MODEL_RES_USERS, readonly=True)
    confirmed_by = fields.Many2one(comodel_name=MODEL_RES_USERS, readonly=True)
    approved_by = fields.Many2one(comodel_name=MODEL_RES_USERS, readonly=True)
    loading_by = fields.Many2one(comodel_name=MODEL_RES_USERS, readonly=True)
    reference = fields.Char(string="Reference", readonly=True)
    datetime = fields.Datetime(
        string="Date/Time",
        tracking=True,
        required=True,
        default=lambda self: fields.Datetime.now(),
        copy=False,
    )
    date = fields.Date(
        string="Date",
        tracking=True,
        required=True,
        copy=False,
    )
    order_type = fields.Selection(
        [("regular", "Regular"), ("bulk", "Bulk")],
        default="regular",
        string="Order Type",
        tracking=True,
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        domain="[('is_company','=', True)]",
        string="Customer",
        tracking=True,
        default=lambda self: self.env.context.get("partner_id", False),
        required=True,
    )
    marketer_id = fields.Many2one(
        comodel_name="res.partner",
        domain="[('is_company', '=', False)]",
        tracking=True,
        string="Sales Person",
        help="The marketer who brought in this deal",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        required=True,
        string="Currency",
        tracking=True,
        domain="[('id', 'in', (188, 114))]",
        default=114,
    )
    proposed_price = fields.Float(
        string="Price", tracking=True, required=True, digits=(12, 5)
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        tracking=True,
        domain="[('sale_ok', '=', True)]",
        required=True,
    )
    quantity = fields.Float(
        string="Quantity", tracking=True, required=True, digits=(12, 2)
    )
    amount = fields.Float(
        string="Amount",
        compute="_compute_amount",
        readonly=True,
        store=True,
        digits=(12, 2),
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom", string="Unit of Measure", required=True, default=11
    )
    payment_term_id = fields.Many2one(
        comodel_name="account.payment.term",
        string="Payment Term",
        tracking=True,
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("propose", "Trading"),
            ("confirm", "Credit Control"),
            ("approve", "Operations"),
            ("loading", "Loading"),
            ("load", "Fully Loaded"),
            ("partially_loaded", "Partially Loaded"),
            ("partially_validated_sos", "Partially Validated SOs"),
            ("fully_validated_sos", "Fully Validated SOs"),
            ("partially_invoiced_sos", "Partially Invoiced SOs"),
            ("fully_invoiced_sos", "Fully Invoiced SOs"),
            ("lock_truck", "Truck Locked Down"),
            ("release_truck", "Truck Released"),
            ("hedge", "Hedged"),
            ("partially_hedged", "Partially Hedged"),
            ("cancel", "Cancelled"),
            ("decline", "Declined"),
        ],
        default="draft",
        tracking=True,
    )

    load_and_park = fields.Boolean(
        string="Load and Park", default=False, readonly=True, copy=False
    )
    cancel_reason = fields.Char(
        string="Cancel Reason", readonly=True, tracking=True, copy=False
    )
    credit_limit = fields.Float(
        string="Credit Limit",
        readonly=True,
        compute="_compute_customer_credit_info",
        store=True,
        digits=(12, 2),
    )
    credit_outstanding = fields.Float(
        string="Outstanding Credit",
        readonly=True,
        compute="_compute_credit_details",
        store=True,
        digits=(12, 2),
    )
    credit_term = fields.Char(
        string="Credit Term",
        readonly=True,
        compute="_compute_customer_credit_info",
        store=True,
    )
    total_outstanding = fields.Float(
        string="Outstanding Invoices",
        compute="_compute_credit_details",
        readonly=True,
        store=True,
        digits=(12, 2),
    )
    total_overdue = fields.Float(
        string="Total Overdue Invoices",
        compute="_compute_credit_details",
        readonly=True,
        store=True,
        digits=(12, 2),
    )
    cleared_cheques = fields.Float(
        string="Cleared Cheques",
        readonly=True,
        compute="_compute_customer_credit_info",
        store=True,
        digits=(12, 2),
    )
    draft_cheques = fields.Float(
        string="Draft Cheques",
        readonly=True,
        compute="_compute_customer_credit_info",
        store=True,
        digits=(12, 2),
    )
    presented_cheques = fields.Float(
        string="Presented Cheques",
        readonly=True,
        compute="_compute_customer_credit_info",
        store=True,
        digits=(12, 2),
    )
    returned_cheques = fields.Float(
        string="Returned Cheques",
        readonly=True,
        compute="_compute_customer_credit_info",
        store=True,
        digits=(12, 2),
    )
    comment_section = fields.Text(string="Comment", tracking=True)
    loading_state = fields.Selection(
        [("loading", "Loading"), ("loaded", "Loaded")], string="Status", readonly=True
    )
    loaded_quantity = fields.Float(
        string="Loaded Quantity", readonly=True, digits=(12, 2), copy=False
    )
    outstanding_quantity = fields.Float(
        string="Outstanding Quantity", readonly=True, digits=(12, 2)
    )
    warehouse_id = fields.Many2one(
        comodel_name="stock.warehouse",
        string="Proposed Warehouse",
        readonly=True,
        required=True,
    )
    sale_order_ids = fields.Many2many(
        comodel_name="sale.order",
        compute="_compute_sale_orders",
        string="Sale Order(s)",
    )
    order_hedge_ids = fields.Many2many(
        comodel_name="account.hedge",
        compute="_compute_hedges",
        string="Hedge(s)",
        ondelete="restrict",
    )
    title = fields.Char(readonly=True, compute="_compute_title")
    decline_history_ids = fields.One2many(
        comodel_name="oms.order.decline.history",
        inverse_name="order_management_id",
        string="Decline History",
    )
    trading_decline_status = fields.Boolean(string="Trading Declined", default=False)
    credit_control_decline_status = fields.Boolean(
        string="Credit Control Declined", default=False
    )
    operations_decline_status = fields.Boolean(
        string="Operations Declined", default=False
    )

    order_loading_ids = fields.One2many(
        comodel_name="oms.order.load",
        inverse_name="order_management_id",
        string="Order Loading",
    )
    order_pricing_ids = fields.One2many(
        comodel_name="oms.order.pricing",
        inverse_name="order_management_id",
        string="Order Pricing",
    )
    sale_order_count = fields.Integer(compute="_compute_sale_orders", default=0)
    hedge_count = fields.Integer(compute="_compute_hedges", default=0)
    credit_auto_approved = fields.Boolean(string="Credit Auto Approved", default=False)
    loading_truck_number = fields.Char(
        string="Truck Number",
        tracking=True,
        help="This is the truck expected to load this order",
    )
    invoiced_amount = fields.Float(
        string="Invoiced Amount",
        compute="_compute_invoiced_amount",
        store=True,
        digits=(12, 2),
    )
    # order_reset_to_draft
    reset_to_draft_reason_ids = fields.One2many(
        comodel_name="oms.order.reset.to.draft.reason",
        inverse_name="order_id",
        string="Reset To Draft Reasons",
    )

    def is_draft(self):
        return self.state == "draft"

    def is_proposed(self):
        return self.state == "propose"

    def is_confirmed(self):
        return self.state == "confirm"

    def is_approved(self):
        return self.state == "approve"

    def is_loading(self):
        return self.state == "loading"

    def is_loaded(self):
        return self.state == "load"

    def is_partially_loaded(self):
        return self.state == "partially_loaded"

    def is_hedged(self):
        return self.state == "hedge"

    def is_partially_hedged(self):
        return self.state == "partially_hedged"

    def is_fully_validated_sos(self):
        return self.state == "fully_validated_sos"

    def is_locked_truck(self):
        return self.state == "lock_truck"

    def is_loaded_and_parked(self):
        return self.load_and_park

    def is_released_truck(self):
        return self.state == "release_truck"

    def is_partially_validated_sos(self):
        return self.state == "partially_validated_sos"

    def is_partially_invoiced_sos(self):
        return self.state == "partially_invoiced_sos"

    def is_fully_invoiced_sos(self):
        return self.state == "fully_invoiced_sos"

    @api.model
    def _model_oms_order_modification_log(self):
        return self.env[Order.MODEL_ORDER_MODIFICATION_LOG]

    @api.model
    def _model_mail_template(self):
        return self.env[Order.MODEL_MAIL_TEMPLATE]

    @api.model
    def _model_mail_mail(self):
        return self.env[Order.MODEL_MAIL_MAIL].sudo()

    def run_recompute_orders_invoiced_amounts(self):
        orders = self.search([])
        orders._compute_invoiced_amount()

    def _compute_invoiced_amount(self):
        for order in self:
            if order.state in (
                "fully_invoiced_sos",
                "partially_invoiced_sos",
                "hedge",
                "partially_hedged",
            ):
                invoiced_amount = sum(
                    order.sale_order_ids.mapped(lambda sale: sale.amount_total)
                )
            else:
                invoiced_amount = 0
            order.write({"invoiced_amount": invoiced_amount})

    def update_hedge_state(self):
        loads_len = len(self.sale_order_ids)
        len_hedged_invoices = len(self.order_hedge_ids)

        if loads_len == len_hedged_invoices:
            self.write({"state": "hedge"})
        elif (len_hedged_invoices > 0) and (len_hedged_invoices < loads_len):
            self.write({"state": "partially_hedged"})

    def update_sos_state(self):
        loads_with_validated_sos_len = len(
            list(filter(lambda load: load.has_validated_so(), self.order_loading_ids))
        )
        loads_with_invoiced_sos_len = len(
            list(
                list(
                    filter(lambda load: load.has_invoiced_so(), self.order_loading_ids)
                )
            )
        )
        loads_with_draft_sos_len = len(
            list(
                list(
                    list(
                        filter(lambda load: load.has_draft_so(), self.order_loading_ids)
                    )
                )
            )
        )
        loads_len = len(self.order_loading_ids)

        if loads_with_draft_sos_len == loads_len:
            return

        if loads_with_invoiced_sos_len == loads_len:
            self.mark_sos_as_fully_invoiced()
        elif loads_with_validated_sos_len == loads_len:
            self.mark_sos_as_fully_validated()
        elif (loads_with_invoiced_sos_len > 0) and (
            loads_with_invoiced_sos_len < loads_len
        ):
            self.mark_sos_as_partially_invoiced()
        elif (loads_with_validated_sos_len > 0) and (
            loads_with_validated_sos_len < loads_len
        ):
            self.mark_sos_as_partially_validated()

    def onchange_sos_state(self):
        self.write({"state": ""})

    def mark_sos_as_fully_invoiced(self):
        self.write({"state": "fully_invoiced_sos"})

    def mark_sos_as_partially_invoiced(self):
        self.write({"state": "partially_invoiced_sos"})

    def mark_sos_as_fully_validated(self):
        self.write({"state": "fully_validated_sos"})

    def mark_sos_as_partially_validated(self):
        self.write({"state": "partially_validated_sos"})

    def mark_as_fully_loaded(self):
        self.write({"state": "load"})

    def mark_as_partially_loaded(self):
        self.write({"state": "partially_loaded"})

    def mark_as_approved(self):
        self.write(
            {
                "state": "approve",
                "approved_by": self.env.user.id,
                "outstanding_quantity": self.quantity,
            }
        )

    def unlink(self):
        for order in self:
            if order.state not in ["draft", "propose", "confirm"]:
                raise UserError(
                    _(
                        "You can only delete a document in Draft / Trading / Credit "
                        "Control state."
                    )
                )
        return super(Order, self).unlink()

    def name_get(self):
        result = []
        for record in self:
            if record:
                name = "{} ({}, {})".format(
                    record.reference, record.quantity, record.outstanding_quantity
                )
            result.append((record.id, name))
        return result

    @api.depends("order_loading_ids", "order_loading_ids.sale_order_id")
    def _compute_sale_orders(self):
        for record in self:
            sale_order_ids = record.order_loading_ids.mapped("sale_order_id.id")
            record.sale_order_ids = sale_order_ids
            record.sale_order_count = len(sale_order_ids)

    @api.depends("order_loading_ids", "order_loading_ids.hedge_id")
    def _compute_hedges(self):
        for record in self:
            order_hedge_ids = record.order_loading_ids.mapped("hedge_id.id")
            record.order_hedge_ids = order_hedge_ids
            record.hedge_count = len(order_hedge_ids)

    @api.model
    def create(self, vals):
        vals["reference"] = self.env["ir.sequence"].next_by_code("oms.order.sequence")
        vals["date"] = "datetime" in vals and vals["datetime"] or fields.Date.today()
        rec = super(Order, self).create(vals)
        self.env["oms.inactivity.monitor"].monitor_order(rec)
        return rec

    def write(self, value):
        if not value:
            return
        if (
            ("proposed_price" in value)
            or ("datetime" in value)
            or ("proposed_price" in value)
            or "partner_id" in value
            or "warehouse_id" in value
            or ("quantity" in value)
            or ("product_id" in value)
            or ("product_uom_id" in value)
            or ("currency_id" in value)
            or ("payment_term_id" in value)
        ):
            self._track_order_modification()
        rec = super(Order, self).write(value)
        self.env["oms.inactivity.monitor"].update_state(self)
        return rec

    def _track_order_modification(self):
        self._model_oms_order_modification_log().create(
            {
                "marketer_id": self.env.user.id,
                "order_management_id": self.id,
                "currency_id": self.currency_id.id,
                "proposed_price": self.proposed_price,
                "date": self.datetime,
                "partner_id": self.partner_id.id,
                "warehouse_id": self.warehouse_id.id,
                "quantity": self.quantity,
                "product_id": self.product_id.id,
                "product_uom_id": self.product_uom_id.id,
                "payment_term_id": self.payment_term_id.id,
            }
        )

    @staticmethod
    def _all_have_hedge(order_load_records):
        hedge_ids = order_load_records.filtered(lambda ol: ol.hedge_status == "hedge")
        order_load_ids = order_load_records.mapped("id")
        if len(order_load_ids) > len(hedge_ids):
            return False
        return True

    def generate_title(self):
        OPERATIONS_ACCOUNTING_FINANCE = "OPERATIONS / FINANCE / ACCOUNTING"
        OPERATIONS_ACCOUNTING = "OPERATIONS / ACCOUNTING"
        ACCOUNTING_FINANCE = "FINANCE / ACCOUNTING"
        OPERATIONS_CREDIT_CONTROL = "OPERATIONS / CREDIT CONTROL"
        ACCOUNTING = "ACCOUNTING"
        OPERATIONS = "OPERATIONS"
        FINANCE = "FINANCE"
        title = None
        if self.is_draft():
            title = "MARKETING"
        elif self.is_proposed():
            title = "TRADING"
        elif any([self.is_confirmed(), self.is_locked_truck()]):
            title = "CREDIT CONTROL"
        elif self.is_approved():
            title = OPERATIONS
        elif all([self.is_loading(), self.is_loaded_and_parked()]):
            title = OPERATIONS_CREDIT_CONTROL
        elif all([self.is_loading(), not self.is_loaded_and_parked()]):
            title = OPERATIONS
        elif all([self.is_partially_loaded(), self.is_loaded_and_parked()]):
            title = OPERATIONS_CREDIT_CONTROL
        elif all([self.is_partially_loaded(), not self.is_loaded_and_parked()]):
            title = OPERATIONS_ACCOUNTING
        elif any([self.is_loaded(), self.is_released_truck()]):
            title = ACCOUNTING
        elif all(
            [
                any([self.is_partially_validated_sos(), self.is_fully_validated_sos()]),
                self.is_loading(),
            ]
        ):
            title = OPERATIONS_ACCOUNTING
        elif all(
            [
                any([self.is_partially_validated_sos(), self.is_fully_validated_sos()]),
                self.is_loaded(),
            ]
        ):
            title = ACCOUNTING
        elif all([self.is_partially_invoiced_sos(), self.is_loading()]):
            title = OPERATIONS_ACCOUNTING_FINANCE
        elif all([self.is_partially_invoiced_sos(), not self.is_loaded()]):
            title = ACCOUNTING_FINANCE
        elif all([self.is_fully_invoiced_sos(), self.is_loading()]):
            title = OPERATIONS_ACCOUNTING_FINANCE
        elif all([self.is_fully_invoiced_sos(), not self.is_loading()]):
            title = FINANCE

        return title

    @api.depends("state", "order_loading_ids", "order_hedge_ids")
    def _compute_title(self):
        all_loads_hedged = self._all_have_hedge(self.order_loading_ids)
        if all_loads_hedged and self.loading_state == "loaded":
            self.write({"state": "hedge"})

        self.title = self.generate_title()

    @api.onchange("product_id")
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id.id

    @api.depends("partner_id", "datetime")
    def _compute_credit_details(self):
        for order in self:
            if order.partner_id and order.datetime:
                query = """
                    WITH a AS
                    (
                    select aml.partner_id,
                           aml.id,
                           aml.name,
                           aml.date,
                           aml.debit,
                           aml.credit,
                           (aml.debit-aml.credit) balance
                    from account_move_line aml,
                         account_move am
                    where aml.move_id = am.id
                    and am.state = 'posted'
                    and aml.account_id in
                        (
                        select id
                        from account_account
                        where internal_type = 'receivable'
                        )
                    and aml.partner_id = %s
                    ),
                    b AS
                    (
                    select *
                    from a
                    where date > '%s'::date
                    order by date desc
                    ),
                    c AS
                    (
                    select partner_id,
                           0 as index,
                           'Balance B/f' description,
                           max(date) as date,
                           sum(debit)
                           debit,
                           sum(credit)
                           credit,
                           sum(debit - credit) balance
                    from
                    (
                        select *
                        from a
                        except
                        select *
                        from b
                    )t
                    group by partner_id
                    ),
                    d AS
                    (
                    select partner_id,
                           row_number() over(order by date asc) as index,
                           id,
                           date,
                           name as description,
                           debit,
                           credit,
                           (debit - credit) balance
                    from b
                    ),
                    e AS
                    (
                    select partner_id,
                           index,
                           0 as id,
                           description,
                           date,
                           debit,
                           credit,
                           balance
                    from c
                    union all
                    select partner_id,
                           index,
                           id,
                           description,
                           date,
                           debit,
                           credit,
                           balance
                    from d
                    ),
                    h AS
                    (
                    select partner_id,
                           index,
                           id,
                           description,
                           date,
                           debit,
                           credit,
                           sum(balance) over(order by index asc) as run_bal
                    from e
                    ),
                    f AS
                    (
                    select ap.partner_id,
                           ('%s'::date - line.date::date) AS days,
                           u.residual_payment * (-1) AS residual
                    from (
                          select aml, sum(amount) as residual_payment
                          from (
                               select id as aml,
                                      credit as amount
                               from account_move_line
                               where payment_id is not null
                               and debit = 0
                               union all
                               select credit_move_id as aml,
                                      -sum(amount) as amount
                               from account_partial_reconcile
                               group by credit_move_id
                               ) as t
                          group by aml
                         ) as u,
                         account_move_line as line,
                         account_payment as ap
                    where u.aml = line.id
                         and line.payment_id = ap.id
                         and abs(residual_payment) > 0.01
                    union all
                    select partner_id,
                           ('%s'::date - invoice_date_due::date) as days,
                           amount_residual
                    from account_move
                    where amount_residual > 0.01
                         and payment_state in ('not_paid', 'partial')
                         and move_type = 'out_invoice'
                    ),
                   g AS
                   (
                   select f.partner_id,
                          case when f.days < 0 then f.residual else 0 end as due,
                          case when f.days >= 0 then f.residual else 0 end as overdue
                   from f
                   order by partner_id
                   )
                   select h.index,
                          h.id,
                          h.description,
                          h.date,
                          h.debit,
                          h.credit,
                          h.run_bal,
                          sum(g.due )  as due,
                          sum(g.overdue) as overdue
                   from h, g
                   where h.partner_id = g.partner_id
                   group by h.partner_id, h.index, h.id, h.date, h.description,
                   h.debit, h.credit, h.run_bal
                   order by h.index
                """
                move_line_date = order.datetime
                query = query % (
                    order.partner_id.id,
                    str(move_line_date),
                    str(move_line_date),
                    str(move_line_date),
                )

                order.env.cr.execute(query)
                rec = order.env.cr.fetchall()

                order.total_outstanding = (rec and rec[-1] and rec[-1][6]) or 0
                order.total_overdue = (rec and rec[-1] and rec[-1][8]) or 0

                order.credit_outstanding = (
                    order.partner_id.credit_limit - order.total_outstanding
                )

                #  all today's orders in state approved, confirm, loading,
                #  and loaded are considered in
                #  computing OMCs outstanding credit
                domains = [
                    ("state", "in", ("approve", "confirm", "loading", "loaded")),
                    ("partner_id", "=", self.partner_id.id),
                    ("date", "=", fields.Date.today()),
                    (
                        "id",
                        "!=",
                        self.id if not isinstance(self.id, models.NewId) else False,
                    ),
                ]

                partner_active_orders = self.search(domains)
                if partner_active_orders:
                    total_amount_from_orders = sum(
                        partner_active_orders.mapped(lambda order: order.amount)
                    )
                    order.credit_outstanding -= total_amount_from_orders

    @api.depends("partner_id")
    def _compute_customer_credit_info(self):
        for order in self:
            if order.partner_id and order.datetime:
                query = """
                    select rp.credit_limit,
                           pt.name credit_term,
                           coalesce(cleared,0)::numeric cleared,
                           coalesce(draft,0)::numeric draft,
                           coalesce(presented,0)::numeric presented,
                           coalesce(returned,0)::numeric returned
                    from crosstab(
                        '
                        select qc.customer_id, qc.state, sum(qc.amount)::numeric(14,4)
                        from account_receivable_cheque qc,res_partner rp
                        where rp.id = qc.customer_id
                        and rp.is_company = TRUE
                        --and rp.customer = TRUE
                        and state in (''cleared'', ''draft'', ''presented'',
                        ''returned'')
                        group by qc.customer_id, qc.state
                        order by qc.customer_id, qc.state asc
                        '
                        , 'values (''cleared''::text), (''draft''::text),
                        (''presented''::text), (''returned''::text)'
                        )AS ct
                        (customer_id integer, cleared numeric(14,4), draft numeric(
                        14,4), presented numeric(14,4), returned numeric(14,4))
                    left join res_partner rp
                    on rp.id = ct.customer_id
                    left join account_payment_term pt
                    on rp.customer_payment_term = pt.id
                    where ct.customer_id = %s
                    """
                query = query % (order.partner_id.id)

                order.env.cr.execute(query)
                rec = order.env.cr.fetchall()
                if rec:
                    record = rec[0]
                    order.credit_limit = record[0]
                    order.credit_term = record[1]
                    order.cleared_cheques = record[2]
                    order.draft_cheques = record[3]
                    order.presented_cheques = record[4]
                    order.returned_cheques = record[5]
                else:
                    order.credit_limit = self.partner_id.credit_limit
                    order.credit_term = self.partner_id.property_payment_term_id.name

    @api.onchange("datetime")
    def onchange_update_date_field(self):
        if self.datetime:
            self.write({"date": self.datetime.date()})
    @api.onchange("partner_id")
    def onchange_partner(self):
        for order in self:
            order.payment_term_id = order.partner_id.customer_payment_term

            if order.partner_name_has_lpg_word():
                self.product_id = self.product_id.search(
                    [("name", "=", "LPG")], limit=1
                )
            else:
                self.product_id = self.product_uom_id = None

    def partner_name_has_lpg_word(self):
        """Checks if an OMC name has the word LPG"""
        if self.partner_id:
            return self.partner_id.name.find("LPG") >= 0
        return False

    @api.constrains("datetime")
    def _check_datetime_validity_with_exception(self):
        if self.datetime > datetime.today():
            raise ValidationError(
                _("Date: {} cannot be a future date.".format(self.datetime))
            )

    @api.constrains("quantity")
    def _check_quantity_validity_with_exception(self):
        if not self.quantity or self.quantity <= 0:
            raise ValidationError(
                _("Quantity: {} cannot be a zero or less.".format(self.quantity))
            )

    def get_form_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        base_url += "/web#id=%d&view_type=form&model=%s" % (self.id, self._name)
        return base_url

    def _parse_email(self, email):
        email_split = email.split("@")
        if len(email_split) == 1:
            company = self.env.user.company_id
            if company and company.website:
                domain = company.website
                # prevent sonar raising ssl security regarding
                # `http` strings
                blacklist = [
                    "https://www.",
                    "http://www.",  # //NOSONAR
                    "https://",
                    "http://",  # //NOSONAR
                ]
                for i in blacklist:
                    domain_split = domain.split(i)
                    if len(domain_split) == 2:
                        domain = domain_split.pop()
                email = "".join([email, "@", domain])
        return email

    def get_user_emails(self, group_name=None):
        if group_name is None:
            return
        to_emails = ""
        not_configured_email_users = ""
        group = self.env.ref("oms.{}".format(group_name))
        if group:
            group = group[0]
            to_emails = ", ".join(
                list(
                    map(
                        lambda user: formataddr(
                            (
                                user.partner_id.name,
                                self._parse_email(user.partner_id.email),
                            )
                        ),
                        list(filter(lambda user: user.partner_id.email, group.users)),
                    )
                )
            )
            no_email_users = list(
                map(
                    lambda partner: partner.name,
                    list(filter(lambda user: not user.partner_id.email, group.users)),
                )
            )
        if no_email_users:
            not_configured_email_users = ", ".join(no_email_users)
        return to_emails, not_configured_email_users

    @api.constrains("proposed_price")
    def _check_proposed_price_validity_with_exception(self):
        if not self.proposed_price or self.proposed_price <= 0:
            raise ValidationError(
                _(
                    "Proposed Price: {} cannot be a zero or less.".format(
                        self.proposed_price
                    )
                )
            )

    @api.depends("quantity", "proposed_price", "currency_id")
    def _compute_amount(self):
        for order in self:
            price = order.proposed_price
            quantity = order.quantity
            if price and quantity:
                order.amount = price * quantity

    @staticmethod
    def _get_app_email():
        return "apps@quantumgroupgh.com"

    def notify_credit_control_of_auto_approval_email(self):
        customer = ""
        if self.partner_id:
            customer = self.partner_id.name

        additional_values = {
            "uom": self.product_uom_id.name,
            "customer": customer,
            "product": self.product_id.name,
            "quantity": str(self.quantity),
            "user": self.env.user.name,
            "access_link": self.get_form_url(),
        }
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_credit_control_user"
        )

        email_values = {
            "email_to": to_emails,
            "email_from": "apps@quantumgroupgh.com",
            "subject": "Order Management: Auto Approved By System",
        }

        mail_template = self.env.ref(
            "oms.order_management_system_approved_order_mail_template"
        ).with_context(additional_values)

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def send_email_propose_order(self):
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_trading_user"
        )

        additional_values = {
            "customer": self.partner_id.name,
            "quantity": str(self.quantity),
            "uom": self.product_uom_id.name,
            "product": self.product_id.name,
            "state": "submitted",
            "user": self.env.user.name,
            "department": Order.MARKETING_DEPARTMENT,
            "access_link": self.get_form_url(),
        }

        email_values = {
            "email_to": to_emails,
            "email_from": self._get_app_email(),
            "subject": "Order Management: Proposal",
        }

        mail_template = self.env.ref(Order.OMS_ORDER_MAIL_TEMPLATE).with_context(
            additional_values
        )

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def send_email_confirm_order(self):
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_credit_control_user"
        )

        additional_values = {
            "customer": self.partner_id.name,
            "quantity": str(self.quantity),
            "uom": self.product_uom_id.name,
            "product": self.product_id.name,
            "state": "confirmed",
            "user": self.env.user.name,
            "department": Order.TRADING_DEPARTMENT,
            "access_link": self.get_form_url(),
        }

        email_values = {
            "email_to": to_emails,
            "email_from": self._get_app_email(),
            "subject": "Order Management: Confirmation",
        }

        mail_template = self.env.ref(Order.OMS_ORDER_MAIL_TEMPLATE).with_context(
            additional_values
        )

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def send_email_repropose_order(self):
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_credit_control_user"
        )

        additional_values = {
            "customer": self.partner_id.name,
            "quantity": str(self.quantity),
            "uom": self.product_uom_id.name,
            "product": self.product_id.name,
            "state": "submitted",
            "user": self.env.user.name,
            "department": Order.MARKETING_DEPARTMENT,
            "access_link": self.get_form_url(),
        }

        email_values = {
            "email_to": to_emails,
            "email_from": self._get_app_email(),
            "subject": "Order Management: Reproposal",
        }

        mail_template = self.env.ref(Order.OMS_ORDER_MAIL_TEMPLATE).with_context(
            additional_values
        )

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def send_email_approve_order(self):
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_operations_user"
        )

        additional_values = {
            "customer": self.partner_id.name,
            "quantity": str(self.quantity),
            "uom": self.product_uom_id.name,
            "product": self.product_id.name,
            "state": "approved",
            "user": self.env.user.name,
            "department": "Credit Control Department",
            "access_link": self.get_form_url(),
        }

        email_values = {
            "email_to": to_emails,
            "email_from": self._get_app_email(),
            "subject": "Order Management: Load Approval",
        }

        mail_template = self.env.ref(Order.OMS_ORDER_MAIL_TEMPLATE).with_context(
            additional_values
        )

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    # def send_email(self):
    #     msg = ""
    #     department = ""
    #     to_emails = {}
    #
    #     is_group_trading_user = self.env.user.has_group("oms.group_trading_user")
    #     is_group_credit_control_user = self.env.user.has_group(
    #         "oms.group_credit_control_user"
    #     )
    #     is_group_accounting_user = self.env.user.has_group("oms.group_accounting_user")
    #     is_group_marketing_user = self.env.user.has_group("oms.group_marketing_user")
    #
    #     if is_group_marketing_user:
    #         msg = "submitted"
    #         department = Order.MARKETING_DEPARTMENT
    #         if self.credit_control_decline_status:
    #             to_emails, not_configured_email_users = self.get_user_emails(
    #                 group_name="group_credit_control_user"
    #             )
    #         else:
    #             to_emails, not_configured_email_users = self.get_user_emails(
    #                 group_name="group_trading_user"
    #             )
    #     if is_group_trading_user:
    #         msg = "confirmed"
    #         department = "Trading Department"
    #         to_emails, not_configured_email_users = self.get_user_emails(
    #             group_name="group_credit_control_user"
    #         )
    #     if is_group_credit_control_user or is_group_accounting_user:
    #         msg = "approved"
    #         department = "Credit Control Department"
    #         to_emails, not_configured_email_users = self.get_user_emails(
    #             group_name="group_operations_user"
    #         )
    #     customer = self.partner_id.name
    #
    #     additional_values = {
    #         "customer": customer,
    #         "quantity": str(self.quantity),
    #         "uom": self.product_uom_id.name,
    #         "product": self.product_id.name,
    #         "state": msg,
    #         "user": self.env.user.name,
    #         "department": department,
    #         "access_link": self.get_form_url(),
    #     }
    #
    #     reproposal_state = (
    #                            self.trading_decline_status
    #                            or self.credit_control_decline_status
    #                            or self.operations_decline_status
    #                        ) and "reproposal"
    #
    #     order_state_subjects = {
    #         "propose": "Order Management: Proposal",
    #         "confirm": "Order Management: Confirmation",
    #         "approve": "Order Management: Load Approval",
    #         "reproposal": "Order Management: Reproposal",
    #     }
    #     state = reproposal_state or self.state
    #
    #     subject = order_state_subjects[state]
    #
    #     email_values = {
    #         "email_to": to_emails,
    #         "email_from": self._get_app_email(),
    #         "subject": subject
    #     }
    #
    #     mail_template = self.env.ref(
    #         Order.OMS_ORDER_MAIL_TEMPLATE
    #     ).with_context(additional_values)
    #
    #     mail_template.with_context(additional_values).send_mail(
    #         self.id, email_values=email_values, force_send=True
    #     )

    def send_order_reset_to_draft_email(self, reset_to_draft_reason_obj):
        """
        Send an email to inform all departments, Marketing, Trading, Credit  Control,
        Operations, and Accounts about the reset order and the resaons
        """

        marketing_user_emails, not_configured_email_users = self.get_user_emails(
            "group_accounting_user"
        )
        trading_user_emails, not_configured_email_users = self.get_user_emails(
            "group_trading_user"
        )
        credit_user_emails, not_configured_email_users = self.get_user_emails(
            "group_credit_control_user"
        )

        to_emails = ", ".join(
            [marketing_user_emails, trading_user_emails, credit_user_emails]
        )

        additional_values = {
            "order_number": self.reference,
            "access_link": self.get_form_url(),
            "action_by": self.env.user.partner_id.name,
            "reset_type": reset_to_draft_reason_obj.reset_type.upper(),
            "message": reset_to_draft_reason_obj.message,
        }

        email_values = {
            "email_to": self.env.user.partner_id.email,
            "email_cc": to_emails,
            "email_from": self._get_app_email(),
            "subject": "Order Management: Order Reset to Draft ({reference})".format(
                reference=self.reference
            ),
        }

        mail_template = self.env.ref("oms.reset_order_to_draft_mail_template2")
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def decline_email(self):
        department = ""
        subject = ""

        is_group_trading_user = self.env.user.has_group("oms.group_trading_user")
        is_group_credit_control_user = self.env.user.has_group(
            "oms.group_credit_control_user"
        )

        is_group_operations_user = self.env.user.has_group("oms.group_operations_user")

        if is_group_trading_user:
            department = Order.TRADING_DEPARTMENT
            subject = "Order Management: Trading Declined"
        elif is_group_credit_control_user:
            department = "Credit Control Department"
            subject = "Order Management: Credit Control Declined"
        elif is_group_operations_user:
            department = "Operations Department"
            subject = "Order Management: Operations Declined"
        customer = self.partner_id.name

        additional_values = {
            "customer": customer,
            "quantity": str(self.quantity),
            "uom": self.product_uom_id.name,
            "product": self.product_id.name,
            "state": "declined",
            "user": self.env.user.name,
            "department": department,
            "access_link": self.get_form_url(),
        }
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_marketing_user"
        )
        email_values = {
            "email_to": to_emails,
            "email_from": self._get_app_email(),
            "subject": subject,
        }

        mail_template = self.env.ref(Order.OMS_ORDER_MAIL_TEMPLATE).with_context(
            additional_values
        )

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def btn_do_approve(self):
        self._approve_order()

    def btn_do_activate_load_park(self):
        self.load_and_park = True
        self._approve_order()

    def btn_do_release_truck(self):
        truck_numbers = self._get_truck_list()
        if self.state != "lock_truck":
            self.load_and_park = False
        else:
            self.write({"state": "release_truck", "load_and_park": False})
        if truck_numbers:
            self._truck_release_mail()

    def _get_truck_list(self):
        truck_numbers = []
        loads = self.env["oms.order.load"].search(
            [("order_management_id", "=", self.id)]
        )
        for load in loads:
            truck_numbers.append(load.truck_number)
        truck_numbers = ", ".join([str(truck_number) for truck_number in truck_numbers])
        return truck_numbers

    def _truck_release_mail(self):
        additional_values = {
            "truck_numbers": self._get_truck_list(),
            "customer": self.partner_id.name,
            "access_link": self.get_form_url(),
        }
        to_emails, not_configured_email_users = self.get_user_emails(
            group_name="group_operations_user"
        )
        email_values = {
            "email_to": to_emails,
            "email_from": self._get_app_email(),
            "subject": "Order Management (Truck Release)",
        }

        mail_template = self.env.ref("oms.truck_release_mail_template").with_context(
            additional_values
        )

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )

    def has_loads(self):
        return len(self.order_loading_ids)

    def is_fully_loaded(self):
        total_loads = self.get_total_loads()
        return self.quantity == total_loads

    def get_total_loads(self):
        return sum(self.order_loading_ids.mapped(lambda load: load.quantity))

    def _approve_order(self):
        self.credit_auto_approved = self.env.context.get("is_auto_approved")
        self.mark_as_approved()
        if self.credit_auto_approved:
            self.notify_credit_control_of_auto_approval_email()

        # Now if this order was earlier reset, and sale orders already exists in draft
        # state, update the price unit of such sale orders if the reason for the reset
        # to draft was about wrong price
        pricing_info = self.get_latest_pricing_info()
        if self.was_reset_to_draft() and self.has_loads():
            sale_orders = self.order_loading_ids.mapped(lambda load: load.sale_order_id)
            sale_orders.update_sale_lines(price_unit=pricing_info.final_price)

            if self.is_fully_loaded():
                self.mark_as_fully_loaded()
            else:
                self.mark_as_partially_loaded()

        self.send_email_approve_order()

    def btn_do_propose(self):
        issue = self.reset_to_draft_reason_ids.get_order_issue(self)
        if issue and issue.old_value in [self.proposed_price, self.quantity]:
            message = (
                "{reset_type}: The issue that existed before the reset to draft "
                "action remains unresolved. Old value {old_value}".format(
                    reset_type=issue.reset_type.upper(), old_value=issue.old_value
                )
            )
            raise ValidationError(_(message))

        self.write({"proposed_by": self.env.user.id, "state": "propose"})
        self._compute_invoiced_amount()
        self.send_email_propose_order()
        # self.send_email()

    def btn_do_repropose(self):
        self._compute_customer_credit_info()
        self._compute_credit_details()
        change_ids = (
            self._model_oms_order_modification_log()
            .search([("order_management_id", "=", self.id)])
            .ids
        )
        if len(change_ids) > 0:
            latest_change_id = max(change_ids)
            latest_change = self._model_oms_order_modification_log().search(
                [("id", "=", latest_change_id)]
            )
            if (
                (self.currency_id.id == latest_change.currency_id.id)
                and (self.product_uom_id.id == latest_change.product_uom_id.id)
                and (self.product_id.id == latest_change.product_id.id)
                and (self.warehouse_id.id == latest_change.warehouse_id.id)
                and (self.quantity == latest_change.quantity)
                and (self.payment_term_id.id == latest_change.payment_term_id.id)
                and (self.partner_id.id == latest_change.partner_id.id)
                and (self.datetime == latest_change.date)
            ):
                if self.credit_control_decline_status:
                    self.state = "confirm"
                    self.send_email_repropose_order()
                    # self.send_email()
                    self.credit_control_decline_status = False
                else:
                    self.state = "propose"
                    self.send_email_repropose_order()
                    # self.send_email()
                    self.write(
                        {
                            "trading_decline_status": False,
                            "credit_control_decline_status": False,
                        }
                    )
        else:
            if self.credit_control_decline_status:
                self.state = "confirm"
                self.send_email_repropose_order()
                # self.send_email()
                self.credit_control_decline_status = False
            elif self.trading_decline_status or self.operations_decline_status:
                self.state = "propose"
                self.send_email_repropose_order()
                # self.send_email()
                self.trading_decline_status = False
                self.operations_decline_status = False
        self.reproposed_by = self.env.user.id

        # once re-proposed, we find out if, system can auto approve on behalf of
        # credit control
        # if self.is_auto_approvable_by_credit_control():
        #     new_self = self.with_context(is_auto_approved=True)
        #     new_self.sudo().btn_do_approve()

    def btn_do_loading(self):
        self.write(
            {
                "state": "loading",
                "loading_state": "loading",
                "loading_by": self.env.user.id,
            }
        )

    def btn_do_load(self):
        return {
            "type": Order.ACTION_WINDOW,
            "res_model": "oms.load.order.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {"order_management_id": self.id},
        }

    def btn_do_confirm(self):
        return {
            "type": Order.ACTION_WINDOW,
            "res_model": "oms.price.order.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {"order_management_id": self.id},
        }

    def btn_create_sale_order(self):
        return {
            "type": Order.ACTION_WINDOW,
            "res_model": "oms.generate.sale.order.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {
                "order_management_id": self.id,
                "partner_id": self.partner_id.id,
            },
        }

    def action_view_sale_orders(self):
        action = self.env.ref("sale.action_quotations").sudo().read()[0]
        sale_order_ids = self.sale_order_ids.mapped("id")
        action["domain"] = [("id", "in", sale_order_ids)]
        return action

    def action_view_hedges(self):
        action = self.env.ref("account_hedge.hedging_action").sudo().read()[0]
        order_hedge_ids = self.order_hedge_ids.mapped("id")
        action["domain"] = [("id", "in", order_hedge_ids)]
        return action

    def btn_do_decline(self):
        return {
            "type": Order.ACTION_WINDOW,
            "res_model": "oms.decline.order.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {"order_management_id": self.id},
        }

    def btn_do_cancel(self):
        return {
            "type": Order.ACTION_WINDOW,
            "res_model": "oms.cancel.order.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {"order_management_id": self.id},
        }

    def has_stocks_delivered(self):
        """
        This checks if the stocks on the sale orders generated for the loads have been
        generated and validated
        """
        if not len(self.order_loading_ids):
            return False

        loads_stock_delivered = []
        for load in self:
            loads_stock_delivered.append(load.order_loading_ids.stock_delivered())

        return any(loads_stock_delivered)

    def btn_do_reset_to_draft(self):
        if self.has_stocks_delivered():
            raise ValidationError(
                _(
                    "Can not reset to draft an order that has "
                    "validated stock deliveries"
                )
            )

        if self.state in (
            "fully_invoiced_sos",
            "partially_invoiced_sos",
            "hedged",
            "cancelled",
            "declined",
        ):
            raise ValidationError(
                _("Can not reset to draft an order that has already been invoiced")
            )

        return {
            "type": Order.ACTION_WINDOW,
            "name": "Reset To Draft",
            "res_model": "oms.reset.order.to.draft.wizard",
            "view_type": "form",
            "view_mode": "form",
            "target": "new",
            "context": {"default_order_id": self.id},
        }

    def is_auto_approvable_by_credit_control(self):
        """
        This function checks if this order can by auto approved by the system on
        behalf of Credit Control,
        without any member of the team manually approving it by click the approve
        button.

        A customer is auto approved if he meets the following requirements
        1. Has this order has an amount <= credit limit
        2. Has no outstanding overdue invoice i.e overdue invoice <= 0
        3. The credit_block field on the customer is not set to true
        """

        if self.partner_id.credit_blocked:
            return False

        # this means OMC is not a credit customer, hence no need to check credit
        # worthiness
        if self.partner_id.credit_limit == 0 and (
            self.total_overdue >= 0 or self.total_outstanding >= 0
        ):
            return False
        elif self.partner_id.credit_limit == 0:
            return abs(self.total_outstanding) >= self.amount

        total_cheques = self.cleared_cheques

        has_overdue_invoices = False
        total_cheques = total_cheques - self.total_overdue
        if self.total_overdue > 0 > total_cheques:
            has_overdue_invoices = True

        outstanding_credit = self.partner_id.credit_limit - self.total_outstanding

        #  all today's orders in state approved, confirm loading, and loaded are
        #  considered in computing OMCs
        #  outstanding credit
        domains = [
            ("state", "in", ("approve", "confirm", "loading", "loaded")),
            ("partner_id", "=", self.partner_id.id),
            ("date", "=", fields.Date.today()),
            ("id", "!=", self.id if not isinstance(self.id, models.NewId) else False),
        ]

        active_orders = self.search(domains)
        if active_orders:
            total_amount_from_orders = sum(
                active_orders.mapped(lambda order: order.amount)
            )
            outstanding_credit -= total_amount_from_orders

        self.credit_outstanding = outstanding_credit

        if self.credit_outstanding <= 0:
            has_exceeded_credit_limit = total_cheques < self.amount
        else:
            has_exceeded_credit_limit = (
                self.amount > self.credit_outstanding
            ) and total_cheques < (self.amount - self.credit_outstanding)

        not_auto_approvable = has_exceeded_credit_limit or has_overdue_invoices

        return not not_auto_approvable

    def run_unfulfilled_orders_cancellation(self):
        """
        This finds all orders that not were not loaded, and are date earlier than today
        """
        today = fields.Date.today()
        orders = self.env["oms.order"].search(
            [
                ("date", "<", today),
                (
                    "state",
                    "not in",
                    [
                        "cancel",
                        "partially_loaded",
                        "partially_validated_sos",
                        "fully_validated_sos",
                        "partially_invoiced_sos",
                        "fully_invoiced_sos",
                        "hedge",
                        "partially_hedged",
                    ],
                ),
            ]
        )
        for order in orders:
            if order.date < today and len(order.order_loading_ids) == 0:
                order.sudo().write(
                    {
                        "state": "cancel",
                        "cancel_reason": "System scheduled cron cancelled "
                        "this order because it was not loaded",
                        "cancelled_by": order.env.user.id,
                    }
                )

    def was_reset_to_draft(self):
        return self.reset_to_draft_reason_ids.search_count([])

    def reset_to_draft(self, reset_type=None, message=None):
        if reset_type == "wrong_quantity" and self.has_stocks_delivered():
            raise ValidationError(
                _(
                    "You can not reset this order to draft because "
                    "we found "
                    "stock delivery already created on the "
                    "associated sale order. "
                    "The action permissible is to cancel this order. "
                    "First request Accounting department to cancel "
                    "the sale order associated to this order"
                )
            )

        if reset_type == "wrong_price":
            old_value = self.proposed_price
        else:
            old_value = self.quantity

        self.reset_to_draft_reason_ids.create(
            {
                "message": message,
                "reset_type": reset_type,
                "order_id": self.id,
                "old_value": old_value,
            }
        )

        # reset order state to draft
        self.state = "draft"

        self.message_post(body=message)

        self.send_order_reset_to_draft_email(
            self.reset_to_draft_reason_ids.get_order_issue(self)
        )

    def check_and_mark_as_load_and_park(self):
        if self.outstanding_quantity == 0 and self.state in (
            "loading",
            "partially_loaded",
        ):
            self.state = self.load_and_park and "lock_truck" or "load"

        if self.outstanding_quantity > 0 and self.state == "loading":
            self.state = self.load_and_park and "lock_truck" or "partially_loaded"

    def get_latest_pricing_info(self):
        return self.order_pricing_ids.search(
            [("order_management_id", "=", self.id)], order="id desc", limit=1
        )
