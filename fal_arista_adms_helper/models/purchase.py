# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _


class Purchase(models.Model):
    _inherit = 'purchase.order'

    @api.onchange('x_studio_real_value')
    def _onchange_real_value(self):
        for po in self:
            if po.amount_untaxed:
                po_value = po.amount_untaxed
            elif po.x_studio_amount_dpp:
                po_value = po.x_studio_amount_dpp
            else:
                po_value = 0
            po.x_studio_variance_unit = po.x_studio_real_value - po_value
