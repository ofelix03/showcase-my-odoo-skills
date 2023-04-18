from datetime import date

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PaymentPlanSchedule(models.Model):
    _name = "account.payment.plan.schedule"
    _description = "Payment Schedule"

    payment_plan_id = fields.Many2one(
        comodel_name="account.payment.plan", string="Payment Plan"
    )
    payment_plan_state = fields.Selection(related="payment_plan_id.state")
    currency_id = fields.Many2one(
        comodel_name="res.currency", related="payment_plan_id.currency_id"
    )
    can_edit = fields.Boolean(related="payment_plan_id.can_edit")
    payment_term = fields.Selection(
        related="payment_plan_id.payment_term", string="Payment Term"
    )
    expected_payment_date = fields.Date()
    actual_payment_date = fields.Date()
    expected_amount = fields.Float()
    actual_amount_paid = fields.Float()
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("not_due", "Not Due"),
            ("is_due", "Due"),
            ("is_defaulting", "Defaulting"),
            ("is_partially_paid", "Partially Paid"),
            ("is_fully_paid", "Fully Paid"),
        ],
        default="draft",
        readonly=True,
    )

    def is_fully_paid(self):
        return self.state == "is_fully_paid"

    def _check_and_raise_expected_date_must_be_present(self):
        invalid_expected_date = (
            self.expected_payment_date
            and self.expected_payment_date < self.payment_plan_id.submitted_on.date()
        )
        if invalid_expected_date:
            raise ValidationError(
                _(
                    "Expected date of schedule can not be before "
                    "payment plan submission date"
                )
            )

    def unpaid_amount(self):
        return self.expected_amount - self.actual_amount_paid

    def _check_and_raise_actual_payment_date_must_be_ahead_of_expected_date(self):
        if (
            self.expected_payment_date
            and self.actual_payment_date
            and self.actual_payment_date < self.expected_payment_date
        ):
            raise ValidationError(
                _("Actual payment date can not be before expected date")
            )

    @api.onchange("actual_payment_date", "expected_payment_date")
    def _onchange_validate_dates(self):
        if self.actual_payment_date and self.expected_payment_date:
            self._check_and_raise_expected_date_must_be_present()
            self._check_and_raise_actual_payment_date_must_be_ahead_of_expected_date()

    def _find_state(self, latest_vals):
        """
        Determine the state of the schedule using the below rules:

        1. If expected_payment_date is earlier than today, and actual_amount is 0
                then ==> is_defaulting
        2. If actual_payment_date is set and actual_amount_paid is >
        expected_amount_paid
                then ==> is_partially_paid
        3. If actual_payment_date is set and actual_amount_paid is >=
        expected_amount_paid
                then ==> is_fully_paid
        4. If not condition 1, 2 or 3
                then ==> not_due
        """
        if (
            self.expected_payment_date <= date.today()
            and latest_vals["actual_amount_paid"] == 0.00
        ):
            state = "is_defaulting"
        elif (
            latest_vals["actual_payment_date"]
            and latest_vals["actual_amount_paid"] < self.expected_amount
        ):
            state = "is_partially_paid"
        elif (
            latest_vals["actual_payment_date"]
            and latest_vals["actual_amount_paid"] >= self.expected_amount
        ):
            state = "is_fully_paid"
        else:
            state = "not_due"

        return state

    def is_due(self):
        return (
            self.expected_payment_date == fields.Date.today()
            and self.actual_amount_paid == 0
        )

    def mark_as_due(self):
        for schedule in self:
            schedule.write({"state": "is_due"})
            schedule.payment_plan_id.update_state()

    def is_defaulting(self):
        return (
            self.expected_payment_date < fields.Date.today()
            and self.actual_amount_paid < self.expected_amount
        )

    def mark_as_defaulting(self):
        for schedule in self:
            schedule.write({"state": "is_defaulting"})
            schedule.payment_plan_id.update_state()


    def make_or_update_payment(self, available_amount):
        if self.is_fully_paid():
            return available_amount

        if available_amount > self.unpaid_amount():
            pay_amount = self.unpaid_amount()
            available_amount_balance = available_amount - self.unpaid_amount()
        else:
            pay_amount = available_amount
            available_amount_balance = 0

        self.write(
            {
                "actual_payment_date": fields.Date.today(),
                "actual_amount_paid": self.actual_amount_paid + pay_amount,
            }
        )
        self.payment_plan_id.update_state()

        return available_amount_balance

    def write(self, vals):
        if "actual_amount_paid" in vals:
            vals["actual_payment_date"] = (
                "actual_payment_date" in vals
                and vals["actual_payment_date"]
                or self.actual_payment_date
            )
            vals["state"] = self._find_state(vals)

        return super(PaymentPlanSchedule, self).write(vals)
