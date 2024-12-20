{
    "name": "Account Payment Plan",
    "summary": "Tracks and auto-settle customer payment plans",
    "author": "QG Apps",
    "website": "https://github.com/TheQuantumGroup/odoo-account",
    "category": "Uncategorized",
    "license": "Other proprietary",
    "version": "14.0.1.0.0",
    "application": True,
    "external_dependencies": {"python": ["python-magic", "magic"]},
    "depends": ["base", "mail", "account", "marketing", "treasury_debt_recovery"],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/payment_plan_views.xml",
        "views/payment_plan_schedule_views.xml",
        "views/payment_plan_decline_history_views.xml",
        "wizards/decline_payment_plan.xml",
        "wizards/decline_draft_dsa.xml",
        "wizards/upload_draft_dsa.xml",
        "wizards/upload_finalized_dsa.xml",
        "wizards/add_review_comment_to_plan.xml",
        "wizards/customer_declined_draft_dsa.xml",
        "data/mail_templates.xml",
        "data/cron.xml",
        "data/config.xml",
        "data/payment_plan_sequence.xml",
    ],
}
