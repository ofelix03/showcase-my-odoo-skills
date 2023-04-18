from odoo import fields, models


class EscalatedNotificationRecipient(models.Model):
    _name = "oms.escalated.notification.recipient"
    _description = "Escalated Notification Members"

    department = fields.Selection(
        [
            ("account", "Account"),
            ("marketing", "Marketing"),
            ("trading", "Trading"),
            ("credit_control", "Credit Control"),
            ("operation", "Operation"),
            ("finance", "Finance"),
        ],
        required=True,
    )
    user_ids = fields.Many2many(
        comodel_name="res.users",
        relation="escalated_notification_users",
        column1="notification_id",
        column2="user_id",
        string="Users",
    )
    notification_id = fields.Many2one(comodel_name="oms.escalated.notification")
