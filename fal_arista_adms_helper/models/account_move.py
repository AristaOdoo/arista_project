# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from num2words import num2words
from odoo.tools import float_is_zero, float_compare, safe_eval, date_utils, email_split, email_escape_char, email_re
from dateutil.relativedelta import relativedelta


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

    def _auto_create_asset(self):
        create_list = []
        invoice_list = []
        auto_validate = []
        for move in self:
            # On arista it can create asset not by vendor bills (For Asset Acquisition Issue)
            # if not move.is_invoice():
            #     continue
            for move_line in move.line_ids:
                # On Arista no need to check if value is 0
                if (
                    move_line.account_id
                    and (move_line.account_id.can_create_asset)
                    and move_line.account_id.create_asset != "no"
                    and not move.reversed_entry_id
                ):
                    if not move_line.name:
                        raise UserError(_('Journal Items of {account} should have a label in order to generate an asset').format(account=move_line.account_id.display_name))
                    vals = {
                        'name': move_line.name,
                        'company_id': move_line.company_id.id,
                        'x_studio_business_type': move_line.fal_business_type.id,
                        'currency_id': move_line.company_currency_id.id,
                        'original_move_line_ids': [(6, False, move_line.ids)],
                        'state': 'draft',
                    }
                    model_id = move_line.account_id.asset_model
                    if model_id:
                        vals.update({
                            'model_id': model_id.id,
                        })
                    auto_validate.append(move_line.account_id.create_asset == 'validate')
                    invoice_list.append(move)
                    create_list.append(vals)

        assets = self.env['account.asset'].create(create_list)
        for asset, vals, invoice, validate in zip(assets, create_list, invoice_list, auto_validate):
            if 'model_id' in vals:
                asset._onchange_model_id()
                asset._onchange_method_period()
                if validate:
                    asset.validate()
            if invoice:
                asset_name = {
                    'purchase': _('Asset'),
                    'sale': _('Deferred revenue'),
                    'expense': _('Deferred expense'),
                }[asset.asset_type]
                msg = _('%s created from invoice') % (asset_name)
                msg += ': <a href=# data-oe-model=account.move data-oe-id=%d>%s</a>' % (invoice.id, invoice.name)
                asset.message_post(body=msg)
        return assets

    def adms_js_assign_outstanding_line(self, line_id):
        self.ensure_one()
        lines = self.env['account.move.line'].browse(line_id)
        lines += self.line_ids.filtered(lambda line: line.account_id == lines[0].account_id and line.partner_id == lines[0].partner_id and not line.reconciled)
        return lines.reconcile()

    def num_to_words_id(self, value):
        return num2words(value, lang="id")

    def action_post(self):
        for move in self:
            if self.env.context.get('combine_account', False):
                # On arista we need to combine line which has relation to so / po
                # Has product, is invoice / vendor bills, same account, same debit/credit position
                product_to_updates = {}
                line_to_removes = []
                for move_line in move.line_ids:
                    if (move_line.account_id.x_studio_is_bank) or (move_line.product_id and move_line.product_id.x_studio_adms_id != '99'):
                        key = move.key_maker(move_line)
                        if key not in product_to_updates:
                            product_to_updates[key] = {
                                'move_line_id': move_line.id,
                                'debit': move_line.debit,
                                'credit': move_line.credit,
                            }
                        else:
                            product_to_updates[key]['debit'] = product_to_updates[key]['debit'] + move_line.debit
                            product_to_updates[key]['credit'] = product_to_updates[key]['credit'] + move_line.credit
                            line_to_removes.append(move_line.id)
                move_line_vals = []
                for product_to_update in product_to_updates:
                    move_line_vals.append((1, product_to_updates[product_to_update]['move_line_id'], {
                        'debit': product_to_updates[product_to_update]['debit'],
                        'credit': product_to_updates[product_to_update]['credit']
                        }))
                for line_to_remove in line_to_removes:
                    move_line_vals.append((2, line_to_remove))
                move.line_ids = move_line_vals
            elif self.env.context.get('mapvo_combine_account', False):
                # Special on mapvo, the accure account is combined based on dmsrefnum
                product_to_updates = {}
                line_to_removes = []
                for move_line in move.line_ids:
                    if (move_line.account_id.x_studio_is_bank) or (move_line.product_id and move_line.product_id.x_studio_adms_id != '99'):
                        key = move.key_maker_mapvo(move_line)
                        if key not in product_to_updates:
                            product_to_updates[key] = {
                                'move_line_id': move_line.id,
                                'debit': move_line.debit,
                                'credit': move_line.credit,
                            }
                        else:
                            product_to_updates[key]['debit'] = product_to_updates[key]['debit'] + move_line.debit
                            product_to_updates[key]['credit'] = product_to_updates[key]['credit'] + move_line.credit
                            line_to_removes.append(move_line.id)
                move_line_vals = []
                for product_to_update in product_to_updates:
                    move_line_vals.append((1, product_to_updates[product_to_update]['move_line_id'], {
                        'debit': product_to_updates[product_to_update]['debit'],
                        'credit': product_to_updates[product_to_update]['credit']
                        }))
                for line_to_remove in line_to_removes:
                    move_line_vals.append((2, line_to_remove))
                move.line_ids = move_line_vals
            # Delete 0 line
            for line in move.line_ids:
                if line.debit + line.credit == 0:
                    line.unlink()
        return super(AccountMove, self).action_post()

    def key_maker(self, line_id):
        return ("d" if line_id.debit else "c") + "|" + str(line_id.account_id.id)

    def key_maker_mapvo(self, line_id):
        return ("d" if line_id.debit else "c") + "|" + str(line_id.account_id.id) + "|" + str(line_id.x_studio_per_line_dmsrefnum)

    def get_line_ids(self, move_line_ids, dmsrefnum, line_checked):
        journal_payment_ids = []
        for line in move_line_ids:
            if line.id not in line_checked:
                line_checked.append(line.id)
                for matched_credit_id in line.matched_credit_ids:
                    if matched_credit_id.credit_move_id.partner_id == line.partner_id and matched_credit_id.credit_move_id.x_studio_dmsrefnumber == dmsrefnum:
                        journal_payment_ids.append(matched_credit_id.credit_move_id.id)
                        journal_payment_ids.extend(line.move_id.get_line_ids(matched_credit_id.credit_move_id.move_id.line_ids, dmsrefnum, line_checked))
                    if matched_credit_id.debit_move_id.partner_id == line.partner_id and matched_credit_id.debit_move_id.x_studio_dmsrefnumber == dmsrefnum:
                        journal_payment_ids.append(matched_credit_id.debit_move_id.id)
                        journal_payment_ids.extend(line.move_id.get_line_ids(matched_credit_id.debit_move_id.move_id.line_ids, dmsrefnum, line_checked))
                for matched_debit_id in line.matched_debit_ids:
                    if matched_debit_id.debit_move_id.partner_id == line.partner_id and matched_debit_id.debit_move_id.x_studio_dmsrefnumber == dmsrefnum:
                        journal_payment_ids.append(matched_debit_id.debit_move_id.id)
                        journal_payment_ids.extend(line.move_id.get_line_ids(matched_debit_id.debit_move_id.move_id.line_ids, dmsrefnum, line_checked))
                    if matched_debit_id.credit_move_id.partner_id == line.partner_id and matched_debit_id.credit_move_id.x_studio_dmsrefnumber == dmsrefnum:
                        journal_payment_ids.append(matched_debit_id.credit_move_id.id)
                        journal_payment_ids.extend(line.move_id.get_line_ids(matched_debit_id.credit_move_id.move_id.line_ids, dmsrefnum, line_checked))
        return journal_payment_ids

    def _get_reconciled_info_JSON_values(self):
        self.ensure_one()
        foreign_currency = self.currency_id if self.currency_id != self.company_id.currency_id else False

        reconciled_vals = []
        pay_term_line_ids = self.line_ids.filtered(lambda line: line.account_id.user_type_id.type in ('receivable', 'payable'))
        partials = pay_term_line_ids.mapped('matched_debit_ids') + pay_term_line_ids.mapped('matched_credit_ids')
        for partial in partials:
            counterpart_lines = partial.debit_move_id + partial.credit_move_id
            counterpart_line_list = counterpart_lines.filtered(lambda line: line not in self.line_ids)

            for counterpart_line in counterpart_line_list:
                if foreign_currency and partial.currency_id == foreign_currency:
                    amount = partial.amount_currency
                else:
                    amount = partial.company_currency_id._convert(partial.amount, self.currency_id, self.company_id, self.date)

                if float_is_zero(amount, precision_rounding=self.currency_id.rounding):
                    continue

                ref = counterpart_line.move_id.name
                if counterpart_line.move_id.ref:
                    ref += ' (' + counterpart_line.move_id.ref + ')'

                reconciled_vals.append({
                    'name': counterpart_line.name,
                    'journal_name': counterpart_line.journal_id.name,
                    'amount': amount,
                    'currency': self.currency_id.symbol,
                    'digits': [69, self.currency_id.decimal_places],
                    'position': self.currency_id.position,
                    'date': counterpart_line.date,
                    'payment_id': counterpart_line.id,
                    'account_payment_id': counterpart_line.payment_id.id,
                    'payment_method_name': counterpart_line.payment_id.payment_method_id.name if counterpart_line.journal_id.type == 'bank' else None,
                    'move_id': counterpart_line.move_id.id,
                    'ref': ref,
                })
        return reconciled_vals

    @api.model
    def _autopost_draft_entries(self):
        '''
            Change Odoo standard, as Odoo will try to auto post entries with asset that is archived
        '''
        now_in_wib = (fields.Datetime.now() + relativedelta(hours=7))
        date = int(now_in_wib.strftime('%d'))
        hour = int(now_in_wib.strftime('%H'))
        if date in [7, 8] and hour in [0, 1, 2, 3, 4, 5, 6, 7]:
            records = self.search([
                ('state', '=', 'draft'),
                ('date', '<=', fields.Date.today()),
                ('auto_post', '=', True),
                ('asset_id.active', '=', True)
            ], limit=500)
            records.post()

    @api.model
    def _autopost_draft_entries_no_limit(self):
        '''
            Change Odoo standard, as Odoo will try to auto post entries with asset that is archived
        '''
        records = self.search([
            ('state', '=', 'draft'),
            ('date', '<=', fields.Date.today()),
            ('auto_post', '=', True),
            ('asset_id.active', '=', True)
        ])
        records.post()


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    ref = fields.Char(copy=True)
