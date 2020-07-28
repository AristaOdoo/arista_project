from odoo import fields, models, api


class AccountPayment(models.Model):
    _inherit = "account.payment"

    @api.onchange('amount', 'currency_id')
    def _onchange_amount(self):
        jrnl_filters = self._compute_journal_domain_and_types()
        journal_types = jrnl_filters['journal_types']
        domain_on_types = [('type', 'in', list(journal_types))]
        if self.invoice_ids:
            domain_on_types.append(('company_id', '=', self.invoice_ids[0].company_id.id))
            domain_on_types.append(('fal_business_type', '=', self.invoice_ids[0].fal_business_type.id))
        if self.journal_id.type not in journal_types or (self.invoice_ids and self.journal_id.company_id != self.invoice_ids[0].company_id):
            self.journal_id = self.env['account.journal'].search(domain_on_types, limit=1)
        return {'domain': {'journal_id': jrnl_filters['domain'] + domain_on_types}}

    fal_business_type = fields.Many2one('fal.business.type', related='journal_id.fal_business_type', string='Business Type', readonly=True)
    journal_id = fields.Many2one('account.journal', string='Journal', required=True, readonly=True, states={'draft': [('readonly', False)]}, tracking=True, domain="[('type', 'in', ('bank', 'cash')), ('company_id', '=', company_id), ('fal_business_type', '=', fal_business_type)]")
    writeoff_account_id = fields.Many2one('account.account', string="Difference Account", domain="[('deprecated', '=', False), ('company_id', '=', company_id), ('fal_business_type', '=', fal_business_type)]", copy=False)
