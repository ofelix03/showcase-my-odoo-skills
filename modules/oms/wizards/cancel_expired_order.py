from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CancelExpiredOrderWizard(models.TransientModel):
    MODEL_ORDER_MANAGEMENT = "oms.order"

    _name = "oms.cancel.expired.order.wizard"
    _description = "Cancel Expired Order"

    reason = fields.Char(string="Reason", required=True)
    expired_order_ids = fields.Many2many(
        comodel_name=MODEL_ORDER_MANAGEMENT,
        string="Cancellable Orders",
        readonly=True,
        domain="[('state','in', ('draft', 'propose', 'confirm', 'approve')), "
        "('date', '<', current_date)]",
    )

    @api.model
    def _model_order_management(self):
        return self.env[CancelExpiredOrderWizard.MODEL_ORDER_MANAGEMENT]

    @api.model
    def default_get(self, fields):
        is_group_accounting_user = self.env.user.has_group("oms.group_accounting_user")
        is_group_finance_user = self.env.user.has_group("oms.group_finance_user")

        is_group_admin_user = self.env.user.has_group(
            "oms.group_order_management_admin"
        )
        if is_group_accounting_user and not is_group_admin_user:
            raise UserError(
                _("Orders cannot be cancelled by users from the Accounting department.")
            )
        elif is_group_finance_user and not is_group_admin_user:
            raise UserError(
                _("Orders cannot be cancelled by users from the Finance department.")
            )
        record_ids = self.env.context.get("active_ids")
        result = super(CancelExpiredOrderWizard, self).default_get(fields)

        if "expired_order_ids" in fields:
            expired_order_records = self._model_order_management()

            for record_id in record_ids:
                expired_order_record = self._model_order_management.browse(
                    record_id
                ).filtered(
                    lambda o: o.state
                    in (
                        "draft",
                        "propose",
                        "confirm",
                        "approve",
                        "loading",
                    )
                    and o.date < datetime.today().date()
                    and len(o.order_loading_ids) == 0
                )
                expired_order_records |= expired_order_record

            result["expired_order_ids"] = expired_order_records.mapped("id")
        return result

    def btn_do_cancel_orders(self):
        expired_orders = self.expired_order_ids
        if expired_orders:
            for expired_order in expired_orders:
                if expired_order.loaded_quantity == 0:
                    expired_order.write(
                        {
                            "state": "cancel",
                            "cancel_reason": self.reason,
                            "cancelled_by": self.env.user.id,
                        }
                    )
