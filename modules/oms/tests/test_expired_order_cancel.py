from datetime import datetime

from odoo.tests.common import tagged

from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class ExpiredOrderCancelWizardTransactionCase(TestCommon):
    def test001_cancel_expired_orders(self):
        rec_order_management = self.rec_order_1
        rec_order_management.with_user(self.res_users_marketing_user).write(
            {"datetime": datetime(2021, 4, 21, 10, 10, 10)}
        )

        rec_expired_order_cancel = self.model_oms_cancel_expired_order_wizard.create(
            {
                "reason": "Please do not bother me",
                "expired_order_ids": [rec_order_management.id],
            }
        )

        rec_expired_order_cancel.with_user(
            self.res_users_marketing_user
        ).btn_do_cancel_orders()
