{
    "name": "OMS",
    "summary": "Sales end-to-end module",
    "author": "QG Apps",
    "website": "https://github.com/TheQuantumGroup/odoo-oms",
    "license": "Other proprietary",
    "category": "Uncategorized",
    "version": "14.0.2.0.1",
    "depends": ["base", "mail", "sale", "account_hedge", "sale_bdc"],
    "application": True,
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/order.xml",
        "views/order_decline_history.xml",
        "views/hedge.xml",
        "views/order_load.xml",
        "views/order_pricing.xml",
        "views/sale_order.xml",
        "views/oms_menus.xml",
        "wizards/cancel_order.xml",
        "wizards/cancel_expired_order.xml",
        "wizards/decline_order.xml",
        "wizards/hedge_order.xml",
        "wizards/load_order.xml",
        "wizards/price_order.xml",
        "wizards/sale_order.xml",
        "wizards/reset_order_to_draft.xml",
        "views/res_partner.xml",
        "views/escalated_notification.xml",
        "data/config.xml",
        "data/cron.xml",
        "data/mail_templates.xml",
    ],
}
