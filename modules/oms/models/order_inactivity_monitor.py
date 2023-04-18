import math
from datetime import timedelta

from odoo import _, api, exceptions, fields, models


class OrderInactivityMonitor(models.Model):
    MODEL_ORDER_MANAGEMENT_ESCALATED_NOTIFICATION = "oms.escalated.notification"

    _name = "oms.inactivity.monitor"
    _description = "Order Inactivity Monitor"

    @api.model
    def _model_order_management_escalated_notification(self):
        return self.env[
            OrderInactivityMonitor.MODEL_ORDER_MANAGEMENT_ESCALATED_NOTIFICATION
        ]

    order_id = fields.Many2one(
        comodel_name="oms.order",
        required=True,
        ondelete="cascade",
    )
    state_changed_at = fields.Datetime(required=True, default=fields.Datetime.now())
    state = fields.Char(required=True)
    prev_state = fields.Char()
    notification_sent = fields.Boolean(default=False)
    next_notification_at = fields.Datetime(
        help="Minutes after which send the next notification if order remains the same"
    )
    notification_config_id = fields.Many2one(
        comodel_name=MODEL_ORDER_MANAGEMENT_ESCALATED_NOTIFICATION,
        compute="_compute_notification_config",
    )

    def _compute_notification_config(self):
        config = self._model_order_management_escalated_notification().search(
            [], limit=1
        )
        if config:
            self.notification_config_id = config

    @api.model
    def monitor_order(self, order):
        self.create({"order_id": order.id, "state": order.state})

    @api.model
    def update_state(self, order):
        rec = self.get_order(order.id)
        if rec:
            rec.write(
                {
                    "state": order.state,
                    "prev_state": rec.state,
                    "state_changed_at": fields.Datetime.now(),
                    "notification_sent": False,
                    "next_notification_at": None,
                }
            )

    def mark_as_notification_sent(self, order):
        next_notification_at = fields.Datetime.now() + timedelta(
            minutes=self.notification_config_id.notify_after
        )
        self.write(
            {
                "notification_sent": True,
                "prev_state": order.state,
                "next_notification_at": next_notification_at,
            }
        )

    @api.model
    def get_order(self, order_id):
        return self.env["oms.inactivity.monitor"].search(
            [("order_id", "=", order_id)], limit=1
        )

    def should_notify(self):
        should_notify = False
        notification_config = (
            self._model_order_management_escalated_notification().search([], limit=1)
        )
        if not notification_config:
            raise exceptions.UserError(
                _(
                    "You have not set the 'notify_after' parameter "
                    "for escalated notifications"
                )
            )

        if self.next_notification_at:
            now = fields.Datetime.now()
            if now > self.next_notification_at and self.state == self.prev_state:
                should_notify = True
        else:
            time_diff = self.get_inactivity_period()
            if time_diff > notification_config.notify_after:
                should_notify = True
        return should_notify

    def get_inactivity_period(self):
        now = fields.Datetime.now()
        time_diff = math.ceil((now - self.state_changed_at).seconds / 60)
        return time_diff

    def send_notification(self):
        for rec in self:
            if rec.should_notify():
                rec.notification_config_id.notify_members(
                    rec.order_id, rec.get_inactivity_period()
                )
                rec.mark_as_notification_sent(rec.order_id)

    @api.model
    def run_inactivity_notification_cron(self):
        orders = self.search(
            [
                "|",
                ("notification_sent", "=", False),
                ("next_notification_at", "!=", None),
            ]
        )
        if orders:
            orders.send_notification()
