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
        sa_mass_APVO = self.env['ir.actions.server'].browse(633)
        ctx = dict(self.env.context or {})
        ctx.update({'active_ids': self.purchase_order_ids.ids, 'active_model': 'purchase.order'})
        sa_mass_APVO.with_context(ctx).run()
