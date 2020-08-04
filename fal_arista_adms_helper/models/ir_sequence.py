# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime, timedelta
import logging
import pytz

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class IrSequence(models.Model):
    """ Sequence model.

    The sequence model allows to define and use so-called sequence objects.
    Such objects are used to generate unique identifiers in a transaction-safe
    way.

    """
    _inherit = 'ir.sequence'

    def _next(self, sequence_date=None):
        # date mode
        dt = sequence_date or self._context.get('ir_sequence_date', fields.Date.today())
        """ Returns the next number in the preferred sequence in all the ones given in self."""
        if not self.use_date_range:
            return self.with_context(ir_sequence_date=dt)._next_do()
        seq_date = self.env['ir.sequence.date_range'].search([('sequence_id', '=', self.id), ('date_from', '<=', dt), ('date_to', '>=', dt)], limit=1)
        if not seq_date:
            seq_date = self._create_date_range_seq(dt)
        return seq_date.with_context(ir_sequence_date_range=seq_date.date_from)._next()
