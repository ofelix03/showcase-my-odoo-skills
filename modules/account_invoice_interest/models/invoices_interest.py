import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class InvoiceInterest(models.Model):
    _name = "account.invoice.interest"
    _inherit = ["mail.thread"]
    _description = "Invoice Interest"
    _rec_name = "invoice_id"
    _order = "id desc"

    def _get_interest_rate(self):
        return float(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("invoice_interest.annual_interest_rate")
        )

    def _get_daily_interest_rate(self):
        annum_interest_rate = self._get_interest_rate()
        daily_interest_rate = 0
        if annum_interest_rate:
            daily_interest_rate = (self._get_interest_rate() / 365) / 100
        return daily_interest_rate

    invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Invoice",
        domain=[
            ("state", "=", "posted"),
            ("move_type", "=", "out_invoice"),
            ("payment_state", "in", ("not_paid", "partial")),
        ],
        required=True,
    )

    invoice_number = fields.Char(related="invoice_id.name", store=True)

    invoice_state = fields.Selection(
        [
            ("not_paid", "Not Paid"),
            ("in_payment", "In Payment"),
            ("paid", "Paid"),
            ("partial", "Partially Paid"),
            ("reversed", "Reversed"),
            ("invoicing_legacy", "Invoicing App Legacy"),
        ],
        related="invoice_id.payment_state",
        string="Invoice State",
    )

    state = fields.Selection(
        [
            ("accrue", "Accrue"),
            ("accrue_and_collect", "Accrue & Collect"),
            ("contract_debt_collector", "Contracted Debt Collection Company"),
            ("legal_action", "Legal Action"),
        ]
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner", related="invoice_id.partner_id", string="Customer"
    )

    invoice_currency_id = fields.Many2one(
        comodel_name="res.currency", related="invoice_id.currency_id"
    )

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        store=True,
        related="invoice_id.partner_id",
        string="Partner",
    )

    invoice_date = fields.Date(related="invoice_id.invoice_date", string="Invoice Date")

    invoice_due_date = fields.Date(
        related="invoice_id.invoice_date_due", string="Due Date"
    )

    overdue_days = fields.Integer(compute="_compute_total_interest")

    total_interest = fields.Monetary(
        compute="_compute_total_interest",
        currency_field="invoice_currency_id",
        string="Interest Payable",
    )

    outstanding_amount = fields.Monetary(
        related="invoice_id.amount_residual",
        currency_field="invoice_currency_id",
        help="The residual amount on the invoice",
    )
    total_outstanding = fields.Monetary(
        compute="_compute_total_interest",
        currency_field="invoice_currency_id",
        help="The sum of the outstanding amount and interest payable",
    )

    daily_interest_ids = fields.One2many(
        comodel_name="account.invoice.interest.daily",
        inverse_name="invoice_interest_id",
        string="Daily Interests",
        help="This is the daily compounding interest",
    )

    form_is_readonly = fields.Boolean(
        compute="_compute_total_interest",
        help="Form becomes readonly once the first daily "
        "compounding interest is computed",
    )

    last_daily_interest_accrued_at = fields.Datetime(
        string="Last Daily Interest Accrued On",
        help="This is the timestamp for the last computed interest amount",
        readonly=True,
    )

    last_daily_accrued_interest = fields.Monetary(
        string="Last Daily Accrued Interest",
        currency_field="invoice_currency_id",
        readonly=True,
        help="This is the last accrued " "interest amount",
    )

    @api.model
    def get_invoices_after_overdue_days(self):
        after_overdue_days = self._get_after_overdue_days()
        query = """
                   select id from (
                       select id, extract('day' from (now() - invoice_date_due))
                       overdue_days
                       from account_move
                       where payment_state in ('not_paid', 'partial')
                       and move_type = 'out_invoice'
                       and amount_residual > 0
                   ) tbl where overdue_days > %(overdue_days)s
               """
        self.env.cr.execute(query, {"overdue_days": after_overdue_days})
        overdue_60_days_invoice_ids = self.env.cr.fetchall()
        overdue_60_days_invoices = self.env["account.move"].search(
            [("id", "in", overdue_60_days_invoice_ids)]
        )
        return overdue_60_days_invoices

    def _get_invoices_already_accruing_interest(self):
        return self.search([]).mapped(lambda interest: interest.invoice_id)

    @api.onchange("invoice_id")
    def _show_only_open_invoices_overdue_after_grace_interest_period(self):
        invoices = self.get_invoices_after_overdue_days().filtered(
            lambda invoice: invoice.id
            not in self._get_invoices_already_accruing_interest().ids
        )
        return {"domain": {"invoice_id": [("id", "in", invoices.ids)]}}

    def action_view_daily_interest(self):
        action = self.env.ref("invoice_interest.invoice_daily_interest_action").read()[
            0
        ]
        action.update({"domain": [("invoice_interest_id", "=", self.id)]})
        return action

    def action_compute_daily_interest(self):
        value_date = fields.Date.today()
        self.compute_daily_interest(value_date)

    @api.model
    def invoice_already_accruing_interest(self, invoice):
        count = self.env["account.invoice.interest"].search_count(
            [("invoice_id", "=", invoice.id)]
        )
        return count > 0

    def get_invoice_interest_obj(self, invoice):
        return self.env["account.invoice.interest"].search(
            [("invoice_id", "=", invoice.id)]
        )

    @api.model
    def create_invoice_interest(self, invoice):
        return self.create(
            {
                "invoice_id": invoice.id,
            }
        )

    @api.depends("invoice_id")
    def _compute_total_interest(self):
        for rec in self:
            rec.overdue_days = rec.overdue_days
            rec.total_interest = rec.total_interest
            rec.total_outstanding = rec.total_outstanding
            rec.form_is_readonly = rec.form_is_readonly
            if rec.invoice_id:
                if not isinstance(rec.id, models.NewId):
                    query = """
                        select sum(interest_due) from account_invoice_interest_daily
                        where invoice_interest_id = %(invoice_interest_id)s
                        group by invoice_interest_id
                    """
                    self.env.cr.execute(query, {"invoice_interest_id": rec.id})
                    result = self.env.cr.fetchone()
                    total_interest = result[0] if result else 0
                    rec.total_interest = total_interest
                rec.outstanding_amount = rec.invoice_id.amount_residual
                rec.total_outstanding = (
                    rec.total_interest + rec.invoice_id.amount_residual
                )
                rec.overdue_days = (
                    fields.Date.today() - rec.invoice_id.invoice_date_due
                ).days

                rec.form_is_readonly = rec.total_interest > 0

    @api.onchange()
    def filter_invoice_ids(self):
        return {"domain": {"invoice_id": [("date_due", "<", fields.Date.today)]}}

    @api.model
    def _get_after_overdue_days(self):
        days_after_overdue_days = 0
        if self.invoice_id:
            product_name = self.invoice_id.invoice_line_ids[0].product_id.name
            if product_name == "LPG":
                days_after_overdue_days = int(
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param("invoice_interest.lpg_product_after_overdue_days_param")
                )
            elif product_name in ["Gas Oil", "Gasoline"]:
                days_after_overdue_days = int(
                    self.env["ir.config_parameter"]
                    .sudo()
                    .get_param(
                        "invoice_interest.white_product_after_overdue_days_param"
                    )
                )
        return days_after_overdue_days

    def _get_interest_rate_for_value_date(self, value_date):
        InvoiceInterestRate = self.env["account.invoice.interest.rate"]
        rate = InvoiceInterestRate.get_daily_rate(
            self.invoice_currency_id.id, value_date
        )
        if not rate and not self.env.context.get("compute_daily_interest_cron"):
            raise ValidationError(
                _(
                    "No interest rate set for {date} on currency {currency}".format(
                        currency=self.invoice_currency_id.name, date=value_date
                    )
                )
            )

        interest_rate = rate.rate
        daily_interest_rate = (rate.rate / 365) / 100

        return [interest_rate, daily_interest_rate]

    def _update_invoice_interest_state(self, overdue_days):
        """Check overdue and update the state of the invoice if they match
        business rules."""
        product_name = self.invoice_id.invoice_line_ids[0].product_id.name
        if product_name in ("Gas Oil", "Gasoline"):
            if overdue_days <= 120:
                self.write({"state": "accrue"})
            elif overdue_days > 120:
                # @todo if customer doesn't present a valid payment plan
                #  and overdue_days > 180 days, proceed to accrue and collect
                self.write({"state": "accrue"})

        if product_name == "LPG":
            if overdue_days <= 60:
                self.write({"state": "accrue"})
            elif overdue_days > 60:
                # @todo if customer doesn't present a valid payment plan,
                #  and overdue_days > 120 days, proceed to accrue and collect
                self.write({"state": "accrue"})

    def _build_daily_interest_value_dates(self, overdue_days):
        # Build interest value dates from the date_due of the
        # invoice to today or the specified value_date
        interest_value_dates = [self.invoice_id.invoice_date_due]
        for i in range(0, overdue_days):
            interest_value_dates.append(
                self.invoice_id.invoice_date_due + timedelta(days=i + 1)
            )
        return interest_value_dates

    def compute_daily_interest(self, value_date=None):
        """Computes the daily compounding interest, that is.

        Interest(n) = (Principal(n-1) + Interest(n-1)) * Daily Interest Rate
        """
        value_date = value_date or fields.Date.today()
        overdue_days = (value_date - self.invoice_id.invoice_date_due).days
        is_cron = self.env.context.get("compute_daily_interest_cron")

        if self.outstanding_amount == 0 and is_cron:
            # Invoice doesn't have outstanding amount? Well there's no point
            # computing daily interest
            return False
        elif self.outstanding_amount == 0:
            raise ValidationError(
                _("You can not run interest on an invoice with a residual of 0")
            )

        if overdue_days < self._get_after_overdue_days() and is_cron:
            #  We only compute daily interest when invoice is overdue beyound the
            #  'after_overdue_days'
            return False

        if overdue_days < self._get_after_overdue_days() and not is_cron:
            raise ValidationError(
                _(
                    "You can not run interest on "
                    "an invoice not yet overdue by %s days"
                    % self._get_after_overdue_days()
                )
            )

        self._update_invoice_interest_state(overdue_days)

        for value_date in self._build_daily_interest_value_dates(overdue_days):
            if not self.daily_interest_accrued(value_date):
                logging.info(
                    "Invoice Interest: Computing daily accrued "
                    "interest for {value_date} on invoice {invoice}".format(
                        value_date=value_date, invoice=self.invoice_id.name
                    )
                )

                [
                    interest_rate,
                    daily_interest_rate,
                ] = self._get_interest_rate_for_value_date(value_date)

                prev_accrued_interest = self._prev_accrued_interest(value_date)
                principal_amount = self.outstanding_amount + prev_accrued_interest
                interest_due = principal_amount * daily_interest_rate
                outstanding_due = principal_amount + interest_due

                if daily_interest_rate and interest_rate:
                    self.daily_interest_ids.create(
                        {
                            "invoice_interest_id": self.id,
                            "value_date": value_date,
                            "principal_amount": principal_amount,
                            "interest_due": interest_due,
                            "outstanding_due": outstanding_due,
                            "interest_rate": interest_rate,
                            "daily_interest_rate": daily_interest_rate,
                        }
                    )
                    self.write(
                        {
                            "last_daily_interest_accrued_at": fields.Datetime.now(),
                            "last_daily_accrued_interest": interest_due,
                        }
                    )
                logging.info(
                    "Invoices Interest: Done computation "
                    "daily accrued interest for {value_date} on"
                    " invoice {invoice}".format(
                        value_date=value_date, invoice=self.invoice_id.name
                    )
                )

    def _prev_accrued_interest(self, value_date):
        daily_interests = self.daily_interest_ids.search(
            [("invoice_interest_id", "=", self.id), ("value_date", "<", value_date)]
        )
        accrued_interest = sum(
            daily_interests.mapped(lambda interest: interest.interest_due)
        )
        return accrued_interest

    def get_last_daily_interest(self):
        return self.env["account.invoice.interest.daily"].search(
            [("invoice_interest_id", "=", self.id)], limit=1, order="id desc"
        )

    def daily_interest_accrued(self, value_date):
        count = self.env["account.invoice.interest.daily"].search_count(
            [("invoice_interest_id", "=", self.id), ("value_date", "=", value_date)]
        )
        return bool(count)
