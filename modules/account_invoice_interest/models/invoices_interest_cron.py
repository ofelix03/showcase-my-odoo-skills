import logging
import threading

from odoo import api, fields, models, registry


class InterestComputationCron(models.TransientModel):
    _name = "account.invoice.interest.cron"
    _description = "Invoices Interest Cron"

    def generate_daily_interest(self):
        value_date = fields.Date.today()
        InvoiceInterest = self.env["account.invoice.interest"]
        invoices = InvoiceInterest.get_invoices_after_overdue_days()
        logging.info(
            "Invoice Interest: Started computing daily interest "
            "on {invoices_len} invoices for "
            "value date {value_date}".format(
                invoices_len=len(invoices), value_date=value_date
            )
        )

        for invoice in invoices:
            # run each invoice's interest computation in it's own thread, with a new
            # cursor
            t1 = threading.Thread(
                target=self._compute_invoice_daily_interest,
                args=[self, invoice, value_date],
            )
            t1.daemon = True
            t1.start()

    @staticmethod
    def _compute_invoice_daily_interest(self_obj, invoice, value_date):
        with api.Environment.manage():
            with registry(self_obj.env.cr.dbname).cursor() as new_cr:
                new_env = api.Environment(
                    new_cr, self_obj.env.uid, self_obj.env.context
                )
                InvoiceInterest = new_env["account.invoice.interest"]
                invoice_interest = InvoiceInterest.get_invoice_interest_obj(invoice)
                if not invoice_interest:
                    invoice_interest = InvoiceInterest.create_invoice_interest(invoice)
                invoice_interest.with_context(
                    compute_daily_interest_cron=True
                ).compute_daily_interest(value_date)
