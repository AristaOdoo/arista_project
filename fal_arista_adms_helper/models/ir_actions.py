# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import odoo
from odoo import api, fields, models, tools, SUPERUSER_ID, _
from odoo.exceptions import MissingError, UserError, ValidationError, AccessError
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval, test_python_expr
from odoo.tools import wrap_module
from odoo.http import request

import base64
from collections import defaultdict
import datetime
import logging
import time

from pytz import timezone

_logger = logging.getLogger(__name__)

# build dateutil helper, starting with the relevant *lazy* imports
import dateutil
import dateutil.parser
import dateutil.relativedelta
import dateutil.rrule
import dateutil.tz
mods = {'parser', 'relativedelta', 'rrule', 'tz'}
attribs = {atr for m in mods for atr in getattr(dateutil, m).__all__}
dateutil = wrap_module(dateutil, mods | attribs)


class IrActionsServer(models.Model):
    _inherit = 'ir.actions.server'

    @api.model
    def adms_method(self, operation, adms_id=False, fal_business_type=False):
        if adms_id and fal_business_type:
            # Action Info
            action_server = self.browse(operation)
            # Model Info
            model = action_server.model_id
            business_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch'])
            company_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'res.company' and x.ttype == 'many2one')
            # Business Type/Company Record
            business_type = self.env['fal.business.type'].sudo().search([('x_studio_adms_id', '=', fal_business_type)], limit=1)
            company = business_type.company_id
            # Real ID
            real_id = self.env[model.model].sudo().search([('x_studio_adms_id', '=ilike', adms_id), (business_type_field.name, '=', business_type.id)])
            if not real_id:
                real_id = self.env[model.model].sudo().search([('x_studio_adms_id', '=ilike', adms_id), (company_type_field.name, '=', company.id)])
            # If still not found
            if not real_id:
                return "Record not found. Model: %s, Business Type Field: %s, Company Field %s, Business Type: %s, Company: %s" % (model.model, business_type_field, company_type_field, business_type, company)
            # Generate Context
            context = {'lang': 'en_US', 'tz': False, 'uid': 2, 'allowed_company_ids': [15, 15, 1, 1, 14, 14, 16, 17, 18, 19, 19], 'active_id': real_id.id, 'active_ids': real_id.ids, 'active_model': model.model, 'mail_notify_force_send': False}
            try:
                action_server.sudo().with_context(context).run()
            except Exception:
                return "Failed to run method. Context: %s" % (str(context))
            # Because we can't return value from ir.action.server, we need to manually search it's result on the object.
            # PC Journal
            if operation in [591]:
                return {'pc_journal': real_id.x_studio_issue_journal.name}
            if operation in [593]:
                return {'pc_journal': real_id.x_studio_issue_journal.name}
            if operation in [587]:
                return {'issue_journal': real_id.x_studio_issue_entry and real_id.x_studio_issue_entry.name or '',
                        'transfer_journal': real_id.x_studio_transfer_journal and real_id.x_studio_transfer_journal.name or '',
                        'invoice_journal': real_id.invoice_ids[0] and real_id.invoice_ids[0].name or ''}
            if operation in [586]:
                return {'issue_journal': real_id.x_studio_issue_entry and real_id.x_studio_issue_entry.name or '',
                        'invoice_journal': real_id.invoice_ids[0] and real_id.invoice_ids[0].name or ''}
        return 'Share ID & Branch is required'
