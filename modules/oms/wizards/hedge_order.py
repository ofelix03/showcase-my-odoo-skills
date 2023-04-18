from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HedgeOrderWizard(models.TransientModel):
    _name = "oms.hedge.order.wizard"
    _description = "Hedge Order"

    order_loading_ids = fields.Many2many(
        comodel_name="oms.order.load",
        string="Order Management",
        domain="[('hedge_status','=', 'draft'), ('so_state','=','invoiced')]",
    )
    deal_date = fields.Date(
        string="Date of Deal", help="Date the forex was secured.", required=True
    )
    bank_id = fields.Many2one(comodel_name="res.bank", string="Bank", required=True)
    trade_number = fields.Char(
        string="Trade Number",
        help="Bank's reference number for a particular hedge.",
        required=True,
    )
    spot_rate = fields.Float(string="Spot Rate", digits=(4, 4), required=True)
    forward_rate = fields.Float(string="Forward Rate", digits=(4, 4), required=True)
    usd_amount = fields.Float(
        string="Amount in USD",
        digits=(12, 2),
        required=True,
        compute="_compute_currency_amount",
        readonly=True,
    )
    ghs_amount = fields.Float(
        string="Amount in GHS",
        digits=(12, 2),
        required=True,
        compute="_compute_currency_amount",
        readonly=True,
    )
    maturity_period = fields.Integer(
        string="Maturity Period",
        help="Forward days for which the hedge was secured.",
        required=True,
    )

    @api.model
    def default_get(self, fields):
        record_ids = self.env.context.get("active_ids")
        result = super(HedgeOrderWizard, self).default_get(fields)

        if "order_loading_ids" in fields:
            unhedged_order_load_records = self.env["oms.order.load"]

            for record_id in record_ids:
                order_loading_record = (
                    self.env["oms.order"]
                    .browse(record_id)
                    .order_loading_ids.filtered(
                        lambda ol: ol.so_state == "invoiced"
                        and ol.hedge_status == "draft"
                    )
                )
                unhedged_order_load_records |= order_loading_record

            result["order_loading_ids"] = unhedged_order_load_records.mapped("id")
        return result

    def btn_create_hedge(self):
        order_loadings = self.order_loading_ids

        if order_loadings:
            order_loading_list = [(6, False, self.order_loading_ids.ids)]
            depreciation_rate = (
                (360 / self.maturity_period)
                * ((self.forward_rate / self.spot_rate) - 1)
                * 100
            )
            hedge = self.env["account.hedge"].create(
                {
                    "deal_date": self.deal_date,
                    "bank_id": self.bank_id.id,
                    "trade_number": self.trade_number,
                    "spot_rate": self.spot_rate,
                    "forward_rate": self.forward_rate,
                    "depreciation_rate": depreciation_rate,
                    "usd_amount": self.usd_amount,
                    "ghs_amount": self.ghs_amount,
                    "maturity_period": self.maturity_period,
                    "order_loading_ids": order_loading_list,
                    "show_order": True,
                }
            )
            for order_loading in order_loadings:
                order_loading.write(
                    {
                        "hedge_id": hedge.id,
                        "hedge_status": "hedge",
                        "hedged_by": self.env.user.id,
                    }
                )
                order_loading.order_management_id.update_hedge_state()

    @api.depends("order_loading_ids", "forward_rate")
    def _compute_currency_amount(self):
        self.usd_amount = 0.0
        self.ghs_amount = 0.0
        if self.forward_rate:
            order_loadings = self.order_loading_ids
            total_amount = 0
            for order_loading in order_loadings:
                order = order_loading.order_management_id
                if order.currency_id.name == "GHS":
                    amount = order_loading.quantity * order.proposed_price
                else:
                    amount = (
                        order_loading.quantity
                        * order.proposed_price
                        * order.order_pricing_ids[0].forward_rate
                    )
                total_amount += amount
            self.ghs_amount = total_amount
            self.usd_amount = total_amount / self.forward_rate

    @api.constrains("forward_rate")
    def _check_validity_of_forward_rate_with_exception(self):
        if (self.forward_rate or not self.forward_rate) and self.forward_rate <= 0:
            raise ValidationError(
                _("Forward Rate: {} cannot be zero or less.".format(self.forward_rate))
            )

    @api.constrains("spot_rate")
    def _check_validity_of_spot_rate_with_exception(self):
        if (self.spot_rate or not self.spot_rate) and self.spot_rate <= 0:
            raise ValidationError(
                _("Spot Rate: {} cannot be zero or less.".format(self.spot_rate))
            )

    @api.constrains("maturity_period")
    def _check_validity_maturity_period_with_exception(self):
        if (
            self.maturity_period or not self.maturity_period
        ) and self.maturity_period <= 0:
            raise ValidationError(
                _("Maturity: {} cannot be zero or less.".format(self.maturity_period))
            )

    @api.constrains("deal_date")
    def _check_validity_of_deal_date_with_exception(self):
        if self.deal_date > fields.Date.today():
            raise ValidationError(
                _("Deal Date: {} cannot be a future date.".format(self.deal_date))
            )
