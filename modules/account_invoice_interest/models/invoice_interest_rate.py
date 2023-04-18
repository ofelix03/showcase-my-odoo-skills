from odoo import api, fields, models


class InvoiceInterestRate(models.Model):
    _name = "account.invoice.interest.rate"
    _description = "Invoice Interest Rates"
    _rec_name = "currency_id"

    _sql_constraints = [
        ("currency_uniq", "unique(currency_id)", "Currency already exists!")
    ]

    currency_id = fields.Many2one(
        comodel_name="res.currency", string="Currency", required=True
    )
    current_rate = fields.Float(compute="_compute_latest_rate", digits=(7, 5))
    daily_interest_rate_ids = fields.One2many(
        comodel_name="account.invoice.interest.rate.daily",
        inverse_name="rate_id",
        string="Daily Interest Rates",
    )

    def _compute_latest_rate(self):
        for _rate in self:
            rate = _rate.daily_interest_rate_ids.search(
                [("rate_id", "=", _rate.id)], order="date desc", limit=1
            )
            _rate.current_rate = rate.rate

    @api.model
    def get_daily_rate(self, currency_id, date):
        rate = self.search([("currency_id", "=", currency_id)])
        daily_invoice_rate = rate.daily_interest_rate_ids.search(
            [("date", ">=", date), ("rate_id", "=", rate.id)], order="date asc", limit=1
        )
        if not daily_invoice_rate:
            # if date has no available rate, use the prevailing rate
            daily_invoice_rate = rate.daily_interest_rate_ids.search(
                [("rate_id", "=", rate.id)], order="date desc", limit=1
            )
        return daily_invoice_rate


class InvoiceInterestRateDaily(models.Model):
    _name = "account.invoice.interest.rate.daily"
    _description = "Invoice Daily Interest Rate"
    _order = "date asc"

    rate_id = fields.Many2one(
        comodel_name="account.invoice.interest.rate", ondelete="cascade"
    )
    date = fields.Date(required=True)
    rate = fields.Float(required=True, digits=(7, 5))

    _sql_constraints = [
        (
            "unique_date_rate_id",
            "unique(rate_id,date)",
            "Can not have more than one rate for any date",
        )
    ]

    @api.model
    def create(self, vals):
        vals["rate_id"] = self.env.context.get("active_id")
        return super(InvoiceInterestRateDaily, self).create(vals)
