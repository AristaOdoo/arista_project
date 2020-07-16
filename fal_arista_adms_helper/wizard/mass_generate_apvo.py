from odoo import api, fields, models, _
import ast
from odoo.exceptions import UserError


class MassGenerateAPVO(models.TransientModel):
    _name = "mass.generate.apvo"
    _description = 'Mass Generate APVO'

    purchase_order_ids = fields.Many2many('purchase.order', string="Purchases")

    def call_mass_apvo(self):
        for purchase_order_id in self.purchase_order_ids:
            if purchase_order_id.partner_id.id != self.purchase_order_ids[0].partner_id.id:
                raise UserError(
                    _('Hanya bisa membuat APVO gabungan untuk vendor yang sama!'))
            if purchase_order_id.taxes_id:
                for purchase_line in purchase_order_id.order_line:
                    purchase_line.taxes_id = [(6, 0, purchase_order_id.taxes_id.ids)]
        sa_mass_APVO = self.env['ir.actions.server'].browse(633)
        ctx = dict(self.env.context or {})
        ctx.update({'active_ids': self.purchase_order_ids.ids, 'active_model': 'purchase.order'})
        sa_mass_APVO.with_context(ctx).run()


class MassGenerateAPVORetur(models.TransientModel):
    _name = "mass.generate.apvo.retur"
    _description = 'Mass Generate APVO Retur'

    purchase_order_ids = fields.Many2many('purchase.order', string="Purchases")

    def call_mass_apvo(self):
        for purchase_order_id in self.purchase_order_ids:
            if purchase_order_id.partner_id.id != self.purchase_order_ids[0].partner_id.id:
                raise UserError(
                    _('Hanya bisa membuat APVO Retur gabungan untuk vendor yang sama!'))
            if purchase_order_id.taxes_id:
                for purchase_line in purchase_order_id.order_line:
                    purchase_line.taxes_id = [(6, 0, purchase_order_id.taxes_id.ids)]
        sa_mass_APVO_retur = self.env['ir.actions.server'].browse(639)
        ctx = dict(self.env.context or {})
        ctx.update({'active_ids': self.purchase_order_ids.ids, 'active_model': 'purchase.order'})
        sa_mass_APVO_retur.with_context(ctx).run()
