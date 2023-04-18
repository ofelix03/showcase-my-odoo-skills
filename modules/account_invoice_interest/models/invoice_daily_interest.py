from odoo import api, fields, models


class InvoiceInterestDaily(models.Model):
    _name = "account.invoice.interest.daily"
    _description = "Invoice Daily Interest"

    value_date = fields.Date(required=True)

    principal_amount = fields.Monetary(
        required=True, currency_field="invoice_currency_id"
    )

    interest_due = fields.Monetary(required=True, currency_field="invoice_currency_id")

    outstanding_due = fields.Monetary(
        required=True, currency_field="invoice_currency_id"
    )

    invoice_interest_id = fields.Many2one(
        comodel_name="account.invoice.interest",
        string="Invoice Interest",
        ondelete="cascade",
    )

    invoice_currency_id = fields.Many2one(
        comodel_name="res.currency", related="invoice_interest_id.invoice_currency_id"
    )

    interest_rate = fields.Float(
        digits=(4, 5), help="Annual interest rate", readonly=True
    )

    daily_interest_rate = fields.Float(
        digits=(4, 5),
        store=True,
        help="This is the daily interest rate, which is annual interest rate "
        "divided by 365 days",
        readonly=True,
    )

    @api.model
    def read_group(
        self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True
    ):
        """
        Override this Odoo method to take over summing up monetary values of computed
        fields when records are grouped. By default, computed fields values are not
        summed up when records are grouped.
        """
        result = super(InvoiceInterestDaily, self).read_group(
            domain,
            fields,
            groupby,
            offset=offset,
            limit=limit,
            orderby=orderby,
            lazy=lazy,
        )
        if "principal_amount" in fields:
            for line in result:
                if line.get("__domain"):
                    recent_daily_interest = self.search(
                        line["__domain"], order="id desc", limit=1
                    )
                    principal_amount = 0
                    if recent_daily_interest:
                        principal_amount = recent_daily_interest.principal_amount
                    line["principal_amount"] = principal_amount

        if "outstanding_due" in fields:
            for line in result:
                if line.get("__domain"):
                    recent_daily_interest = self.search(
                        line["__domain"], order="id desc", limit=1
                    )
                    outstanding_due = 0
                    if recent_daily_interest:
                        outstanding_due = recent_daily_interest.outstanding_due
                    line["outstanding_due"] = outstanding_due

        if "interest_rate" in fields:
            for line in result:
                if line.get("__domain"):
                    line["interest_rate"] = 0

        if "daily_interest_rate" in fields:
            for line in result:
                if line.get("__domain"):
                    line["daily_interest_rate"] = 0

        return result
