# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _


class Purchase(models.Model):
    _inherit = 'purchase.order'

    def _compute_po_value(self):
        for po in self:
            po_value = 0
            if po.amount_untaxed > 0:
                po_value = po.amount_untaxed
            elif po.x_studio_amount_dpp > 0:
                po_value = po.x_studio_amount_dpp
            else:
                po_value = 0
            po.fal_po_value = po_value

    fal_po_value = fields.Float("PO Value", compute='_compute_po_value')
