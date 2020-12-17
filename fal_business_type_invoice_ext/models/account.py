# -*- coding: utf-8 -*-
from odoo.exceptions import UserError, ValidationError
from odoo import api, fields, models, _, tools


class AccountAccount(models.Model):
    _inherit = "account.account"

    @api.constrains('user_type_id')
    def _check_user_type_id_unique_current_year_earning(self):
        data_unaffected_earnings = self.env.ref('account.data_unaffected_earnings')
        result = self.read_group([('user_type_id', '=', data_unaffected_earnings.id)], ['fal_business_type', 'company_id'], ['fal_business_type'])
        for res in result:
            if res.get('fal_business_type_count', 0) >= 2:
                account_unaffected_earnings = self.search([('fal_business_type', '=', res['fal_business_type'][0]), ('user_type_id', '=', data_unaffected_earnings.id)])
                raise ValidationError(_('You cannot have more than one account with "Current Year Earnings" as type. (accounts: %s, %s)') % ([a.id for a in account_unaffected_earnings], [a.code for a in account_unaffected_earnings]))
