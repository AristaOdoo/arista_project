# -*- coding: utf-8 -*-
{
    'name': "Multi Payment Wizard.",
    'version': '13.0.1.0.0',
    'license': 'OPL-1',
    'summary': "Multiple register payment.",
    'sequence': 20,
    'category': 'Accounting',
    'author': "CLuedoo",
    'website': "https://www.cluedoo.com",
    'support': 'cluedoo@falinwa.com',
    'description': """
        Multiple register payment
        ==================================

        Enable user to have multiple register payment
    """,
    'depends': [
        'account_batch_payment',
    ],
    'data': [
        'wizard/fal_multi_payment_wizard_view.xml',
        'views/account_invoice.xml',
    ],
    'images': [
        'static/description/multi_payment_screenshot.png'
    ],
    'demo': [
    ],
    'price': 360.00,
    'currency': 'EUR',
    'application': False,
}
