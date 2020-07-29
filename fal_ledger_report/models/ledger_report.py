# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, api, _, _lt, fields
from odoo.tools.misc import format_date
from datetime import timedelta


class ReportPartnerLedger(models.AbstractModel):
    _inherit = "account.partner.ledger"

    filter_dms = True
    filter_filter_dms = ''

    @api.model
    def _get_options_domain(self, options):
        domain = super(ReportPartnerLedger, self)._get_options_domain(options)
        if options.get('filter_dms'):
            domain += [
                ('x_studio_dmsrefnumber', 'ilike', options['filter_dms']),
            ]
        return domain

    def _get_columns_name(self, options):
        columns = super(
            ReportPartnerLedger, self)._get_columns_name(options)
        columns.insert(4,
            {'name': _('DMS Ref Number'),},
        )
        columns.insert(5,
            {'name': _('Nomor Bon'),},
        )
        return columns

    @api.model
    def _get_query_amls(self, options, expanded_partner=None, offset=None, limit=None):
        res = super(ReportPartnerLedger, self)._get_query_amls(options, expanded_partner, offset, limit)
        query = res[0][:100] + 'account_move_line.x_studio_dmsrefnumber, account_move_line.x_studio_nomor_bon,' + res[0][100:]
        return query, res[1]

    @api.model
    def _get_report_line_move_line(self, options, partner, aml, cumulated_init_balance, cumulated_balance):
        res = super(ReportPartnerLedger, self)._get_report_line_move_line(options, partner, aml, cumulated_init_balance, cumulated_balance)
        columns = res.get('columns')
        columns.insert(3,
            {'name': aml['x_studio_dmsrefnumber']},
        )
        columns.insert(4,
            {'name': aml['x_studio_nomor_bon']},
        )
        return res

    @api.model
    def _get_report_line_total(self, options, initial_balance, debit, credit, balance):
        res = super(ReportPartnerLedger, self)._get_report_line_total(options, initial_balance, debit, credit, balance)
        res.update({'colspan': 8})
        return res

    @api.model
    def _get_report_line_partner(self, options, partner, initial_balance, debit, credit, balance):
        res = super(ReportPartnerLedger, self)._get_report_line_partner(options, partner, initial_balance, debit, credit, balance)
        res.update({'colspan': 8})
        return res

    @api.model
    def _get_report_line_load_more(self, options, partner, offset, remaining, progress):
        res = super(ReportPartnerLedger, self)._get_report_line_load_more(options, partner, offset, remaining, progress)
        res.update({'colspan': 12 if self.user_has_groups('base.group_multi_currency') else 11})
        return res


class AccountGeneralLedgerReport(models.AbstractModel):
    _inherit = "account.general.ledger"

    filter_dms = True
    filter_filter_dms = ''

    @api.model
    def _get_options_domain(self, options):
        domain = super(AccountGeneralLedgerReport, self)._get_options_domain(options)
        if options.get('filter_dms'):
            domain += [
                ('x_studio_dmsrefnumber', 'ilike', options['filter_dms']),
            ]
        return domain

    @api.model
    def _get_query_amls(self, options, expanded_partner=None, offset=None, limit=None):
        print(options, 'hhhhhhhhhhhhh')
        res = super(AccountGeneralLedgerReport, self)._get_query_amls(options, expanded_partner, offset, limit)
        query = res[0][:100] + 'account_move_line.x_studio_dmsrefnumber, account_move_line.x_studio_nomor_bon,' + res[0][100:]
        return query, res[1]

    def _get_columns_name(self, options):
        columns = super(
            AccountGeneralLedgerReport, self)._get_columns_name(options)
        columns.insert(3,
            {'name': _('Account'),},
        )
        columns.insert(4,
            {'name': _('DMS Ref Number'),},
        )
        columns.insert(5,
            {'name': _('Nomor Bon'),},
        )
        return columns

    @api.model
    def _get_aml_line(self, options, account, aml, cumulated_balance):
        res = super(AccountGeneralLedgerReport, self)._get_aml_line(options, account, aml, cumulated_balance)
        columns = res.get('columns')
        columns.insert(2,
            {'name': aml['account_code']},
        )
        columns.insert(3,
            {'name': aml['x_studio_dmsrefnumber']},
        )
        columns.insert(4,
            {'name': aml['x_studio_nomor_bon']},
        )
        return res

    @api.model
    def _get_total_line(self, options, debit, credit, balance):
        res = super(AccountGeneralLedgerReport, self)._get_total_line(options, debit, credit, balance)
        res.update({'colspan': 8})
        return res

    @api.model
    def _get_account_title_line(self, options, account, amount_currency, debit, credit, balance, has_lines):
        res = super(AccountGeneralLedgerReport, self)._get_account_title_line(options, account, amount_currency, debit, credit, balance, has_lines)
        res.update({'colspan': 7})
        return res

    @api.model
    def _get_initial_balance_line(self, options, account, amount_currency, debit, credit, balance):
        res = super(AccountGeneralLedgerReport, self)._get_initial_balance_line(options, account, amount_currency, debit, credit, balance)
        res.update({'colspan': 7})
        return res

    @api.model
    def _get_load_more_line(self, options, account, offset, remaining, progress):
        res = super(AccountGeneralLedgerReport, self)._get_load_more_line(options, account, offset, remaining, progress)
        res.update({'colspan': 10})
        return res

    @api.model
    def _get_account_total_line(self, options, account, amount_currency, debit, credit, balance):
        res = super(AccountGeneralLedgerReport, self)._get_account_total_line(options, account, amount_currency, debit, credit, balance)
        res.update({'colspan': 7})
        return res
