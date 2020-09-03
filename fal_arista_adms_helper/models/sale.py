# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _prepare_invoice_line(self):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        """
        self.ensure_one()
        res = super(SaleOrderLine, self)._prepare_invoice_line()
        res['discount_fixed'] = self.x_studio_adms_discount
        return res

    def _check_line_unlink(self):
        """
        Check wether a line can be deleted or not.

        Lines cannot be deleted if the order is confirmed; downpayment
        lines who have not yet been invoiced bypass that exception.
        :rtype: recordset sale.order.line
        :returns: set of lines that cannot be deleted
        """
        # No need to check
        return False


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _prepare_invoice(self):
        self.ensure_one()
        res = super(SaleOrder, self)._prepare_invoice()
        res['invoice_date'] = self.x_studio_transdate_adms
        return res

    def _get_forbidden_state_confirm(self):
        return {'none'}
