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
                user_id = self.env['res.users'].browse(self.env.uid)
                rec['journal_id'] = self.env['account.journal'].search([('fal_business_type', '=', user_id.fal_business_type_id.id), ('company_id', '=', self.env.company.id), ('type', 'in', ('bank', 'cash'))], limit=1).id
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

            user_id = self.env['res.users'].browse(self.env.uid)
            rec['fal_business_type'] = user_id.fal_business_type_id and user_id.fal_business_type_id.id or False
            return rec
        else:
            return super(account_register_payments, self).default_get(fields)

    @api.onchange('fal_business_type')
    def _onchange_fal_business_type(self):
        if self.fal_business_type:
            domain = {
                'journal_id': [('fal_business_type', '=', self.fal_business_type.id), ('type', 'in', ['bank', 'cash'])],
            }
            return {'domain': domain}

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
        # In Arista, they can add more lines on register payment
        # But if the line account is the same, we need to combine (Logically only 1)
        for extra_line in self.extra_lines:
            same_account_found = False
            for payment_move in payment_moves['line_ids']:
                if payment_move[2]['account_id'] == extra_line.account_id.id:
                    payment_move[2]['debit'] = payment_move[2]['debit'] + extra_line.debit
                    payment_move[2]['credit'] = payment_move[2]['credit'] + extra_line.credit
                    same_account_found = True
            if not same_account_found:
                payment_moves['line_ids'].append((0, 0, {
                    'name': extra_line.name,
                    'debit': extra_line.debit,
                    'credit': extra_line.credit,
                    'account_id': extra_line.account_id.id,
                }))
        moves = AccountMove.create(payment_moves)
        # In Arista there is a condition that Head Office pay for other branch purchases.
        # So, we need construct the data per branch
        value_line_ids_per_branch = {}
        main_entries_line_to_delete = []
        total_debit_other_branch = 0
        total_credit_other_branch = 0

        for move_line in moves.line_ids:
            if move_line.x_studio_branch_of_account.id != self.journal_id.fal_business_type.id:
                if move_line.x_studio_branch_of_account.id not in value_line_ids_per_branch:
                    value_line_ids_per_branch[move_line.x_studio_branch_of_account.id] = {
                        'debit': move_line.debit,
                        'credit': move_line.credit,
                        'line_ids': [(0, 0, {
                            'name': move_line.name,
                            'quantity': move_line.quantity,
                            'ref': move_line.ref,
                            'debit': move_line.debit,
                            'credit': move_line.credit,
                            'account_id': move_line.account_id.id,
                            'x_studio_per_line_dmsrefnum': move_line.x_studio_per_line_dmsrefnum,
                            'product_dimension_id': move_line.product_dimension_id and move_line.product_dimension_id.id or False,
                            'no_rangka_id': move_line.no_rangka_id and move_line.no_rangka_id.id or False,
                            'partner_id': move_line.partner_id and move_line.partner_id.id or False,
                        })],
                    }
                else:
                    value_line_ids_per_branch[move_line.x_studio_branch_of_account.id]['debit'] = value_line_ids_per_branch[move_line.x_studio_branch_of_account.id]['debit'] + move_line.debit
                    value_line_ids_per_branch[move_line.x_studio_branch_of_account.id]['credit'] = value_line_ids_per_branch[move_line.x_studio_branch_of_account.id]['credit'] + move_line.credit
                    value_line_ids_per_branch[move_line.x_studio_branch_of_account.id]['line_ids'].append((0, 0, {
                        'name': move_line.name,
                        'quantity': move_line.quantity,
                        'ref': move_line.ref,
                        'debit': move_line.debit,
                        'credit': move_line.credit,
                        'account_id': move_line.account_id.id,
                        'x_studio_per_line_dmsrefnum': move_line.x_studio_per_line_dmsrefnum,
                        'product_dimension_id': move_line.product_dimension_id and move_line.product_dimension_id.id or False,
                        'no_rangka_id': move_line.no_rangka_id and move_line.no_rangka_id.id or False,
                        'partner_id': move_line.partner_id and move_line.partner_id.id or False,
                    }))
                total_debit_other_branch += move_line.debit
                total_credit_other_branch += move_line.credit
                main_entries_line_to_delete.append(move_line.id)

        # Select intercompany journal to use
        unit = self.env['product.product'].search([('x_studio_adms_id', '=', '99')], limit=1).with_context(active_test=False)
        product_category = unit.categ_id
        Property_to_branch = self.env['ir.property'].with_context(force_company=self.journal_id.company_id.id, force_business_type=self.journal_id.fal_business_type.id)
        pc_out_in_pemusatan_to_branch = Property_to_branch.get_multi('property_stock_account_output_input_main_categ_id', product_category._name, [product_category.id])
        intercompany_account = pc_out_in_pemusatan_to_branch[product_category.id].id

        # Change initial journal to interbranch first
        ic_value = total_debit_other_branch - total_credit_other_branch
        main_journal_change = []
        main_journal_change.append((0, 0, {
            'name': "InterBranch Journal",
            'quantity': 1,
            'ref': 'InterBranch Journal',
            'debit': ic_value if ic_value > 0 else 0,
            'credit': ic_value if ic_value <= 0 else 0,
            'account_id': intercompany_account,
        }))
        for main_entries_line_to_delete_id in main_entries_line_to_delete:
            main_journal_change.append((2, main_entries_line_to_delete_id))
        # Apply new line to move
        moves.write({'line_ids': main_journal_change})
        # Reconcile
        moves.filtered(lambda move: move.journal_id.post_at != 'bank_rec').post()
        for payment in self:
            for rec in payment.payment_wizard_line_ids:
                for line in moves.line_ids.filtered(lambda a: a.name.split(":")[-1] == ' ' + rec.invoice_ids[0].name and a.account_internal_type in ['receivable', 'payable']):
                    rec.invoice_ids[0].js_assign_outstanding_line(line.id)

        ##############################################################
        # Create new journal for each branch
        for value_line_id_per_branch in value_line_ids_per_branch:
            # Select account and journal
            branch = self.env['fal.business.type'].browse(value_line_id_per_branch)
            company = branch.company_id
            Property_to_branch = self.env['ir.property'].with_context(force_company=company.id, force_business_type=branch.id)
            pc_out_in_pemusatan_to_branch = Property_to_branch.get_multi('property_stock_account_output_input_main_categ_id', product_category._name, [product_category.id])
            intercompany_account = pc_out_in_pemusatan_to_branch[product_category.id].id
            journal = branch.x_studio_intercompany_transaction

            # Define debit/credit position
            debit = value_line_ids_per_branch[value_line_id_per_branch]['debit']
            credit = value_line_ids_per_branch[value_line_id_per_branch]['credit']
            value_ic_branch = debit - credit
            line_ids = value_line_ids_per_branch[value_line_id_per_branch]['line_ids']

            branch_journal_account_line = []
            branch_journal_account_line.append((0, 0, {
                'name': "InterBranch Journal",
                'quantity': 1,
                'ref': 'InterBranch Journal',
                # We switch the position, if the real one is in debit, we need to fill on the credit
                'debit': value_ic_branch if value_ic_branch < 0 else 0,
                'credit': value_ic_branch if value_ic_branch >= 0 else 0,
                'account_id': intercompany_account,
            }))
            for line_id in line_ids:
                branch_journal_account_line.append(line_id)
            branch_am = self.env['account.move'].with_context(default_journal_id=journal.id).sudo().create({
                'journal_id': journal.id,
                'line_ids': branch_journal_account_line,
                'date': moves.date,
                'ref': 'InterBranch Payment',
                'type': 'entry',
            })
            # Post the Journal Entries
            branch_am.action_post()
            # Reconcile
            for payment in self:
                for rec in payment.payment_wizard_line_ids:
                    for line in branch_am.line_ids.filtered(lambda a: a.name.split(":")[-1] == ' ' + rec.invoice_ids[0].name and a.account_internal_type in ['receivable', 'payable']):
                        rec.invoice_ids[0].js_assign_outstanding_line(line.id)

    payment_wizard_line_ids = fields.One2many(
        'fal.multi.payment.wizard',
        'register_payments_id', 'Payment List', default=_default_payment_wizard_line_ids)
    fal_split_multi_payment = fields.Boolean(
        string="Split payments for each invoice", default=True)
    fal_create_batch_payment = fields.Boolean(
        string="Create Batch Payment", default=False)
    fal_business_type = fields.Many2one('fal.business.type', 'Business Type')
    extra_lines = fields.One2many("fal.multi.payment.wizard.extra.lines", 'register_payments_id', 'Extra Lines')

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


class fal_multi_payment_wizard_extra_lines(models.TransientModel):
    _name = "fal.multi.payment.wizard.extra.lines"
    _description = "Multi Payment Wizard Extra Lines"

    account_id = fields.Many2one('account.account')
    fal_business_type = fields.Many2one('fal.business.type', related="account_id.fal_business_type")
    register_payments_id = fields.Many2one(
        'account.payment.register', 'Payment List')
    name = fields.Char("Name")
    debit = fields.Float(string='Debit', default=0.0)
    credit = fields.Float(string='Credit', default=0.0)
