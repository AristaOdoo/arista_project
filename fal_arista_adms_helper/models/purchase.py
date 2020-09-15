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


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity')
    def _compute_qty_invoiced(self):
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                if inv_line.move_id.state not in ['cancel']:
                    if inv_line.move_id.type == 'in_invoice':
                        qty += inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
                    elif inv_line.move_id.type == 'in_refund':
                        qty -= inv_line.product_uom_id._compute_quantity(inv_line.quantity, line.product_uom)
            line.qty_invoiced = 0.0
