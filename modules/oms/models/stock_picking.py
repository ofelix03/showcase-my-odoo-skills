from odoo import _, models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        oms_order = self.sale_id.order_management_id
        order_is_reset_to_draft = oms_order and oms_order.state not in (
            "load",
            "partially_loaded",
            "lock_truck",
            "fully_validated_sos",
            "partially_validated_sos",
            "fully_invoiced_sos",
            "partially_invoiced_sos",
            "hedged",
            "partially_hedged",
        )
        if order_is_reset_to_draft:
            raise ValidationError(
                _(
                    "You can not perform stock delivery on a sale "
                    "order whiles the original OMS order with "
                    f"reference {oms_order.reference} "
                    "has been reset to "
                    "draft for corrections"
                )
            )

        return super(StockPicking, self).button_validate()
