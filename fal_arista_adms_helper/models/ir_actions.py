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
        result = {
            'isSuccess': '',
            'ErrorMsg': '',
            'id_record': 0,
            'id_pc_journal': 0,
            'pc_journal': '',
            'id_issue_journal': 0,
            'issue_journal': '',
            'id_transfer_journal': 0,
            'transfer_journal': '',
            'id_invoice_journal': 0,
            'invoice_journal': '',
            'id_nomor_voucher': 0,
            'nomor_voucher': '',
            'ar_customer': '',
            'id_bon_merah': 0,
            'bon_merah': '',
            'id_bon_hijau': 0,
            'bon_hijau': '',
            'id_mutasi_out': 0,
            'mutasi_out': '',
            'id_mutasi_in': 0,
            'mutasi_in': '',
            'id_mutasi_intercompany': 0,
            'mutasi_intercompany': '',
            'id_adjust_in': 0,
            'adjust_in': '',
            'id_adjust_out': 0,
            'adjust_out': '',
            'id_invoice_journal_cancel': 0,
            'invoice_journal_cancel': '',
            'id_issue_journal_cancel': 0,
            'issue_journal_cancel': '',
            'id_apvo': 0,
            'apvo': '',
            'id_apvo_retur': 0,
            'apvo_retur': '',
            'total_dp': 0.0,
            'total_pay': 0.0,
        }
        if adms_id and fal_business_type:
            # Action Info
            action_server = self.browse(operation)
            # Model Info
            model = action_server.model_id
            business_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch', 'x_studio_origin'])
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
                result['isSuccess'] = False
                result['ErrorMsg'] = "Record not found. Model: %s, Business Type Field: %s, Company Field %s, Business Type: %s, Company: %s" % (model.model, business_type_field, company_type_field, business_type, company)
                return result
            # Generate Context
            context = {'lang': 'en_US', 'tz': False, 'uid': 2, 'allowed_company_ids': [15, 15, 1, 1, 14, 14, 16, 17, 18, 19, 19], 'active_id': real_id.id, 'active_ids': real_id.ids, 'active_model': model.model, 'mail_notify_force_send': False}
            try:
                action_server.sudo().with_context(context).run()
            except Exception:
                result['isSuccess'] = False
                result['ErrorMsg'] = "Failed to run method. Context: %s" % (str(context))
                return result
            # Because we can't return value from ir.action.server, we need to manually search it's result on the object.
            # PC Journal
            if operation in [606]:
                result['id_record'] = real_id.id or 0
                result['id_pc_journal'] = real_id.x_studio_issue_journal.id or 0
                result['pc_journal'] = real_id.x_studio_issue_journal and real_id.x_studio_issue_journal.name or ''
                if real_id.x_studio_issue_journal:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [607]:
                result['id_record'] = real_id.id or 0
                result['id_pc_journal'] = real_id.x_studio_issue_journal.id or 0
                result['pc_journal'] = real_id.x_studio_issue_journal and real_id.x_studio_issue_journal.name or ''
                if real_id.x_studio_issue_journal:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [605]:
                result['id_record'] = real_id.id or 0
                result['id_issue_journal'] = real_id.x_studio_issue_entry and real_id.x_studio_issue_entry.id or 0
                result['issue_journal'] = real_id.x_studio_issue_entry and real_id.x_studio_issue_entry.name or ''
                result['id_transfer_journal'] = real_id.x_studio_transfer_journal and real_id.x_studio_transfer_journal.id or 0
                result['transfer_journal'] = real_id.x_studio_transfer_journal and real_id.x_studio_transfer_journal.name or ''
                result['id_invoice_journal'] = real_id.invoice_ids[0] and real_id.invoice_ids[0].id or 0
                result['invoice_journal'] = real_id.invoice_ids[0] and real_id.invoice_ids[0].name or ''
                if real_id.x_studio_issue_entry or real_id.x_studio_transfer_journal or real_id.invoice_ids[0]:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [592]:
                result['id_record'] = real_id.id or 0
                result['id_issue_journal'] = real_id.x_studio_issue_entry and real_id.x_studio_issue_entry.id or 0
                result['issue_journal'] = real_id.x_studio_issue_entry and real_id.x_studio_issue_entry.name or ''
                result['id_invoice_journal'] = real_id.invoice_ids[0] and real_id.invoice_ids[0].id or 0
                result['invoice_journal'] = real_id.invoice_ids[0] and real_id.invoice_ids[0].name or ''
                if real_id.x_studio_issue_entry or real_id.invoice_ids[0]:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [608]:
                result['id_record'] = real_id.id or 0
                result['id_bon_merah'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.id or ''
                result['bon_merah'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.x_studio_nomor_bon or ''
                result['id_nomor_voucher'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.id or ''
                result['nomor_voucher'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.name or ''
                result['ar_customer'] = real_id.x_studio_customer_account or ''
                if real_id.x_studio_bon_merah:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [609]:
                result['id_record'] = real_id.id or 0
                result['id_bon_hijau'] = real_id.x_studio_bon_hijau and real_id.x_studio_bon_hijau.id or 0
                result['bon_hijau'] = real_id.x_studio_bon_hijau and real_id.x_studio_bon_hijau.x_studio_nomor_bon or ''
                result['id_nomor_voucher'] = real_id.x_studio_bon_hijau and real_id.x_studio_bon_hijau.id or 0
                result['nomor_voucher'] = real_id.x_studio_bon_hijau and real_id.x_studio_bon_hijau.name or ''
                result['ar_customer'] = real_id.x_studio_customer_account or ''
                if real_id.x_studio_bon_hijau:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [625]:
                result['id_record'] = real_id.id or 0
                result['id_bon_merah'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.id or 0
                result['bon_merah'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.x_studio_nomor_bon or ''
                result['id_nomor_voucher'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.id or 0
                result['nomor_voucher'] = real_id.x_studio_bon_merah and real_id.x_studio_bon_merah.name or ''
                result['ar_customer'] = real_id.x_studio_customer_account or ''
                if real_id.x_studio_bon_merah:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [594]:
                result['id_record'] = real_id.id or 0
                result['id_mutasi_out'] = real_id.x_studio_journal_keluar_1 and real_id.x_studio_journal_keluar_1.id or 0
                result['mutasi_out'] = real_id.x_studio_journal_keluar_1 and real_id.x_studio_journal_keluar_1.name or ''
                if real_id.x_studio_journal_keluar_1:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [596]:
                result['id_record'] = real_id.id or 0
                result['id_mutasi_in'] = real_id.x_studio_journal_masuk_2 and real_id.x_studio_journal_masuk_2.id or 0
                result['mutasi_in'] = real_id.x_studio_journal_masuk_2 and real_id.x_studio_journal_masuk_2.name or ''
                result['id_mutasi_intercompany'] = real_id.x_studio_journal_masuk and real_id.x_studio_journal_masuk.id or 0
                result['mutasi_intercompany'] = real_id.x_studio_journal_masuk and real_id.x_studio_journal_masuk.name or ''
                if real_id.x_studio_journal_masuk_2 or real_id.x_studio_journal_masuk:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [603]:
                result['id_record'] = real_id.id or 0
                result['id_adjust_in'] = real_id.x_studio_journal_in and real_id.x_studio_journal_in.id or 0
                result['adjust_in'] = real_id.x_studio_journal_in and real_id.x_studio_journal_in.name or ''
                result['id_adjust_out'] = real_id.x_studio_journal_out and real_id.x_studio_journal_out.id or 0
                result['adjust_out'] = real_id.x_studio_journal_out and real_id.x_studio_journal_out.name or ''
                if real_id.x_studio_journal_in or real_id.x_studio_journal_out:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [618]:
                result['id_record'] = real_id.id or 0
                result['id_invoice_journal_cancel'] = real_id.x_studio_invoice_journal_cancel and real_id.x_studio_invoice_journal_cancel.id or 0
                result['invoice_journal_cancel'] = real_id.x_studio_invoice_journal_cancel and real_id.x_studio_invoice_journal_cancel.name or ''
                result['id_issue_journal_cancel'] = real_id.x_studio_issue_journal_cancel and real_id.x_studio_issue_journal_cancel.id or 0
                result['issue_journal_cancel'] = real_id.x_studio_issue_journal_cancel and real_id.x_studio_issue_journal_cancel.name or ''
                if real_id.x_studio_invoice_journal_cancel or real_id.x_studio_issue_journal_cancel:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [628]:
                result['id_record'] = real_id.id or 0
                result['id_apvo'] = real_id.x_studio_journal_apvo and real_id.x_studio_journal_apvo.id or 0
                result['apvo'] = real_id.x_studio_journal_apvo and real_id.x_studio_journal_apvo.name or ''
                if real_id.x_studio_journal_apvo:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [631]:
                result['id_record'] = real_id.id or 0
                result['id_apvo_retur'] = real_id.x_studio_journal_apvo_retur and real_id.x_studio_journal_apvo_retur.id or 0
                result['apvo_retur'] = real_id.x_studio_journal_apvo_retur and real_id.x_studio_journal_apvo_retur.name or ''
                if real_id.x_studio_journal_apvo_retur:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [632]:
                result['id_record'] = real_id.id or 0
                result['id_invoice_journal_cancel'] = real_id.x_studio_invoice_journal_cancel and real_id.x_studio_invoice_journal_cancel.id or 0
                result['invoice_journal_cancel'] = real_id.x_studio_invoice_journal_cancel and real_id.x_studio_invoice_journal_cancel.name or ''
                result['id_issue_journal_cancel'] = real_id.x_studio_issue_journal_cancel and real_id.x_studio_issue_journal_cancel.id or 0
                result['issue_journal_cancel'] = real_id.x_studio_issue_journal_cancel and real_id.x_studio_issue_journal_cancel.name or ''
                if real_id.x_studio_invoice_journal_cancel or real_id.x_studio_issue_journal_cancel:
                    result['isSuccess'] = True
                else:
                    result['isSuccess'] = False
                    result['ErrorMsg'] = "Journal not created. Context: %s" % (str(context))
                return result
            if operation in [629]:
                result['isSuccess'] = True
                result['id_record'] = real_id.id or 0
                # For Recalculate payment, we do the logic here
                if real_id:
                    # For total DP we find spk payment that is related to this sale order
                    total_dp = 0.0
                    total_pay = 0.0
                    spk_pay_list = self.env['x_spk_payment'].sudo().search([('x_studio_nospk', '=', real_id.id)])
                    for spk_pay in spk_pay_list.filtered(lambda x: x.x_studio_bon_merah and (not x.x_studio_bon_hijau)):
                        if spk_pay.x_studio_paymtype in ['1', '2']:
                            total_dp += spk_pay.x_studio_amount
                        total_pay += spk_pay.x_studio_amount
                    result['total_dp'] = total_dp
                    result['total_pay'] = total_pay
                return result
        result['isSuccess'] = False
        result['ErrorMsg'] = 'Share ID & Branch is required'
        return result
