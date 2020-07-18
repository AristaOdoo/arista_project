from odoo import api, fields, models, _
import ast
from odoo.exceptions import UserError


class MassGenerateAPVOModel(models.Model):
    _name = "mass.generate.apvo.model"
    _description = 'Mass Generate APVO'

    def _get_business_type_default(self):
        user_id = self.env['res.users'].browse(self.env.uid)
        return user_id.fal_business_type_id or False

    taxes_id = fields.Many2one('account.tax', string="Taxes", domain=[('type_tax_use', '=', 'purchase')])
    purchase_order_ids = fields.Many2many('purchase.order', string="Purchases")
    partner_id = fields.Many2one("res.partner")
    date = fields.Date("Date")
    mass_apvo_sequence = fields.Char("Mass APVO sequence")
    apvo_type = fields.Selection([
        ('1', 'Receipt'),
        ('2', 'Retur'),
    ])
    text = fields.Text("Text")
    account_id = fields.Many2one("account.account", required=True)
    used = fields.Boolean("Has been Used")
    fal_business_type = fields.Many2one('fal.business.type', string="Business Type", default=_get_business_type_default)

    def call_mass_apvo(self):
        for purchase_order_id in self.purchase_order_ids:
            if purchase_order_id.partner_id.id != self.purchase_order_ids[0].partner_id.id:
                raise UserError(
                    _('Hanya bisa membuat APVO gabungan untuk vendor yang sama!'))
            if self.taxes_id:
                for purchase_line in purchase_order_id.order_line:
                    purchase_line.taxes_id = [(6, 0, [self.taxes_id.id])]
            else:
                for purchase_line in purchase_order_id.order_line:
                    purchase_line.taxes_id = [(6, 0, [])]
            if self.account_id:
                purchase_order_id.x_studio_variance_unit_account = self.account_id.id
        if self.apvo_type == '1':
            sa_mass_APVO = self.env['ir.actions.server'].browse(633)
            ctx = dict(self.env.context or {})
            ctx.update({'text': self.text, 'date': self.date, 'active_ids': self.purchase_order_ids.ids, 'active_model': 'purchase.order'})
            sa_mass_APVO.with_context(ctx).run()
        else:
            sa_mass_APVO_retur = self.env['ir.actions.server'].browse(639)
            ctx = dict(self.env.context or {})
            ctx.update({'text': self.text, 'date': self.date, 'active_ids': self.purchase_order_ids.ids, 'active_model': 'purchase.order'})
            sa_mass_APVO_retur.with_context(ctx).run()
        self.used = True

    @api.model
    def create(self, vals):
        business_type = self.fal_business_type
        if not business_type:
            user_id = self.env['res.users'].browse(self.env.uid)
            business_type = user_id.fal_business_type_id
        p_journal = self.env['account.journal'].sudo().search([('type', '=', 'purchase'), ('fal_business_type', '=', business_type.id), ('x_studio_arista_code', '=', 'AP-VO')])
        nomor = p_journal.sequence_id.with_context(ir_sequence_date=vals['date']).next_by_id(sequence_date=vals['date'])
        if nomor:
            vals['mass_apvo_sequence'] = nomor
        return super(MassGenerateAPVOModel, self).create(vals)
