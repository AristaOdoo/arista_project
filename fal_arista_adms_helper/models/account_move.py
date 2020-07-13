# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError


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
