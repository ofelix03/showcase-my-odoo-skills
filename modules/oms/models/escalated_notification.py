from odoo import fields, models


class EscalatedNotification(models.Model):
    _name = "oms.escalated.notification"
    _description = "Escalated Notification"

    name = fields.Char(default="Escalation Notification")
    notify_after = fields.Integer(
        string="Notify After",
        help="Minutes after which any in-activity on an order should "
        "be reported to department HoD be reported to HoD",
    )
    member_ids = fields.One2many(
        comodel_name="oms.escalated.notification.recipient",
        inverse_name="notification_id",
        string="Members",
    )

    def get_form_url(self, order):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        base_url += "/web#id=%d&view_type=form&model=%s" % (order.id, order._name)
        return base_url

    def get_account_members(self):
        member = self.member_ids.search([("department", "=", "account")])
        return member.user_ids if member else None

    def get_marketing_members(self):
        member = self.member_ids.search([("department", "=", "marketing")], limit=1)
        return member.user_ids if member else None

    def get_trading_members(self):
        member = self.member_ids.search([("department", "=", "trading")], limit=1)
        return member.user_ids if member else None

    def get_operation_members(self):
        member = self.member_ids.search([("department", "=", "operation")], limit=1)
        return member.user_ids if member else None

    def get_finance_members(self):
        member = self.member_ids.search([("department", "=", "finance")], limit=1)
        return member.user_ids if member else None

    def get_credit_control_members(self):
        member = self.member_ids.search(
            [("department", "=", "credit_control")], limit=1
        )
        return member.user_ids if member else None

    def notify_members(self, order, inactivity_period):
        additional_values = {
            "order_ref": order.reference,
            "access_link": self.get_form_url(order),
            "inactivity_period": str(inactivity_period),
        }

        if order.state == "draft":
            members = self.get_marketing_members()
        elif order.state == "propose":
            members = self.get_trading_members()
        elif order.state == "confirm":
            members = self.get_credit_control_members()
        elif order.state == "load":
            members = self.get_account_members()
        else:
            members = None

        if members:
            recipients = members.mapped(
                lambda user: "{} <{}>".format(
                    user.partner_id.name, user.partner_id.email
                )
            )
            to_email = ", ".join(recipients)

        email_values = {
            "email_to": to_email,
            "email_from": "apps@quantumgroupgh.com",
            "subject":  "Escalated Notification: Respond to Order Now"
        }

        mail_template = self.env.ref(
            "oms.escalated_notification_mail_template"
        ).with_context(additional_values)

        mail_template.with_context(additional_values).send_mail(
            self.id, email_values=email_values, force_send=True
        )
