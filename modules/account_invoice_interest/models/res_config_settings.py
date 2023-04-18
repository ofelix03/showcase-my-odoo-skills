from odoo import fields, models


class ResConfigSettings(models.TransientModel):

    _inherit = "res.config.settings"

    lpg_product_after_overdue_days_param = fields.Integer(
        string="LPG Product Compute Interest After",
        config_parameter="invoice_interest.lpg_product_after_overdue_days_param",
    )
    white_product_after_overdue_days_param = fields.Integer(
        string="White Product Compute Interest After",
        config_parameter="invoice_interest.white_product_after_overdue_days_param",
    )
