from datetime import date

from odoo.tests.common import tagged

from ..tests.common import TestCommon


@tagged("-at_install", "post_install")
class OrderHedgeWizardTransactionCase(TestCommon):
    def create_order_hedge_wizard_record(self):
        rec_order_hedge_wizard = self.model_oms_hedge_order_wizard.create(
            {
                "order_loading_ids": [self.rec_order_load_1.id],
                "deal_date": date(2021, 4, 23),
                "bank_id": self.rec_bank.id,
                "trade_number": "TRADE001",
                "spot_rate": 4.2,
                "forward_rate": 4.3,
                "maturity_period": 20,
            }
        )

        return rec_order_hedge_wizard

    def test001_create_hedge(self):
        # self.model_oms_hedge_order_wizard.create({
        #     "order_loading_ids": [self.rec_order_load_1.id],
        #     "deal_date": date(2021, 4, 23),
        #     "bank_id": self.rec_bank.id,
        #     "trade_number": "TRADE001",
        #     "spot_rate": 4.2,
        #     "forward_rate": 4.3,
        #     "maturity_period": 20,
        # })

        rec_order_hedge_wizard = self.create_order_hedge_wizard_record()

        rec_order_hedge_wizard.with_user(self.res_users_finance_user).btn_create_hedge()
