# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import datetime
import logging
_logger = logging.getLogger(__name__)


MAP_INVOICE_TYPE_PAYMENT_SIGN = {
    'out_invoice': 1,
    'in_refund': 1,
    'out_receipt': 1,
    'in_invoice': -1,
    'out_refund': -1,
    'in_receipt': -1,
}

MAP_INVOICE_TYPE_PARTNER_TYPE = {
    'out_invoice': 'customer',
    'out_refund': 'customer',
    'out_receipt': 'customer',
    'in_invoice': 'supplier',
    'in_refund': 'supplier',
    'in_receipt': 'supplier',
}


class account_register_payments(models.TransientModel):
    _inherit = "account.payment.register"

    @api.model
    def default_get(self, fields):
        rec = {}
        active_ids = self._context.get('active_ids')
        active_model = self._context.get('active_model')
        if active_model == 'account.move' and len(active_ids) > 1:
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
            if 'fal_split_multi_payment' not in rec:
                rec['fal_split_multi_payment'] = True

            if 'payment_date' not in rec:
                rec['payment_date'] = datetime.date.today()

            if 'payment_wizard_line_ids' not in rec:
                rec['payment_wizard_line_ids'] = self._default_payment_wizard_line_ids()

            return rec
        else:
            return super(account_register_payments, self).default_get(fields)

    @api.onchange('journal_id')
    def _onchange_journal(self):
        res = super(account_register_payments, self)._onchange_journal()
        if self.journal_id:
            for wizard_line in self.payment_wizard_line_ids:
                wizard_line.journal_id = self.journal_id.id
                self.payment_method_id = wizard_line.payment_method_id and wizard_line.payment_method_id[0]
        return res

    @api.onchange('payment_date')
    def _onchange_payment_date(self):
        if self.payment_date:
            for wizard_line in self.payment_wizard_line_ids:
                wizard_line.payment_date = self.payment_date

    @api.onchange('payment_method_id')
    def _onchange_payment_method_id(self):
        if self.payment_method_id:
            for wizard_line in self.payment_wizard_line_ids:
                pay_type = self.payment_method_id.payment_type
                if wizard_line.payment_type == pay_type:
                    wizard_line.payment_method_id = self.payment_method_id.id

    @api.model
    def _default_payment_wizard_line_ids(self):
        if self.env.context.get('active_ids', False):
            active_ids = self.env.context.get('active_ids')
            temp = []
            for invoices in self.env['account.move'].browse(active_ids):
                currency = False
                journal = self.env['account.journal'].search(
                    [('type', '=', 'bank')], limit=1)

                if any(inv.currency_id != invoices[0].currency_id
                       for inv in invoices):
                    raise UserError(_(
                        "In order to pay multiple invoices at once, "
                        "they must use the same currency."))
                for invoice in invoices:
                    if invoice.state != 'posted' or invoice.invoice_payment_state != 'not_paid':
                        raise UserError(_(
                            "You can only register payments for open invoices"
                        ))
                    currency = invoice.currency_id.id

                payment_method = self.env['account.payment.method'].search(
                    [
                        (
                            'payment_type',
                            '=',
                            'inbound' if invoices.amount_residual > 0 else 'outbound')
                    ], limit=1)
                communication = False
                list_ref = invoices.filtered('invoice_payment_ref').mapped('invoice_payment_ref')
                if list_ref:
                    communication = ','.join(list_ref)
                inv_type = MAP_INVOICE_TYPE_PAYMENT_SIGN[invoice.type]
                total_amount = invoice.amount_residual * inv_type
                temp.append((0, 0, {
                    'partner_id': invoices.commercial_partner_id.id or invoices.partner_id.id,
                    'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
                    'amount': abs(invoices.amount_residual),
                    'currency_id': currency,
                    'payment_type': 'inbound' if total_amount > 0 else 'outbound',
                    'payment_date': fields.date.today(),
                    'invoice_ids': [(6, 0, invoices.ids)],
                    'fal_number': invoices and invoices[0].name,
                    'journal_id': journal and journal[0].id,
                    'payment_method_id': payment_method and payment_method[0].id,
                    'communication': communication,
                }))
        return temp

    def create_multi_payment(self):
        payment_ids = []
        for wizard_line in self.payment_wizard_line_ids:
            res = wizard_line.with_context({'active_id': wizard_line.id}).fal_create_payments()
            payment_ids.append(res['res_id'])

        if self.fal_create_batch_payment:
            batch = self.env['account.payment'].browse(payment_ids).create_batch_payment()
            batch_id = self.env['account.batch.payment'].browse(batch['res_id'])
            for bp in batch_id.payment_ids:
                for invoice in bp.invoice_ids:
                    invoice.write({'invoice_payment_ref': batch_id.name})
        return {'type': 'ir.actions.act_window_close'}

    def create_payments(self):
        # create entries only
        payment_moves = self._prepare_payment_moves()
        AccountMove = self.env['account.move'].with_context(default_type='entry')
        moves = AccountMove.create(payment_moves)
        moves.filtered(lambda move: move.journal_id.post_at != 'bank_rec').post()
        for payment in self:
            for rec in payment.payment_wizard_line_ids:
                for line in moves.line_ids.filtered(lambda a: a.name.split(":")[-1] == ' ' + rec.invoice_ids[0].name):
                    rec.invoice_ids[0].js_assign_outstanding_line(line.id)
        # if self.fal_split_multi_payment:
        #     self.create_multi_payment()
        # else:
        #     res = super(account_register_payments, self).create_payments()
        #     if self.fal_create_batch_payment:
        #         batch = self.env['account.payment'].search(res['domain']).create_batch_payment()
        #         batch_id = self.env['account.batch.payment'].browse(batch['res_id'])
        #         for bp in batch_id.payment_ids:
        #             for invoice in bp.invoice_ids:
        #                 invoice.write({'invoice_payment_ref': batch_id.name})


    payment_wizard_line_ids = fields.One2many(
        'fal.multi.payment.wizard',
        'register_payments_id', 'Payment List', default=_default_payment_wizard_line_ids)
    fal_split_multi_payment = fields.Boolean(
        string="Split payments for each invoice", default=True)
    fal_create_batch_payment = fields.Boolean(
        string="Create Batch Payment", default=False)

    def _prepare_payment_moves(self):
        all_move_vals = []
        for payment in self:
            line_ids = []
            total_amount = 0
            for pay in payment.payment_wizard_line_ids:
                partner_id = pay.partner_id.commercial_partner_id or pay.invoice_ids[0].partner_id
                counterpart_amount = -pay.amount
                liquidity_line_account = payment.journal_id.default_credit_account_id
                destination_account = pay.invoice_ids[0].mapped(
                    'line_ids.account_id').filtered(
                        lambda account: account.user_type_id.type in ('receivable', 'payable'))[0]

                if pay.payment_type == 'outbound':
                    counterpart_amount = pay.amount
                    liquidity_line_account = payment.journal_id.default_debit_account_id

                total_amount += counterpart_amount

                rec_pay_line_name = ''

                if pay.partner_type == 'customer':
                    if pay.payment_type == 'inbound':
                        rec_pay_line_name += _("Customer Payment")
                    elif pay.payment_type == 'outbound':
                        rec_pay_line_name += _("Customer Credit Note")
                elif pay.partner_type == 'supplier':
                    if pay.payment_type == 'inbound':
                        rec_pay_line_name += _("Vendor Credit Note")
                    elif pay.payment_type == 'outbound':
                        rec_pay_line_name += _("Vendor Payment")
                if pay.invoice_ids:
                    rec_pay_line_name += ': %s' % ', '.join(pay.invoice_ids.mapped('name'))

                vals = (0, 0, {'name': rec_pay_line_name,
                        'debit': counterpart_amount > 0.0 and counterpart_amount or 0.0,
                        'credit': counterpart_amount < 0.0 and -counterpart_amount or 0.0,
                        'date_maturity': payment.payment_date,
                        'partner_id': partner_id.id,
                        'account_id': destination_account.id,
                })
                line_ids.append(vals)

            value = (0, 0, {'name': 'Payment',
                    'debit': total_amount < 0.0 and -total_amount or 0.0,
                    'credit': total_amount > 0.0 and total_amount or 0.0,
                    'date_maturity': payment.payment_date,
                    'account_id': liquidity_line_account.id,
            })
            line_ids.append(value)

            move_vals = {
                'date': payment.payment_date,
                # 'ref': 'ref',
                'journal_id': payment.journal_id.id,
                'line_ids': line_ids,
            }
            return move_vals


