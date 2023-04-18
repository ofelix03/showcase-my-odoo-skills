{
    "name": "Invoice Interest",
    "summary": "Compute the daily compounding interest on customer invoices",
    "author": "QG Apps",
    "website": "https://github.com/TheQuantumGroup/odoo-account",
    "category": "Uncategorized",
    "license": "Other proprietary",
    "version": "14.0.1.0.0",
    "depends": ["base", "account", "treasury"],
    "data": [
        "security/ir.model.access.csv",
        "views/invoices_interest.xml",
        "views/invoice_interest_rate.xml",
        "views/res_config_settings.xml",
        "views/menuitems.xml",
        "views/res_partner_view.xml",
        "data/parameters.xml",
        "data/cron.xml",
    ],
}