# -*- coding: utf-8 -*-
# Part of Odoo Falinwa Edition. See LICENSE file for full copyright and licensing details.
{
    "name": "Access Right to Reset to Draft",
    "version": "13.0.1.0.0",
    'author': "CLuedoo",
    'website': "https://www.cluedoo.com",
    "description": """
    Module to Extension the account reset
    """,
    "depends": [
        'account',
    ],
    'init_xml': [],
    'data': [
        'security/security.xml',
        'views/account_cancel_view.xml',
    ],
    'css': [],
    'js': [],
    'installable': True,
    'active': False,
    'application': False,
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
