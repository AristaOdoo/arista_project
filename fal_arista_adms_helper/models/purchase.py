# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _


class Purchase(models.Model):
    _inherit = 'purchase.order'

    taxes_id = fields.Many2many('account.tax', string="Taxes")

    @api.onchange('x_studio_real_value')
    def _onchange_real_value(self):
        for po in self:
            po.x_studio_variance_unit = po.x_studio_real_value - po.amount_untaxed
