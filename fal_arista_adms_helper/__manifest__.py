{
    "name": "Helper module for Arista",
    "version": "13.0.1.0.0",
    'license': 'OPL-1',
    'summary': 'Module to give adms_import method.',
    'category': 'Tools',
    'author': 'Falinwa Indonesia',
    'website': "https://www.falinwa.com",
    'support': 'sales@falinwa.com',
    "description": """
Module to give adms_import method.
=============================================

ADMS / Arista have special request to just call one method to know:
    1. If it's create/write
        How --> We search on the record if record with same share_id already available
    2. Translate share ID to real ID
        How --> On every share ID field in Odoo, the name should be:
                x_partner_id_adms_id, which can be char/integer
                then automatically get the 'partner_id' component
    3. As ADMS did not want to manage stock, here we need to 'virtually' manage stock
    """,
    "depends": [
        'base',
        'fal_business_type',
        'stock'
    ],
    'data': [
    ],
    'images': [
    ],
    'demo': [
    ],
    'currency': 'EUR',
    'application': False,
}
