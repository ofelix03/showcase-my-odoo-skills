import base64

import magic

from odoo import _, fields, models
from odoo.exceptions import ValidationError

MODEL_PAYMENT_PLAN = "account.payment.plan"


class UploadDSA(models.TransientModel):
    _name = "account.upload.dsa.payment.plan"
    _description = "Wizard for uploading DSA documents"

    payment_plan_id = fields.Many2one(
        comodel_name="account.payment.plan", string="Payment Plan"
    )
    dsa_doc = fields.Binary(string="Document", required=True)
    dsa_doc_filename = fields.Char()

    def _generate_filename(self):
        if self.dsa_doc:
            src_bytes = base64.b64decode(self.dsa_doc)
            src_format = magic.from_buffer(src_bytes)
            filename = "Debt Settlement Agreement"
            if "OpenDocument" in src_format:
                extension = ".odt"
            elif "Microsoft" in src_format:
                extension = ".docx"
            elif "PDF document" in src_format:
                extension = ".dpf"
            else:
                raise ValidationError(
                    _(
                        "Document type not supported. Upload only "
                        "supports documents with extension .odt, "
                        ".docx, and .pdf"
                    )
                )

            return f"{filename}-{self.payment_plan_id.partner_id.name}{extension}"

    def action_upload_draft_dsa(self):
        dsa_doc_filename = f"Draft {self._generate_filename()}"
        self.payment_plan_id.upload_draft_dsa(self.dsa_doc, dsa_doc_filename)

    def action_upload_finalized_dsa(self):
        dsa_doc_filename = self._generate_filename()
        self.payment_plan_id.upload_finalized_dsa(self.dsa_doc, dsa_doc_filename)