class fal_multi_payment_wizard(models.TransientModel):
    _name = "fal.multi.payment.wizard"
    _description = "Multi Payment Wizard"

    register_payments_id = fields.Many2one(
        'account.payment.register', 'Payment List')
    partner_id = fields.Many2one('res.partner', string='Partner')
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor')])
    amount = fields.Monetary(string='Payment Amount', required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', required=True, default=lambda self: self.env.user.company_id.currency_id)
    payment_type = fields.Selection([('outbound', 'Send Money'), ('inbound', 'Receive Money')], string='Payment Type', required=True)
    payment_date = fields.Date(string='Payment Date', default=fields.Date.context_today, required=True, copy=False)
    invoice_ids = fields.Many2many('account.move', string='Invoices', copy=False)
    fal_number = fields.Char(string='Number')
    journal_id = fields.Many2one('account.journal', string='Payment Journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method Type', required=True, oldname="payment_method",
        help="Manual: Get paid by cash, check or any other method outside of Odoo.\n"\
        "Electronic: Get paid automatically through a payment acquirer by requesting a transaction on a card saved by the customer when buying or subscribing online (payment token).\n"\
        "Check: Pay bill by check and print it from Odoo.\n"\
        "Batch Deposit: Encase several customer checks at once by generating a batch deposit to submit to your bank. When encoding the bank statement in Odoo, you are suggested to reconcile the transaction with the batch deposit.To enable batch deposit, module account_batch_payment must be installed.\n"\
        "SEPA Credit Transfer: Pay bill from a SEPA Credit Transfer file you submit to your bank. To enable sepa credit transfer, module account_sepa must be installed ")
    communication = fields.Char(string='Memo')

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
        return [self._prepare_payment_vals(self.invoice_ids)]

    def fal_create_payments(self):
        Payment = self.env['account.payment']
        payments = Payment
        for payment_vals in self.get_payments_vals():
            payments += Payment.create(payment_vals)
        payments.post()

        action_vals = {
            'name': _('Payments'),
            'domain': [('id', 'in', payments.ids), ('state', '=', 'posted')],
            'view_type': 'form',
            'res_model': 'account.payment',
            'view_id': False,
            'type': 'ir.actions.act_window',
        }
        if len(payments) == 1:
            action_vals.update({'res_id': payments[0].id, 'view_mode': 'form'})
        else:
            action_vals['view_mode'] = 'tree,form'
        return action_vals
