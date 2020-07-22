# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

from collections import defaultdict

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}


class payment_register(models.Model):
    _name = 'account.payment.register.model'
    _description = 'Register Payment'

    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method Type', required=True,
                                        help="Manual: Get paid by cash, check or any other method outside of Odoo.\n"
                                        "Electronic: Get paid automatically through a payment acquirer by requesting a transaction on a card saved by the customer when buying or subscribing online (payment token).\n"
                                        "Check: Pay bill by check and print it from Odoo.\n"
                                        "Batch Deposit: Encase several customer checks at once by generating a batch deposit to submit to your bank. When encoding the bank statement in Odoo, you are suggested to reconcile the transaction with the batch deposit.To enable batch deposit, module account_batch_payment must be installed.\n"
                                        "SEPA Credit Transfer: Pay bill from a SEPA Credit Transfer file you submit to your bank. To enable sepa credit transfer, module account_sepa must be installed ")
    invoice_ids = fields.Many2many('account.move', 'account_invoice_payment_rel_transient', 'payment_id', 'invoice_id', string="Invoices", copy=False, readonly=True)
    group_payment = fields.Boolean(help="Only one payment will be created by partner (bank)/ currency.")

    @api.model
    def default_get(self, fields):
        rec = super(payment_register, self).default_get(fields)
        active_ids = self._context.get('active_ids')
        if not active_ids:
            return rec
        invoices = self.env['account.move'].browse(active_ids)

        # Check all invoices are open
        if any(invoice.state != 'posted' or invoice.invoice_payment_state != 'not_paid' or not invoice.is_invoice() for invoice in invoices):
            raise UserError(_("You can only register payments for open invoices"))
        # Check all invoices are inbound or all invoices are outbound
        outbound_list = [invoice.is_outbound() for invoice in invoices]
        first_outbound = invoices[0].is_outbound()
        if any(x != first_outbound for x in outbound_list):
            raise UserError(_("You can only register at the same time for payment that are all inbound or all outbound"))
        if any(inv.company_id != invoices[0].company_id for inv in invoices):
            raise UserError(_("You can only register at the same time for payment that are all from the same company"))
        # Check the destination account is the same
        destination_account = invoices.line_ids.filtered(lambda line: line.account_internal_type in ('receivable', 'payable')).mapped('account_id')
        if len(destination_account) > 1:
            raise UserError(_('There is more than one receivable/payable account in the concerned invoices. You cannot group payments in that case.'))
        if 'invoice_ids' not in rec:
            rec['invoice_ids'] = [(6, 0, invoices.ids)]
        if 'journal_id' not in rec:
            rec['journal_id'] = self.env['account.journal'].search([('company_id', '=', self.env.company.id), ('type', 'in', ('bank', 'cash'))], limit=1).id
        if 'payment_method_id' not in rec:
            if invoices[0].is_inbound():
                domain = [('payment_type', '=', 'inbound')]
            else:
                domain = [('payment_type', '=', 'outbound')]
            rec['payment_method_id'] = self.env['account.payment.method'].search(domain, limit=1).id
        return rec

    @api.onchange('journal_id', 'invoice_ids')
    def _onchange_journal(self):
        active_ids = self._context.get('active_ids')
        invoices = self.env['account.move'].browse(active_ids)
        if self.journal_id and invoices:
            if invoices[0].is_inbound():
                domain_payment = [('payment_type', '=', 'inbound'), ('id', 'in', self.journal_id.inbound_payment_method_ids.ids)]
            else:
                domain_payment = [('payment_type', '=', 'outbound'), ('id', 'in', self.journal_id.outbound_payment_method_ids.ids)]
            domain_journal = [('type', 'in', ('bank', 'cash')), ('company_id', '=', invoices[0].company_id.id)]
            return {'domain': {'payment_method_id': domain_payment, 'journal_id': domain_journal}}
        return {}

    def _prepare_payment_vals(self, invoices):
        '''Create the payment values.

        :param invoices: The invoices/bills to pay. In case of multiple
            documents, they need to be grouped by partner, bank, journal and
            currency.
        :return: The payment values as a dictionary.
        '''
        amount = self.env['account.payment']._compute_payment_amount(invoices, invoices[0].currency_id, self.journal_id, self.payment_date)
        values = {
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'payment_date': self.payment_date,
            'communication': " ".join(i.invoice_payment_ref or i.ref or i.name for i in invoices),
            'invoice_ids': [(6, 0, invoices.ids)],
            'payment_type': ('inbound' if amount > 0 else 'outbound'),
            'amount': abs(amount),
            'currency_id': invoices[0].currency_id.id,
            'partner_id': invoices[0].commercial_partner_id.id,
            'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
            'partner_bank_account_id': invoices[0].invoice_partner_bank_id.id,
        }
        return values

    def get_payments_vals(self):
        '''Compute the values for payments.

        :return: a list of payment values (dictionary).
        '''
        grouped = defaultdict(lambda: self.env["account.move"])
        for inv in self.invoice_ids:
            if self.group_payment:
                grouped[(inv.commercial_partner_id, inv.currency_id, inv.invoice_partner_bank_id, MAP_INVOICE_TYPE_PARTNER_TYPE[inv.type])] += inv
            else:
                grouped[inv.id] += inv
        return [self._prepare_payment_vals(invoices) for invoices in grouped.values()]

    def create_payments(self):
        '''Create payments according to the invoices.
        Having invoices with different commercial_partner_id or different type
        (Vendor bills with customer invoices) leads to multiple payments.
        In case of all the invoices are related to the same
        commercial_partner_id and have the same type, only one payment will be
        created.

        :return: The ir.actions.act_window to show created payments.
        '''
        Payment = self.env['account.payment']
        payments = Payment.create(self.get_payments_vals())
        payments.post()

        action_vals = {
            'name': _('Payments'),
            'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        if len(payments) == 1:
            action_vals.update({'res_id': payments[0].id, 'view_mode': 'form'})
        else:
            action_vals['view_mode'] = 'tree,form'
        return action_vals
