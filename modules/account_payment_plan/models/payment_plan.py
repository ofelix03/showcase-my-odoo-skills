import base64
import logging
import re
import subprocess
from datetime import date, timedelta
from pathlib import Path

import magic
from dateutil import rrule
from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountPaymentPlan(models.Model):
    _name = "account.payment.plan"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _rec_name = "name"
    _description = "Account Payment Plan"
    _order = "submitted_on desc"

    name = fields.Char(string="Reference", readonly=True, copy=False, tracking=True)
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        required=True,
        string="Customer",
        tracking=True,
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        store=True,
        string="Currency",
        compute="_compute_customer_receivable_balance",
        tracking=True,
    )
    amount = fields.Float(
        compute="_compute_customer_receivable_balance",
        store=True,
        copy=False,
        tracking=True,
        string="Balance",
    )
    outstanding_amount = fields.Monetary(
        currency_field="currency_id", string="Balance Outstanding", readonly=True
    )
    received_amount = fields.Monetary(
        currency_field="currency_id",
        string="Balance Received",
        readonly=True,
        help="This is the amount received from customer since the payment plan was "
        "activated. Only customer payments applied to their credit invoices are "
        "considered",
    )
    product_type = fields.Selection(
        selection=[("lpg", "LPG"), ("white_product", "White Product")],
        required=True,
        tracking=True,
    )
    payment_term = fields.Selection(
        selection=[
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("specific", "Specific"),
        ],
        required=True,
        tracking=True,
    )
    submitted_on = fields.Datetime(
        required=True, default=fields.Datetime.now(), tracking=True
    )
    dsa_doc_draft = fields.Binary(string="Draft DSA", tracking=True)
    dsa_doc_draft_filename = fields.Char()
    dsa_doc_finalized = fields.Binary(string="Finalized DSA", tracking=True)
    dsa_doc_finalized_filename = fields.Char()
    schedule_ids = fields.One2many(
        comodel_name="account.payment.plan.schedule",
        inverse_name="payment_plan_id",
        string="Payment Schedule",
        tracking=True,
    )
    decline_history_ids = fields.One2many(
        comodel_name="account.payment.plan.decline.history",
        inverse_name="payment_plan_id",
        string="Decline History",
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("waiting_review", "Waiting Review"),
            ("waiting_approval", "Waiting Approval"),
            ("approved", "Approved"),
            ("legal", "Legal"),
            ("draft_dsa_waiting_approval", "Waiting Draft DSA Approval"),
            ("draft_dsa_approved", "Draft DSA Approved"),
            ("customer_approval", "Waiting Customer Approval"),
            ("customer_approved", "Customer Approved"),
            ("ready", "Ready"),
            ("active", "Active"),
            ("is_defaulting", "Defaulting"),
            ("is_paying", "Is Paying"),
            ("is_fully_paid", "Fully Paid"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )
    start_date = fields.Date(string="Start Date", tracking=True)
    end_date = fields.Date(string="End Date", tracking=True)
    is_declined = fields.Boolean(default=False)
    declined_at_state = fields.Selection(
        selection=[
            ("waiting_review", "Waiting Review"),
            ("waiting_approval", "Waiting Approval"),
            ("customer_approval", "Customer Approval"),
            ("draft_dsa_waiting_approval", "Draft DSA Waiting Approval"),
        ]
    )
    can_edit = fields.Boolean(
        default=lambda self: self.env.user.has_group(
            "account_payment_plan.group_payment_plan_create"
        ),
        string="Can edit",
    )
    invoice_ids = fields.Many2many(
        comodel_name="account.move",
        relation="payment_plan_invoices_rel",
        column1="plan_id",
        column2="invoice_id",
        compute="_compute_customer_invoices",
    )
    payment_ids = fields.Many2many(
        comodel_name="account.payment",
        relation="payment_plan_payments_rel",
        column1="plan_id",
        column2="payment_id",
        compute="_compute_customer_applied_payments",
    )
    unreconciled_payment_ids = fields.Many2many(
        comodel_name="account.payment",
        relation="payment_plan_payments_rel",
        column1="plan_id",
        column2="payment_id",
        compute="_compute_customer_unapplied_payments",
    )
    form_load_trigger = fields.Boolean(compute="_compute_form_load_trigger")
    parent_plan_id = fields.Many2one(
        comodel_name="account.payment.plan",
        string="Original Plan",
        help="Payment plan from which revised plan was created. This plan was will "
        "automatically be cancelled when this revised plan is activated.",
    )

    @api.model
    def _customer_outstanding_overdue_invoices_sql(self):
        return f"""
            select amount_balance,
                    amount_balance_currency
            from (
                select (sum(aml.debit) - sum(coalesce(payments.amount,
                0))) "amount_balance",
                        case when aml.currency_id = 114 then
                            sum(0)
                        else
            (sum(aml.amount_currency) - sum(coalesce(payments.amount_currency, 0)))
                        end "amount_balance_currency"
                from account_move_line aml
                right join account_move am
                on am.id = aml.move_id
                left join account_account aa
                on aa.id = aml.account_id
                left join account_payment_term apt
                on apt.id = am.invoice_payment_term_id
                left join res_partner rp
                on rp.id = am.partner_id
                left join lateral (
                    select debit_move_id,
                            sum(amount) "amount",
                            sum(debit_amount_currency) "amount_currency"
                    from account_partial_reconcile
                    where debit_move_id = aml.id
                    group by debit_move_id
                ) payments
                on payments.debit_move_id = aml.id
                where am.state = 'posted'
                and aa.internal_type = 'receivable'
                and am.move_type = 'out_invoice'
                --and apt.name != 'Immediate Payment'
                and am.payment_state in ('not_paid', 'partial')
                and am.invoice_date_due < now()::date
                and rp.id = {self.partner_id.id}
                group by rp.id, aml.currency_id
                limit 1
            ) tbl
        """

    @api.depends("payment_ids")
    def _compute_form_load_trigger(self):
        self.form_load_trigger = None
        for plan in self:
            plan.onchange_calc_outstanding_customer_balance()
            plan._onchange_calc_total_payments_received()
            plan._apply_payments_received_to_schedules()
            plan._compute_customer_unapplied_payments()

    @api.onchange("partner_id")
    def onchange_calc_outstanding_customer_balance(self):
        if self.partner_id:
            self.env.cr.execute(self._customer_outstanding_overdue_invoices_sql())
            results = self.env.cr.fetchone()
            if results:
                [balance, balance_currency] = results
                if self.currency_id == self.env.user.currency_id:
                    self.outstanding_amount = balance
                else:
                    self.outstanding_amount = balance_currency
            else:
                self.outstanding_amount = 0

    def customers_with_plan(self):
        query = """
            select partner_id
            from account_payment_plan
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        customer_ids = []
        if results:
            customer_ids = list(map(lambda c: c[0], results))

        return customer_ids

    @api.onchange("partner_id")
    def _onchange_show_only_customers_with_overdue_invoices(self):
        self.env.cr.execute(self._customers_with_overdue_invoices_sql())
        results = self.env.cr.fetchall()
        customer_ids = list(map(lambda c: c[0], results))

        customer_ids = list(
            filter(lambda id: id not in self.customers_with_plan(), customer_ids)
        )

        return {"domain": {"partner_id": [("id", "in", customer_ids)]}}

    @api.model
    def _total_payments_received_sql(self):
        return f"""
            select sum(amount) "amount",
                    sum(amount_currency) "amount_currency"
            from (
                select 	am.id,
                        am.name,
                        aml.partner_id,
                        apr.amount,
                        case when aml.currency_id = 114 then
                            0
                        else
                            apr.amount_currency
                        end "amount_currency",
                        apr.payment_date
                from account_move_line aml
                right join account_move am
                on am.id = aml.move_id
                left join account_account aa
                on aa.id = aml.account_id
                left join account_payment_term apt
                on apt.id = am.invoice_payment_term_id
                left join res_partner rp
                on rp.id = am.partner_id
                left join lateral (
                    select debit_move_id,
                            amount "amount",
                            debit_amount_currency "amount_currency",
                            create_date "payment_date"
                    from account_partial_reconcile
                    where debit_move_id = aml.id
                ) apr
                on apr.debit_move_id = aml.id
                where am.state = 'posted'
                and aa.internal_type = 'receivable'
                and am.move_type = 'out_invoice'
                --and apt.name != 'Immediate Payment'
                and am.payment_state in ('not_paid', 'partial')
                and am.invoice_date_due < now()::date
                and rp.id = {self.partner_id.id}
                and apr.payment_date >= '{self.submitted_on}'
            ) tbl
            group by partner_id
            limit 1
        """

    @api.onchange("partner_id", "outstanding_amount")
    def _onchange_calc_total_payments_received(self):
        """
        Calculates the total payments received from customer and applied to their
        invoices since the payment plan was activated.

        Note: Customer payments registered but not applied to their invoices are not
        considered in this calculation.
        """
        if self.is_active_plan():
            self.received_amount = self.amount - self.outstanding_amount

    @api.model
    def _customers_with_overdue_invoices_sql(self):
        return """
            with customer_invoice_overdue_balance as (
                select rp.id "partner_id",
            (sum(aml.debit) - sum(coalesce(payments.amount, 0))) "amount_balance",
                        case when aml.currency_id = 114 then
                            sum(0)
                        else
            (sum(aml.amount_currency) - sum(coalesce(payments.amount_currency, 0)))
                        end "amount_balance_currency"
                from account_move_line aml
                right join account_move am
                on am.id = aml.move_id
                left join account_account aa
                on aa.id = aml.account_id
                left join account_payment_term apt
                on apt.id = am.invoice_payment_term_id
                left join res_partner rp
                on rp.id = am.partner_id
                left join lateral (
                    select debit_move_id,
                            sum(amount) "amount",
                            sum(debit_amount_currency) "amount_currency"
                    from account_partial_reconcile
                    where debit_move_id = aml.id
                    group by debit_move_id
                ) payments
                on payments.debit_move_id = aml.id
                where am.state = 'posted'
                and aa.internal_type = 'receivable'
                and am.move_type = 'out_invoice'
                --and apt.name != 'Immediate Payment'
                and am.payment_state in ('not_paid', 'partial', 'in_payment')
                and am.invoice_date_due < now()::date
                group by rp.id, aml.currency_id
                order by rp.id
            ),
            customer_unreconciled_payments as (
                select am.partner_id,
            -1 * sum(aml.credit - coalesce(apr.amount_reconciled, 0)) "amount_balance",
                        case when aml.currency_id = 114 then
                            sum(0)
                        else
            -1 * sum(aml.amount_currency - coalesce(apr.amount_reconciled_currency, 0))
                        end "amount_balance_currency"
                from account_move am
                left join account_move_line aml
                on am.id = aml.move_id
                left join account_account aa
                on aa.id = aml.account_id
                left join lateral (
                    select apr.credit_move_id,
                            sum(apr.amount) "amount_reconciled",
                    sum(apr.credit_amount_currency) "amount_reconciled_currency"
                    from account_partial_reconcile apr
                    where apr.credit_move_id = aml.id
                    group by apr.credit_move_id
                ) apr
                on apr.credit_move_id = aml.id
                left join res_partner rp
                on rp.id = aml.partner_id
                where am.state = 'posted'
                and aa.internal_type = 'receivable'
                group by am.partner_id, aml.currency_id
            ),
            customer_current_balance as (
                select  partner_id, round(sum(amount_balance), 2) "amount_balance",
                round(sum(amount_balance_currency), 2) "amount_balance_currency"
                from (
                    select partner_id, amount_balance, amount_balance_currency
                    from customer_invoice_overdue_balance
                    union all
                    select partner_id, amount_balance, amount_balance_currency
                    from customer_unreconciled_payments
                ) tbl
                group by partner_id
            )
            select partner_id
            from customer_current_balance
            where amount_balance > 0
        """

    @api.model
    def _customer_invoices_sql(self):
        return f"""
                select
                    am.id
                from account_move_line aml
                right join account_move am
                on am.id = aml.move_id
                left join account_account aa
                on aa.id = aml.account_id
                left join account_payment_term apt
                on apt.id = am.invoice_payment_term_id
                left join res_partner rp
                on rp.id = am.partner_id
                left join lateral (
                    select debit_move_id,
                            sum(amount) "amount",
                            sum(debit_amount_currency) "amount_currency"
                    from account_partial_reconcile
                    where debit_move_id = aml.id
                    group by debit_move_id
                ) payments
                on payments.debit_move_id = aml.id
                where am.state = 'posted'
                and aa.internal_type = 'receivable'
                and am.move_type = 'out_invoice'
                --and apt.name != 'Immediate Payment'
                and am.payment_state in ('not_paid', 'partial', 'in_payment')
                and am.invoice_date_due < now()::date
                and rp.id = {self.partner_id.id}
                order by am.id desc
            """

    @api.depends("partner_id")
    def _compute_customer_invoices(self):
        """
        Compute all invoices that make up the current receivable of the
        customer.
        """
        self.invoice_ids = None
        if self.partner_id:
            self.env.cr.execute(self._customer_invoices_sql())
            results = self.env.cr.fetchall()
            invoice_ids = list(map(lambda r: r[0], results))
            self.invoice_ids = [(6, False, invoice_ids)]

    @api.model
    def _customer_applied_payments_sql(self):
        return f"""
                with customer_credit_invoices_overdue as (
                    select am.id, aml.id "aml_id"
                    from account_move_line aml
                    right join account_move am
                    on am.id = aml.move_id
                    left join account_account aa
                    on aa.id = aml.account_id
                    left join account_payment_term apt
                    on apt.id = am.invoice_payment_term_id
                    left join res_partner rp
                    on rp.id = am.partner_id
                    where am.state = 'posted'
                    and aa.internal_type = 'receivable'
                    and am.move_type = 'out_invoice'
                    and apt.name != 'Immediate Payment'
                    and am.payment_state in ('not_paid', 'partial', 'in_payment')
                    and am.invoice_date_due < now()::date
                    and rp.id = {self.partner_id.id}
                    order by am.id
                ),
                customer_credit_invoices_reconciled_payments as (
                    select ap.id "payment_id"
                        from account_move_line aml
                        left join account_account aa
                        on aa.id = aml.account_id
                        left join account_partial_reconcile apr
                        on apr.debit_move_id = aml.id
                        left join account_move_line payment_line
                        on payment_line.id = apr.credit_move_id
                        left join account_move payment_move
                        on payment_move.id = payment_line.move_id
                        left join account_payment ap
                        on ap.id = payment_move.payment_id
                        where aml.id in (
                            select aml_id from customer_credit_invoices_overdue
                        )
                        and ap.partner_id = {self.partner_id.id}
                        and apr.create_date >= '{self.submitted_on}'
                    )
                select payment_id
                from customer_credit_invoices_reconciled_payments
                order by payment_id desc
            """

    @api.depends("partner_id")
    def _compute_customer_applied_payments(self):
        """
        Find all the customer's payments fully or partially applied to the invoices
        captured by this Payment Plan

        Note: Registered payments that are yet to be applied to customer invoices are
        exempted here.
        """
        self.payment_ids = None
        if self.partner_id:
            self.env.cr.execute(self._customer_applied_payments_sql())
            results = self.env.cr.fetchall()
            payment_ids = list(map(lambda p: p[0], results))
            self.payment_ids = [(6, False, payment_ids)]

    @api.model
    def _customer_unapplied_payments_sql(self):
        return f"""
            select payment_id
                from (
                    select am.partner_id,  am.name, ap.id "payment_id",
                        -1 * sum(aml.credit - coalesce(apr.amount_reconciled, 0))
                         "amount_balance",
                        case when aml.currency_id = 114 then
                            sum(0)
                        else
            -1 * sum(aml.amount_currency - coalesce(apr.amount_reconciled_currency, 0))
                        end "amount_balance_currency"
                    from account_move am
                    left join account_move_line aml
                    on am.id = aml.move_id
                    left join account_account aa
                    on aa.id = aml.account_id
                    left join account_payment ap
                    on ap.id = aml.payment_id
                    left join lateral (
                    select apr.credit_move_id,
                            sum(apr.amount) "amount_reconciled",
                            sum(apr.credit_amount_currency) "amount_reconciled_currency"
                    from account_partial_reconcile apr
                    where apr.credit_move_id = aml.id
                    group by apr.credit_move_id
                    ) apr
                    on apr.credit_move_id = aml.id
                    left join res_partner rp
                    on rp.id = aml.partner_id
                    where am.state = 'posted'
                    and aa.internal_type = 'receivable'
                    and rp.id = {self.partner_id.id}
                    group by am.partner_id, aml.currency_id, ap.id, am.name
                ) tbl where round(amount_balance, 2) != 0
                order by payment_id desc
            """

    @api.depends("partner_id")
    def _compute_customer_unapplied_payments(self):
        """
        Finds all registered customer payments created after the payment plan,
        are yet to be applied to customer's invoices captured in this plan.

        Note: Any customer invoice captured after this plan is activated are exempted
        here.
        """
        self.unreconciled_payment_ids = None
        if self.partner_id.id:
            self.env.cr.execute(self._customer_unapplied_payments_sql())
            results = self.env.cr.fetchall()
            unreconciled_payment_ids = list(map(lambda p: p[0], results))
            self.unreconciled_payment_ids = [(6, False, unreconciled_payment_ids)]

    def _parse_email(self, email):
        company_website = self.env.user.company_id.website

        if "@" in email:
            return email

        company_website_split = re.split("^(https|http)://w+.", company_website)
        if company_website_split:
            company_domain = company_website_split[-1]

        return "".join([email, "@", company_domain])

    def get_parent_plan(self, partner_id):
        return self.search(
            [("partner_id", "=", partner_id), ("state", "!=", "cancelled")], limit=1
        )

    def customer_has_plan(self, partner_id):
        return self.search(
            [
                ("partner_id", "=", partner_id),
                ("state", "!=", "cancelled"),
                ("parent_plan_id", "=", False),
            ],
            limit=1,
        )

    def is_active_plan(self):
        ACTIVE_STATES = ["active", "is_defaulting", "is_paying"]
        return self.state in ACTIVE_STATES

    def is_waiting_review(self):
        return self.state == "waiting_review"

    def is_waiting_approval(self):
        return self.state == "waiting_approval"

    def is_draft_dsa_waiting_approval(self):
        return self.state == "draft_dsa_waiting_approval"

    def is_at_legal(self):
        return self.state == "legal"

    def is_at_customer_approval(self):
        return self.state == "customer_approval"

    def is_at_customer_approved(self):
        return self.state == "customer_approved"

    def mark_as_draft(self):
        self.write({"state": "draft"})

    def mark_as_waiting_review(self):
        self.write({"state": "waiting_review"})

    def mark_as_legal(self):
        self.write({"state": "legal"})

    def mark_as_draft_dsa_approved(self):
        self.write({"state": "draft_dsa_approved"})

    def set_draft_dsa(self, dsa_doc, dsa_doc_filename):
        self.write(
            {"dsa_doc_draft": dsa_doc, "dsa_doc_draft_filename": dsa_doc_filename}
        )

    def set_finalized_dsa(self, dsa_doc, dsa_doc_filename):
        self.write(
            {
                "dsa_doc_finalized": dsa_doc,
                "dsa_doc_finalized_filename": dsa_doc_filename,
            }
        )

    def mark_as_draft_dsa_waiting_approval(self):
        self.write({"state": "draft_dsa_waiting_approval"})

    def mark_as_customer_approved(self):
        self.write({"state": "customer_approved"})

    def mark_as_ready(self):
        self.write({"state": "ready"})

    def decline(self, reason, document):
        declined_at_state = None
        if self.is_waiting_review():
            self.mark_as_draft()
            declined_at_state = "waiting_review"
        elif self.is_waiting_approval():
            self.mark_as_draft()
            declined_at_state = "waiting_approval"
        elif self.is_draft_dsa_waiting_approval():
            self.dsa_doc_draft = None
            self.mark_as_legal()
            declined_at_state = "draft_dsa_waiting_approval"
        self.is_declined = True
        self.register_decline_reason(reason, document, declined_at_state)
        self.set_declined_at_state(declined_at_state)

    def customer_declined_draft_dsa(self, reason, document):
        self.is_declined = True
        declined_at_state = "customer_approval"
        self.register_decline_reason(reason, document, declined_at_state)
        self.set_declined_at_state(declined_at_state)
        self.mark_as_legal()

    def upload_draft_dsa(self, dsa_doc, dsa_doc_filename):
        self.set_draft_dsa(dsa_doc, dsa_doc_filename)
        self.mark_as_draft_dsa_waiting_approval()
        self.send_email_notification_to_approve_team_to_approve_dsa()

    def upload_finalized_dsa(self, dsa_doc, dsa_doc_filename):
        self.set_finalized_dsa(dsa_doc, dsa_doc_filename)
        self._upload_finalized_dsa_to_chatterbox(dsa_doc, dsa_doc_filename)
        self.mark_as_ready()
        self.send_email_notification_to_review_team_cc_all()

    def is_declined_at_review(self):
        return self.declined_at_state == "waiting_review"

    def is_declined_at_approval(self):
        return self.declined_at_state == "waiting_approval"

    def is_declined_at_dsa_approval(self):
        return self.declined_at_state == "draft_dsa_waiting_approval"

    def set_declined_at_state(self, state):
        self.write({"declined_at_state": state})

    def register_decline_reason(self, reason, document, declined_at_state):
        decline_reason = self.env["account.payment.plan.decline.history"].create(
            {
                "payment_plan_id": self.id,
                "reason": reason,
                "declined_by_id": self.env.user.id,
                "declined_at": fields.Datetime.now(),
                "declined_at_state": declined_at_state,
                "document": document,
            }
        )
        return decline_reason

    @api.onchange("submitted_on")
    def onchange_show_only_debtors_without_activated_plan(self):
        customers_with_plan_query = """
               select distinct(partner_id) from account_payment_plan
           """
        self.env.cr.execute(customers_with_plan_query)
        customers_with_plan = self.env.cr.fetchall()
        with_plan_customers_ids = list(
            map(lambda customer: customer[0], customers_with_plan)
        )
        return {"domain": {"partner_id": [("id", "not in", with_plan_customers_ids)]}}

    @api.onchange("submitted_on")
    def _onchange_check_submitted_date(self):
        if self.partner_id:
            self._check_submitted_date_is_present_date()

    @api.constrains("submitted_on")
    def _check_submitted_date(self):
        self._check_submitted_date_is_present_date()

    @api.constrains("schedule_ids")
    def _check_total_expected_receivables(self):
        if self.payment_term == "specific":
            total_expected_amount = sum(
                self.schedule_ids.mapped(lambda schedule: schedule.expected_amount)
            )
            if (
                total_expected_amount < self.amount
                or total_expected_amount > self.amount
            ):
                raise ValidationError(
                    _("Total expected amount must match total " "receivable")
                )

    @api.constrains("start_date", "end_date")
    def _check_start_end_date(self):
        self._check_start_date_is_present_date()
        self._check_end_date_is_future_date()

    @api.onchange("start_date", "end_date", "submitted_on")
    def _onchange_check_start_end_date(self):
        self._check_start_date_is_present_date()
        self._check_end_date_is_future_date()

    @api.onchange("start_date", "end_date", "payment_term", "amount")
    def _onchange_create_scheduled_payments(self):
        self._check_start_date_is_greater_than_end_date()
        self.schedule_ids = [(5, 0, 0)]
        start = 0
        installment_amount = 0
        period_counts = 0
        if all([self.start_date, self.end_date, self.amount > 0]):
            if self.payment_term == "weekly":
                period_counts = (
                    rrule.rrule(
                        rrule.WEEKLY, dtstart=self.start_date, until=self.end_date
                    )
                ).count()
                installment_amount = self.amount / period_counts
            elif self.payment_term == "monthly":
                period_counts = (
                    rrule.rrule(
                        rrule.MONTHLY, dtstart=self.start_date, until=self.end_date
                    )
                ).count()
                installment_amount = self.amount / period_counts
            while start < period_counts:
                time_add = (
                    timedelta(weeks=start)
                    if self.payment_term == "weekly"
                    else relativedelta(months=start)
                )
                payment_date = self.start_date + time_add
                self.schedule_ids.create(
                    {
                        "payment_plan_id": self.id,
                        "expected_payment_date": payment_date,
                        "expected_amount": installment_amount,
                    }
                )
                start += 1

    @api.depends("partner_id")
    def _compute_customer_receivable_balance(self):
        if self.partner_id:
            self.currency_id = self.partner_id.transactional_currency_id
            self.env.cr.execute(self._customer_outstanding_overdue_invoices_sql())
            results = self.env.cr.fetchone()
            if results:
                [balance, balance_currency] = results
                if self.currency_id == self.env.user.currency_id:
                    self.amount = balance
                else:
                    self.amount = balance_currency
            else:
                self.amount = 0

    def _check_submitted_date_is_present_date(self):
        if self.submitted_on and self.submitted_on.date() < date.today():
            raise ValidationError(_("Submitted date can not be a past date"))

    def action_submit_for_review(self):
        if self.schedule_ids:
            total_schedule_amount = sum(self.schedule_ids.mapped("expected_amount"))
            if round(self.amount, 2) != round(total_schedule_amount, 2):
                raise UserError(
                    _(
                        "Please ensure the total amount of the schedule "
                        "lines matches the customers total debt."
                    )
                )

            self.state = "waiting_review"
            self.send_email_notification_to_review_team()
            self.is_declined = False

    def action_add_review_comment(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment.plan.add.review.comment",
            "view_mode": "form",
            "name": "Add Review Comment",
            "target": "new",
            "view_id": self.env.ref(
                "account_payment_plan.add_review_comment_to_plan"
            ).id,
            "context": {"default_payment_plan_id": self.id},
        }

    def submit_for_approval(self, review_comment):
        message = f"Review Comment: {review_comment}"
        self.message_post(body=message)
        self.state = "waiting_approval"
        self.send_email_plan_reviewed()
        self.send_email_notification_to_approve_team(review_comment)

    def action_approve(self):
        self.state = "approved"
        self.send_email_notification_to_review_team_when_approved()
        self.action_forward_to_legal()

    def action_forward_to_legal(self):
        self.state = "legal"
        self.send_email_notification_to_legal_team()

    def action_legal_upload_draft(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.upload.dsa.payment.plan",
            "view_type": "form",
            "view_mode": "form",
            "name": "Upload Draft DSA document",
            "target": "new",
            "view_id": self.env.ref("account_payment_plan.upload_draft_dsa_form").id,
            "context": {"default_payment_plan_id": self.id},
        }

    def action_approve_draft_dsa(self):
        self.mark_as_draft_dsa_approved()
        self.send_email_notification_to_legal_team_when_approved()
        self.action_forward_to_create_group()

    def action_decline_at_draft_dsa_approval(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.decline.payment.plan",
            "view_mode": "form",
            "name": "Decline Draft DSA Document",
            "target": "new",
            "view_id": self.env.ref("account_payment_plan.decline_draft_dsa_form").id,
            "context": {"default_payment_plan_id": self.id},
        }

    def action_forward_to_create_group(self):
        self.state = "customer_approval"
        draft_dsa_doc_pdf = self._convert_draft_dsa_doc_to_pdf()
        self.send_email_notification_to_create_team(draft_dsa_doc_pdf)

    def action_confirm_customer_approved_draft_dsa(self):
        self.mark_as_customer_approved()
        attachment = self._upload_approved_draft_dsa_doc_to_chatterbox(
            self.dsa_doc_draft, self.dsa_doc_draft_filename
        )
        dsa_filename = f"Debt Settlement Agreement - {self.partner_id.name}"
        attachment2 = attachment.copy()
        attachment2.store_fname = dsa_filename
        attachment2.name = dsa_filename
        self.send_email_to_executive_office_to_finalize_dsa(attachment2)

    def action_customer_declined_draft_dsa(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.decline.payment.plan",
            "view_type": "form",
            "view_mode": "form",
            "name": "Customer Declined Payment Plan",
            "target": "new",
            "context": {"default_payment_plan_id": self.id},
            "view_id": self.env.ref(
                "account_payment_plan.customer_declined_draft_dsa_form"
            ).id,
        }

    def action_legal_upload_finalized_dsa(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.upload.dsa.payment.plan",
            "view_type": "form",
            "view_mode": "form",
            "view_id": self.env.ref(
                "account_payment_plan.upload_finalized_dsa_form"
            ).id,
            "name": "Upload Finalized DSA Document",
            "target": "new",
            "context": {"default_payment_plan_id": self.id},
        }

    def action_activate_plan(self):
        if self.parent_plan_id:
            self.parent_plan_id.mark_as_cancelled()
            message = (
                f"Originating plan with reference number "
                f"{self.parent_plan_id.name} has been cancelled after current "
                f"plan was activated"
            )
            self.message_post(body=_(message))

        self.state = "active"
        self.send_email_notification_plan_activated()

    def action_decline_at_approval(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "account.decline.payment.plan",
            "view_type": "form",
            "view_mode": "form",
            "name": "Decline Payment  Plan",
            "target": "new",
            "context": {"default_payment_plan_id": self.id},
            "view_id": self.env.ref(
                "account_payment_plan.decline_payment_plan_form"
            ).id,
        }

    def action_revise_payment_plan(self):
        if not self.is_valid_for_generating_new_plan():
            raise ValidationError(
                _("A new payment plan can only be generate from an active plan.")
            )

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.payment.plan",
            "view_mode": "form",
            "target": "current",
            "view_id": self.env.ref("account_payment_plan.payment_plan_form").id,
            "context": {
                "default_parent_plan_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_currency_id": self.currency_id.id,
                "default_product_type": self.product_type,
                "default_amount": float(self.outstanding_amount),
                "default_submitted_on": fields.Datetime.now(),
            },
        }

    def _check_start_date_is_present_date(self):
        if (
            all([self.start_date, self.submitted_on])
            and self.start_date < self.submitted_on.date()
        ):
            raise ValidationError(_("Start date can not be a past date"))

    def _check_end_date_is_future_date(self):
        if (
            all([self.end_date, self.submitted_on])
            and self.end_date < self.submitted_on.date()
        ):
            raise ValidationError(_("End date can not be a past date"))

    def _check_start_date_is_greater_than_end_date(self):
        if all([self.end_date, self.start_date]) and self.end_date < self.start_date:
            raise ValidationError(_("End date can not be before start date"))

    def update_state(self):
        """
        Method uses the states of the individual payment plan schedules to determine
        and update the state of the payment plan.
        """
        all_schedules_states = self.schedule_ids.mapped(
            lambda _schedule: _schedule.state
        )
        if "is_defaulting" in all_schedules_states:
            state = "is_defaulting"
        elif "is_partially_paid" in all_schedules_states:
            state = "is_paying"
        elif "is_due" in all_schedules_states:
            state = "is_paying"
        elif (
            "is_fully_paid" in all_schedules_states
            and "not_due" in all_schedules_states
        ):
            state = "is_paying"
        elif (
            "is_fully_paid" in all_schedules_states
            and "not_due" not in all_schedules_states
        ):
            state = "is_fully_paid"
        else:
            state = self.state

        self.write({"state": state})

    def _build_scheduled_payments_states_update_when_plan_is_activated(self):
        """
        When a payment plan is activated, the state of all scheduled payments are
        updated to 'not_due'
        """
        schedules_states_vals = []
        for schedule in self.schedule_ids:
            if schedule.expected_payment_date < fields.Date.today():
                state = "is_defaulting"
            elif schedule.expected_payment_date == fields.Date.today():
                state = "is_due"
            else:
                state = "not_due"

            schedules_states_vals.append((1, schedule.id, {"state": state}))

        return {"schedule_ids": schedules_states_vals}

    def available_scheduled_payment_amount(self):
        """
        This is the amount of the customer's payments already applied to their
        invoices but yet to be applied to their scheduled payments.
        """
        total_amount_paid = sum(self.schedule_ids.mapped("actual_amount_paid"))
        available_amount = self.received_amount - total_amount_paid
        return available_amount

    def unpaid_scheduled_payments(self):
        """
        This is a list of scheduled payment that are not fully paid off
        """
        return self.schedule_ids.filtered(lambda r: not r.is_fully_paid())

    @api.model
    def run_cron_check_and_apply_payments_received(self):
        self._apply_payments_received_to_schedules()

    def _apply_payments_received_to_schedules(self):
        active_plans_domain = [
            (
                "state",
                "not in",
                [
                    "draft",
                    "waiting_review",
                    "reviewed",
                    "waiting_approval",
                    "approved",
                    "legal",
                ],
            )
        ]
        for plan in self.search(active_plans_domain):
            available_amount = plan.available_scheduled_payment_amount()
            for schedule in plan.unpaid_scheduled_payments():
                if available_amount == 0:
                    break
                available_amount = schedule.make_or_update_payment(available_amount)

    @api.model
    def run_cron_check_and_mark_due_schedules(self):
        schedules = self.schedule_ids.search([("state", "=", "not_due")])
        due_schedules = schedules.filtered(lambda schedule: schedule.is_due())
        due_schedules.mark_as_due()

    @api.model
    def run_cron_check_and_mark_defaulting_schedules(self):
        schedules = self.schedule_ids.search([("state", "in", ["not_due", "is_due"])])
        defaulting_schedules = schedules.filtered(
            lambda schedule: schedule.is_defaulting()
        )
        defaulting_schedules.mark_as_defaulting()

    @api.model
    def run_cron_notify_treasury_about_defaulting_customers(self):
        """
        Based on a scheduled time, this cron sends Treasury a list of customers who are
        defaulting on their payment plan, along with a list of the actual defaulted
        payments.
        """
        defaulting_customers = self._get_defaulting_customers()
        if defaulting_customers:
            self.send_email_about_defaulting_customers(defaulting_customers)

    def _get_defaulting_customers(self):
        CUSTOMER_ID_INDEX = 0
        CUSTOMER_NAME_INDEX = 1
        PAYMENT_PLAN_ID_INDEX = 2
        PAYMENT_PLAN_REF_INDEX = 3

        query = """
            select rp.id "customer_id",
                rp.name "customer_name",
                app.id "payment_plan_id",
                app.name "payment_plan_ref"
            from account_payment_plan app
            left join account_payment_plan_schedule appr
            on app.id = appr.payment_plan_id
            left join res_partner rp
            on rp.id = app.partner_id
            where appr.state = 'is_defaulting'
            order by expected_payment_date asc
        """
        self.env.cr.execute(query)
        results = self.env.cr.fetchall()
        defaulting_customers = []

        for r in results:
            customers = list(
                filter(
                    lambda customer: customer["customer_id"] == r[CUSTOMER_ID_INDEX],
                    defaulting_customers,
                )
            )
            if customers:
                # add defaulting payment plan to existing customer dictionary
                customer = customers[0]
                updated_defaulting_plans = customer["defaulting_plans"] + [
                    {
                        "payment_plan_id": r[PAYMENT_PLAN_ID_INDEX],
                        "payment_plan_ref": r[PAYMENT_PLAN_REF_INDEX],
                        "payment_plan_link": self._build_payment_plan_link(
                            r[PAYMENT_PLAN_ID_INDEX]
                        ),
                    }
                ]
                customer.update({"defaulting_plans": updated_defaulting_plans})
            else:
                # build a new dictionary for customer
                customer = {
                    "customer_id": r[CUSTOMER_ID_INDEX],
                    "customer_name": r[CUSTOMER_NAME_INDEX],
                    "defaulting_plans": [
                        {
                            "payment_plan_id": r[PAYMENT_PLAN_ID_INDEX],
                            "payment_plan_ref": r[PAYMENT_PLAN_REF_INDEX],
                            "payment_plan_link": self._build_payment_plan_link(
                                r[PAYMENT_PLAN_ID_INDEX]
                            ),
                        }
                    ],
                }
                defaulting_customers.append(customer)

        return defaulting_customers

    def get_defaulting_notifications_recipients(self):
        """
        This is a list of users who should know about customers who are defaulting on
        their payment schedules.
        """
        emails = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("account_payment_plan.defaulting_plan_notification_recipients")
        )

        return emails

    def _build_payment_plan_link(self, plan_id):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        return f"{base_url}/web#id={plan_id}&model=account.payment.plan&view_type=form"

    @api.model
    def send_email_about_defaulting_customers(self, defaulting_customers):
        """
        Send email to appropriate persons about customers who are currently
        defaulting on their scheduled payments. Email contains customers and a list of
        their defaulted payments.
        """
        logging.info(
            "[Account Payment Plan] Sending email to Treasury about defaulting "
            "customers"
        )
        additional_values = {
            "defaulting_customers": defaulting_customers,
        }
        email_values = {
            "email_to": self.get_defaulting_notifications_recipients(),
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.defaulting_schedules_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info(
            "[Account Payment Plan] Email sent successfully to Treasury about "
            "defaulting customers"
        )

    def _get_last_decline_history(self):
        return self.env["account.payment.plan.decline.history"].search(
            [], order="id desc", limit=1
        )

    def _convert_draft_dsa_doc_to_pdf(self):
        timestamp = fields.Datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"Draft Debt Settlement Agreement - {self.partner_id.name}"

        src_bytes = base64.b64decode(self.dsa_doc_draft)
        src_format = magic.from_buffer(src_bytes)
        if "OpenDocument" in src_format:
            format_ = ".odt"
        elif "Microsoft" in src_format:
            format_ = ".docx"
        else:
            format_ = ".pdf"

        src_file = Path(f"/tmp/Draft_DSA_{timestamp}{format_}")
        src_file.write_bytes(src_bytes)

        subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                "/tmp",
                src_file,
            ]
        )
        pdf_file = Path(f"/tmp/Draft_DSA_{timestamp}.pdf")
        datas = base64.b64encode(pdf_file.read_bytes())
        return self.env["ir.attachment"].create(
            {
                "datas": datas,
                "name": filename,
                "store_fname": filename,
                "res_id": self.id,
                "res_model": "account.payment.plan",
            }
        )

    def _upload_finalized_dsa_to_chatterbox(self, dsa_doc, dsa_doc_filename):
        return self.env["ir.attachment"].create(
            {
                "datas": dsa_doc,
                "name": dsa_doc_filename,
                "store_fname": dsa_doc_filename,
                "res_id": self.id,
                "res_model": "account.payment.plan",
            }
        )

    def _upload_approved_draft_dsa_doc_to_chatterbox(self, dsa_doc, dsa_doc_filename):
        return self.env["ir.attachment"].create(
            {
                "datas": dsa_doc,
                "name": dsa_doc_filename,
                "store_fname": dsa_doc_filename,
                "res_id": self.id,
                "res_model": "account.payment.plan",
            }
        )

    @api.model
    def send_email_notification_declined_at_review_stage(self, reason, document):
        """
        When a payment plan is declined at the Review stage, we send a notification to
        Creators to make the necessary changes to the plan to make it acceptable
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify Creators, payment plan "
            f"{self.name} was declined at the review stage"
        )
        recipients_email = self.get_group_create_plan_users_emails()
        recipients_email = ",".join(recipients_email)
        additional_values = {
            "reason": reason,
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }

        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }

        if document:
            history = self._get_last_decline_history()
            email_values["attachment_ids"] = [history.document_ir_attachment]

        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_declined_at_waiting_review_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_declined_at_approval_stage(self, reason, document):
        """
        When a payment plan is declined at the Approval stage, we send a notification to
        both Creators and Reviewers. But only Creators are required to respond to and
        make the necessary requested changes making the plan acceptable.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify both Creators & "
            f"Reviewers payment plan "
            f"{self.name} was declined at the review stage"
        )
        recipients_email = self.get_group_review_plan_users_email()
        recipients_email = ",".join(recipients_email)
        recipients_cc_email = self.get_group_review_plan_users_email()
        recipients_cc_email = ",".join(recipients_cc_email)
        additional_values = {
            "reason": reason,
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_cc": recipients_cc_email,
            "email_from": "apps@quantumgroupgh.com",
        }

        if document:
            additional_values["has_attachment"] = True
            history = self._get_last_decline_history()
            email_values["attachment_ids"] = [history.document_ir_attachment]

        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_declined_at_waiting_approval_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_declined_at_dsa_approval_stage(self, reason, document):
        """
        When a payment plan is declined at the draft DSA Approval stage,
        we send a notification to Legal Team. Legal Team are required to respond and
        come up with a new dsa document
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify Legal Team "
            f"debt settlement agreement document "
            f"{self.name} was declined at the dsa review stage"
        )
        recipients_email = self.get_group_legal_plan_users_email()
        recipients_email = ",".join(recipients_email)
        additional_values = {
            "reason": reason,
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }

        if document:
            history = self._get_last_decline_history()
            email_values["attachment_ids"] = [history.document_ir_attachment.id]

        mail_template = self.env.ref(
            "account_payment_plan"
            ".payment_plan_declined_at_draft_dsa_waiting_approval_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_customer_declined_draft_dsa(self, reason, document):
        logging.info(
            f"[Account Payment Plan] Sending email to notify Legal Team "
            f"debt settlement agreement document "
            f"{self.name} was not accepted by customer"
        )
        recipients_email = self.get_group_legal_plan_users_email()
        recipients_email = ",".join(recipients_email)
        additional_values = {
            "reason": reason,
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }

        if document:
            additional_values["has_attachment"] = True
            history = self._get_last_decline_history()
            email_values["attachment_ids"] = [history.document_ir_attachment.id]

        mail_template = self.env.ref(
            "account_payment_plan.draft_dsa_declined_by_customer_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_review_team(self):
        """
        When a payment plan moves to waiting review state, we send a notification to
        the Review team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Review team payment plan "
            f"{self.name} has reached the waiting review stage"
        )
        recipients_email = self.get_group_review_plan_users_email()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_at_waiting_review_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_plan_reviewed(self):
        """
        When a payment plan is reviewed by the review team,
        we send a notification to the Create group (Marketers).
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Create team payment plan "
            f"{self.name} has been reviewed and accepted"
        )
        recipients_email = self.get_group_create_plan_users_emails()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }

        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_reviewed_and_accepted_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_create_team(self, dsa_doc):
        """
        When dsa is approved and sent by the approve team,
        we send a notification to the Create team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Create team dsa "
            f"{self.name} has been approved and sent"
        )
        recipients_email = self.get_group_create_plan_users_emails()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
            "attachment_ids": [dsa_doc.id],
        }
        mail_template = self.env.ref(
            "account_payment_plan.dsa_approved_and_sent_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_approve_team(self, review_comment):
        """
        When a payment plan moves to waiting approval state, we send a notification to
        the Approve team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Approve team payment plan "
            f"{self.name} has reached the waiting approval stage"
        )
        recipients_email = self.get_group_approve_plan_users_email()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
            "review_comment": review_comment,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_at_waiting_approval_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_approve_team_to_approve_dsa(self):
        """
        When a payment plan moves to dsa waiting approval state, we send a
        notification to
        the Approve team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Approve team payment plan "
            f"{self.name} has reached the dsa waiting approval stage"
        )
        recipients_email = self.get_group_approve_plan_users_email()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_at_dsa_waiting_approval_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_review_team_when_approved(self):
        """
        When a payment plan is approved by the approval team, we send a notification to
        the Review team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Review team payment plan "
            f"{self.name} has been approved"
        )
        recipients_email = self.get_group_review_plan_users_email()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_approved_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_review_team_cc_all(self):
        """
        When a finalized dsa is uploaded by the legal team, we send a notification to
        the Review team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Review team finalized dsa "
            f"{self.name} has been uploaded"
        )
        recipients_email = self.get_group_review_plan_users_email()
        recipients_email = ",".join(recipients_email)
        joined_recipients_cc_email = (
            self.get_group_create_plan_users_emails()
            + self.get_group_approve_plan_users_email()
            + self.get_group_legal_plan_users_email()
            + self.get_group_activate_plan_users_email()
        )
        recipients_cc_email = ",".join(joined_recipients_cc_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_cc": recipients_cc_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.finalized_dsa_uploaded_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_legal_team(self):
        """
        When a payment plan moves to legal state, we send a notification to
        the Legal team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Legal team payment plan "
            f"{self.name} has reached the legal stage"
        )
        recipients_email = self.get_group_legal_plan_users_email()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_at_legal_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_legal_team_when_approved(self):
        """
        When a payment plan dsa is approved by the approval team, we send a
        notification to
        the Legal team.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Legal team draft debt settlement agreement document "
            f"{self.name} has been approved"
        )
        recipients_email = self.get_group_legal_plan_users_email()
        recipients_email = ",".join(recipients_email)

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.draft_dsa_approved_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    def _retrieve_executive_office_emails(self):
        emails = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("account_payment_plan.executive_office_email_recipients")
        )
        return emails

    @api.model
    def send_email_to_executive_office_to_finalize_dsa(self, draft_dsa_doc):
        """
        When a signed dsa is sent by the create team, we send a notification to
        the Executive team to finalize the DSA document.

        We keep the group Create, Approver and Legal in copy
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Legal team signed debt settlement agreement document from the partner"
            f"{self.name} has been sent by the create team"
        )
        recipients_email = self._retrieve_executive_office_emails()
        if not recipients_email:
            raise ValidationError(
                _(
                    "No Executive Office email address found to send "
                    "the approved DSA for "
                    "finalization. Contact Administrator for "
                    "assistance"
                )
            )

        recipients_cc_email = (
            self.get_group_approve_plan_users_email()
            + self.get_group_legal_plan_users_email()
            + self.get_group_create_plan_users_emails()
        )
        recipients_cc_email = ",".join(set(recipients_cc_email))

        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_cc": recipients_cc_email,
            "email_from": "apps@quantumgroupgh.com",
            "attachment_ids": [draft_dsa_doc.id],
        }
        mail_template = self.env.ref(
            "account_payment_plan.customer_approved_draft_dsa_doc_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_to_creators_reviewers(self):
        """
        When a payment plan moves to customer approval state, we send a notification to
        the creators and reviewers.
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Marketing team payment plan "
            f"{self.name} has reached the customer approval stage"
        )
        recipients_email = self.get_group_create_plan_users_emails()
        recipients_email = ",".join(recipients_email)
        recipients_cc_email = self.get_group_review_plan_users_email()
        recipients_cc_email = ",".join(recipients_cc_email)
        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_cc": recipients_cc_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_at_customer_approval_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    @api.model
    def send_email_notification_plan_activated(self):
        """
        When a payment plan activates, we send a notification to
        the creator group, with all other groups in copy of the email
        """
        logging.info(
            f"[Account Payment Plan] Sending email to notify "
            f"Review team payment plan "
            f"{self.name} has been activated"
        )
        recipients_email = self.get_group_create_plan_users_emails()
        recipients_email = ",".join(recipients_email)
        joined_recipients_cc_email = (
            self.get_group_approve_plan_users_email()
            + self.get_group_legal_plan_users_email()
            + self.get_group_review_plan_users_email()
        )
        recipients_cc_email = ",".join(joined_recipients_cc_email)
        additional_values = {
            "payment_plan_link": self._build_payment_plan_link(self.id),
            "payment_plan_ref": self.name,
            "parent_plan_ref": self.parent_plan_id and self.parent_plan_id.name,
            "customer_name": self.partner_id.name,
        }
        email_values = {
            "email_to": recipients_email,
            "email_cc": recipients_cc_email,
            "email_from": "apps@quantumgroupgh.com",
        }
        mail_template = self.env.ref(
            "account_payment_plan.payment_plan_activated_template"
        ).with_context(additional_values)
        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
        logging.info("[Account Payment Plan] Email successfully sent")

    def get_group_create_plan_users_emails(self):
        """
        Returns a list of users who belong to the user group "Create"
        :return: [res.users(1), ...]
        """
        group = self.env.ref("account_payment_plan.group_payment_plan_create")
        return group.users.mapped(lambda user: self._parse_email(user.email))

    def get_group_review_plan_users_email(self):
        """
        Returns a list of users who belong to the user group "Review"
        :return: [res.users(1), ...]
        """
        group = self.env.ref("account_payment_plan.group_payment_plan_review")
        return group.users.mapped(lambda user: self._parse_email(user.email))

    def get_group_approve_plan_users_email(self):
        """
        Returns a list of users who belong to the user group "Approve"
        :return: [res.users(1), ...]
        """
        group = self.env.ref("account_payment_plan.group_payment_plan_approve")
        return group.users.mapped(lambda user: self._parse_email(user.email))

    def get_group_legal_plan_users_email(self):
        """
        Returns a list of users who belong to the user group "Legal"
        :return: [res.users(1), ...]
        """
        group = self.env.ref("account_payment_plan.group_payment_plan_legal")
        return group.users.mapped(lambda user: self._parse_email(user.email))

    def get_group_executve_plan_users_email(self):
        """
        Returns a list of users who belong to the user group "Executive"
        :return: [res.users(1), ...]
        """
        group = self.env.ref("account_payment_plan.group_payment_plan_executive")
        return group.users.mapped(lambda user: self._parse_email(user.email))

    def get_group_activate_plan_users_email(self):
        """
        Returns a list of users who belong to the user group "activate"
        :return: [res.users(1), ...]
        """
        group = self.env.ref("account_payment_plan.group_payment_plan_activate")
        return group.users.mapped(lambda user: self._parse_email(user.email))

    def mark_as_cancelled(self):
        self.state = "cancelled"

    def is_valid_for_generating_new_plan(self):
        return self.state in ("active", "is_defaulting", "is_paying")

    @api.model
    def create(self, vals):
        parent_plan_id = vals["parent_plan_id"]
        if self.customer_has_plan(vals["partner_id"]) and not parent_plan_id:
            raise ValidationError(_("Customer already has a payment plan"))

        vals["name"] = self.env["ir.sequence"].next_by_code("payment.plan.number")
        return super(AccountPaymentPlan, self).create(vals)

    def write(self, vals):
        if "state" in vals and vals["state"] == "active":
            vals.update(
                self._build_scheduled_payments_states_update_when_plan_is_activated()
            )

        res = super(AccountPaymentPlan, self).write(vals)
        return res

    def action_update_plan_info(self):
        """
        When button is clicked, the following actions are taken
        1. Customer's outstanding balance is updated
        2. Customer's  total received and applied payments is updated
        3. Customer's scheduled payments are updated by allocating received and
        applied payments to schedules.
        """
        self.onchange_calc_outstanding_customer_balance()
        self._compute_customer_applied_payments()
        self._onchange_calc_total_payments_received()
        self._apply_payments_received_to_schedules()
        self._compute_customer_unapplied_payments()
