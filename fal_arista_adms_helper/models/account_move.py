# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _domain_partner_id(self):
        domain = "['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
        if self.env.context.get('default_type', 'entry') in ['out_invoice', 'out_refund', 'out_receipt']:
            return "['|', ('company_id', '=', False), ('company_id', '=', company_id), ('customer_rank', '>', 0)]"
        elif self.env.context.get('default_type', 'entry') in ['in_invoice', 'in_refund', 'in_receipt']:
            return "['|', ('company_id', '=', False), ('company_id', '=', company_id), ('supplier_rank', '>', 0)]"
        else:
            return "['|', ('company_id', '=', False), ('company_id', '=', company_id)]"
        return domain

    partner_id = fields.Many2one('res.partner', domain=_domain_partner_id)
