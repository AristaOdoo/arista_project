# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import datetime
import logging
_logger = logging.getLogger(__name__)

from collections import defaultdict

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


class payment_register(models.Model):
    _name = 'account.payment.register.model'
    _description = 'Register Payment'

    def _get_total_payment(self):
        for aprm in self:
            total_payment = 0
            debit = 0
            credit = 0
            # Count for each payment line
            for payment_wizard_line_id in aprm.payment_wizard_line_ids:
                total_payment += abs(payment_wizard_line_id.amount)
            for extra_line in aprm.extra_lines:
                debit += extra_line.debit
                credit += extra_line.credit
            # Count for each extra line
            if aprm.payment_type == 'out':
                total_payment += debit - credit
            else:
                total_payment += credit - debit

            aprm.total_payment = total_payment

    def _get_partner_name(self):
        for aprm in self:
            name = ""
            for invoice in aprm.invoice_ids:
                name = invoice.invoice_partner_display_name
            aprm.partner_name = name

    @api.depends('journal_id')
    def _get_forbidden_account(self):
        for aprm in self:
            if aprm.journal_id and aprm.journal_id.default_debit_account_id:
                aprm.forbidden_account = aprm.journal_id.default_debit_account_id.id
            else:
                aprm.forbidden_account = 0

    @api.onchange('invoice_ids')
    def _default_payment_wizard_line_ids(self):
        temp = [(5, 0, 0)]
        if self.invoice_ids:
            active_ids = self.invoice_ids
            for invoices in active_ids:
                currency = False
                journal = self.journal_id or self.env['account.journal'].search(
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
                # Don't know why but the amount residual is wrong if not from the
                # real object
                invoice_obj = self.env['account.move'].search([
                    ('name', '=', invoices.name),
                    ('company_id', '=', invoices.company_id.id),
                    ('fal_business_type', '=', invoices.fal_business_type.id)
                ], limit=1)
                amount_residual_signed = 0
                if invoice_obj:
                    amount_residual_signed = invoice_obj.amount_residual
                temp.append((0, 0, {
                    'partner_id': invoices.commercial_partner_id.id or invoices.partner_id.id,
                    'partner_type': MAP_INVOICE_TYPE_PARTNER_TYPE[invoices[0].type],
                    'amount': amount_residual_signed or abs(invoices.amount_residual_signed),
                    'currency_id': currency,
                    'payment_type': 'inbound' if total_amount > 0 else 'outbound',
                    'payment_date': fields.date.today(),
                    'invoice_ids': [(6, 0, invoices.ids)],
                    'fal_number': invoices and invoices[0].name,
                    'journal_id': journal and journal[0].id,
                    'payment_method_id': payment_method and payment_method[0].id,
                    'communication': communication,
                }))
        self.payment_wizard_line_ids = temp

    @api.onchange('payment_type')
    def _onchange_payment_type(self):
        if self.payment_type:
            if self.payment_type == 'in':
                domain = [('payment_type', '=', 'inbound'), ('code', '=', 'manual')]
            else:
                domain = [('payment_type', '=', 'outbound'), ('code', '=', 'manual')]
            self.payment_method_id = self.env['account.payment.method'].search(domain, limit=1).id

    @api.model
    def default_get(self, fields):
        rec = {}
        if 'payment_date' not in rec:
            rec['payment_date'] = datetime.date.today()
        if 'fal_split_multi_payment' not in rec:
            rec['fal_split_multi_payment'] = True
        if 'fal_create_batch_payment' not in rec:
            rec['fal_create_batch_payment'] = False
        if 'payment_type' not in rec:
            if self._context.get('default_payment_type'):
                rec['payment_type'] = self._context.get('default_payment_type')
            else:
                rec['payment_type'] = 'in'
        if 'account_move_type' not in rec:
            if self._context.get('default_account_move_type'):
                rec['account_move_type'] = self._context.get('default_account_move_type')
            else:
                rec['account_move_type'] = 'out_invoice'
        if 'journal_id' not in rec:
            user_id = self.env['res.users'].browse(self.env.uid)
            if rec['account_move_type'] in ['out_invoice', 'in_refund']:
                rec['journal_id'] = self.env['account.journal'].search([('fal_business_type', '=', user_id.fal_business_type_id.id), ('company_id', '=', self.env.company.id), ('type', 'in', ('bank', 'cash')), ('x_studio_type_bon', '=', 'm')], limit=1).id
            else:
                rec['journal_id'] = self.env['account.journal'].search([('fal_business_type', '=', user_id.fal_business_type_id.id), ('company_id', '=', self.env.company.id), ('type', 'in', ('bank', 'cash')), ('x_studio_type_bon', '=', 'h')], limit=1).id
        if 'state' not in rec:
            rec['state'] = 'draft'

        user_id = self.env['res.users'].browse(self.env.uid)
        rec['fal_business_type'] = user_id.fal_business_type_id and user_id.fal_business_type_id.id or False
        return rec

    name = fields.Char("Name", required=True)
    payment_date = fields.Date(required=True, default=fields.Date.context_today)
    journal_id = fields.Many2one('account.journal', required=True, domain=[('type', 'in', ('bank', 'cash'))])
    payment_type = fields.Selection([('in', 'Money In'), ('out', 'Money Out')], required=True, default="in")
    payment_method_id = fields.Many2one('account.payment.method', string='Payment Method Type', required=True)
    invoice_ids = fields.Many2many('account.move', 'account_invoice_payment_rel_model', 'payment_id', 'invoice_id', string="Invoices", copy=False)
    group_payment = fields.Boolean(help="Only one payment will be created by partner (bank)/ currency.")
    payment_wizard_line_ids = fields.One2many('fal.multi.payment.wizard.model', 'register_payments_id', 'Payment List', default=_default_payment_wizard_line_ids)
    fal_split_multi_payment = fields.Boolean(
        string="Split payments for each invoice", default=True)
    fal_create_batch_payment = fields.Boolean(
        string="Create Batch Payment", default=False)
    fal_business_type = fields.Many2one('fal.business.type', 'Business Type')
    company_id = fields.Many2one('res.company', 'Company', related="fal_business_type.company_id")
    extra_lines = fields.One2many("fal.multi.payment.wizard.extra.lines.model", 'register_payments_id', 'Extra Lines')
    state = fields.Selection([('draft', 'Draft'), ('post', 'Posted')], default="draft")
    total_payment = fields.Float('Total Payment', compute="_get_total_payment", store=True)
    forbidden_account = fields.Integer('Forbidden Account', compute="_get_forbidden_account")
    bon_id = fields.Many2one('account.move', 'Bon')
    nomor_bon = fields.Char('Nomor Bon', related="bon_id.x_studio_nomor_bon", store=True)
    partner_name = fields.Char("Partner Name", compute="_get_partner_name")
    account_move_type = fields.Selection([
        ('out_invoice', 'Customer Invoice'),
        ('out_refund', 'Customer Credit Note'),
        ('in_invoice', 'Vendor Bills'),
        ('in_refund', 'Vendor Refund')])
    account_move_ids = fields.Many2many('account.move', string="Journals", copy=False, readonly=True)

    @api.onchange('fal_business_type')
    def _onchange_fal_business_type(self):
        if self.fal_business_type:
            if self.account_move_type in ['out_invoice', 'in_refund']:
                domain = {
                    'journal_id': [('fal_business_type', '=', self.fal_business_type.id), ('type', 'in', ['bank', 'cash']), ('x_studio_type_bon', '=', 'm')],
                }
            else:
                domain = {
                    'journal_id': [('fal_business_type', '=', self.fal_business_type.id), ('type', 'in', ['bank', 'cash']), ('x_studio_type_bon', '=', 'h')],
                }
            return {'domain': domain}

    @api.onchange('journal_id', 'invoice_ids')
    def _onchange_journal(self):
        active_ids = self._context.get('active_ids')
        invoices = self.env['account.move'].browse(active_ids)
        if self.journal_id and invoices:
            if invoices[0].is_inbound():
                domain_payment = [('payment_type', '=', 'inbound'), ('id', 'in', self.journal_id.inbound_payment_method_ids.ids)]
            else:
                domain_payment = [('payment_type', '=', 'outbound'), ('id', 'in', self.journal_id.outbound_payment_method_ids.ids)]
            domain_journal = [('type', 'in', ('bank', 'cash')), ('fal_business_type', '=', self.fal_business_type.id)]
            if self.account_move_type in ['out_invoice', 'in_refund']:
                domain_journal = [('type', 'in', ('bank', 'cash')), ('fal_business_type', '=', self.fal_business_type.id), ('x_studio_type_bon', '=', 'm')]
            else:
                domain_journal = [('type', 'in', ('bank', 'cash')), ('fal_business_type', '=', self.fal_business_type.id), ('x_studio_type_bon', '=', 'h')]
            for wizard_line in self.payment_wizard_line_ids:
                wizard_line.journal_id = self.journal_id.id
                self.payment_method_id = wizard_line.payment_method_id and wizard_line.payment_method_id[0]
            return {'domain': {'payment_method_id': domain_payment, 'journal_id': domain_journal}}
        return {}

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

    def register_payment(self):
        # Check all invoices are open
        if any(invoice.state != 'posted' or invoice.invoice_payment_state != 'not_paid' or not invoice.is_invoice() for invoice in self.invoice_ids):
            raise UserError(_("You can only register payments for open invoices"))
        # Check all invoices are inbound or all invoices are outbound
        outbound_list = [invoice.is_outbound() for invoice in self.invoice_ids]
        first_outbound = self.invoice_ids[0].is_outbound()
        if any(x != first_outbound for x in outbound_list):
            raise UserError(_("You can only register at the same time for payment that are all inbound or all outbound"))
        if any(inv.company_id != self.invoice_ids[0].company_id for inv in self.invoice_ids):
            raise UserError(_("You can only register at the same time for payment that are all from the same company"))
        if any(extra_line.account_id.id == self.forbidden_account for extra_line in self.extra_lines):
            raise UserError(_("You cannot use journal bank account on extra lines"))
        # Value creation
        payment_wizard_line_vals = []
        for payment_wizard_line in self.payment_wizard_line_ids:
            payment_wizard_line_vals.append((0, 0, {
                'partner_id': payment_wizard_line.partner_id.id,
                'partner_type': payment_wizard_line.partner_type,
                'amount': payment_wizard_line.amount,
                'currency_id': payment_wizard_line.currency_id.id,
                'payment_type': payment_wizard_line.payment_type,
                'payment_date': payment_wizard_line.payment_date,
                'invoice_ids': [(6, 0, payment_wizard_line.invoice_ids.ids)],
                'fal_number': payment_wizard_line.fal_number,
                'journal_id': payment_wizard_line.journal_id.id,
                'payment_method_id': payment_wizard_line.payment_method_id.id,
                'communication': payment_wizard_line.communication,
            }))
        extra_lines_vals = []
        for extra_line in self.extra_lines:
            extra_lines_vals.append((0, 0, {
                'account_id': extra_line.account_id.id,
                'partner_id': extra_line.partner_id.id,
                'name': extra_line.name,
                'debit': extra_line.debit,
                'credit': extra_line.credit,
                'x_product_dimension_id': extra_line.x_product_dimension_id and extra_line.x_product_dimension_id.id or False,
                'x_studio_department_id': extra_line.x_studio_department_id and extra_line.x_studio_department_id.id or False,

            }))
        apr_vals = {
            'payment_date': self.payment_date,
            'journal_id': self.journal_id.id,
            'payment_method_id': self.payment_method_id.id,
            'invoice_ids': self.invoice_ids,
            'group_payment': self.group_payment,
            'payment_wizard_line_ids': payment_wizard_line_vals,
            'fal_split_multi_payment': self.fal_split_multi_payment,
            'fal_business_type': self.fal_business_type.id,
            'extra_lines': extra_lines_vals,
            'name': self.name,
        }
        self.env['account.payment.register'].create(apr_vals).with_context(aprm_id=self.id).create_payments()
        self.state = 'post'


class fal_multi_payment_wizard(models.Model):
    _name = "fal.multi.payment.wizard.model"
    _description = "Multi Payment Wizard"

    register_payments_id = fields.Many2one(
        'account.payment.register.model', 'Payment List')
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


class fal_multi_payment_wizard_extra_lines(models.Model):
    _name = "fal.multi.payment.wizard.extra.lines.model"
    _description = "Multi Payment Wizard Extra Lines"

    account_id = fields.Many2one('account.account', required=True)
    company_id = fields.Many2one('res.company', 'Company', related="register_payments_id.company_id")
    fal_business_type = fields.Many2one('fal.business.type', related="account_id.fal_business_type")
    register_payments_id = fields.Many2one(
        'account.payment.register.model', 'Payment List')
    partner_id = fields.Many2one('res.partner')
    name = fields.Char("Name")
    debit = fields.Float(string='Debit', default=0.0)
    credit = fields.Float(string='Credit', default=0.0)
    x_product_dimension_id = fields.Many2one('x_product_dimension', 'Product Dimension')
    x_studio_department_id = fields.Many2one('x_studio_department', 'Department')

    _sql_constraints = [
        (
            'check_credit_debit',
            'CHECK(credit + debit>=0 AND credit * debit=0)',
            'Wrong credit or debit value in accounting entry !'
        ),
    ]
