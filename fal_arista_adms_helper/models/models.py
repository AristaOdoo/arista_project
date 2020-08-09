# -*- coding: utf-8 -*-
from odoo import models, api
from lxml.builder import E

import logging
_logger = logging.getLogger(__name__)

# Model exception
model_exception = []


class BaseModel(models.AbstractModel):
    _inherit = 'base'

    @api.model_create_multi
    @api.returns('self', lambda value: value.id)
    def adms_import(self, list_vals):
        model = self.env['ir.model'].sudo().search([('model', '=', self._name)], limit=1)

        for vals in list_vals:
            # 0. Business Type need to be defined here, no matter what, the header and child
            #    should always be on the same business type
            business_type = False
            business_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch'])
            company_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'res.company' and x.ttype == 'many2one')
            if business_type_field:
                business_type_adms_key = 'x_studio_adms_id_' + business_type_field.name
                for key in vals:
                    if key == business_type_adms_key:
                        business_type = self.env['fal.business.type'].sudo().search([('x_studio_adms_id', '=', vals[key])], limit=1)
            # 1. Translate any adms_id field into standard field
            new_vals = self.iterate_and_compute(model, vals, business_type)
            # 2. Determine wether it's create new or write
            #    But to determine if it's have similar ID, it's not only based by x_studio_adms_id
            #    as because on ADMS their database are separate for each company.
            #    So, unique are, combination of Business type + ADMS ID
            #    Extra Issue are, some object did not have Business type
            #    ----------------------------
            # If business type field is present, search by adms_id + business type
            # TO DO: later there is some exception object
            domain = [('x_studio_adms_id', '=', vals['x_studio_adms_id'])]
            # Special case for Partner. Because ADMS split it's partner to customer and vendor
            # Both table have different approach
            if model.model in ['res.partner']:
                # If customer, do not find the business type. Only the company
                # And do not find in partner that is vendor
                # Means that customer and vendor can have the same ADMS ID
                if 'customer_rank' in new_vals and new_vals['customer_rank'] > 0:
                    domain += [(company_type_field.name, '=', new_vals[company_type_field.name])]
                    domain += [('customer_rank', '>', 0)]
                else:
                    domain += [(company_type_field.name, '=', new_vals[company_type_field.name])]
                    domain += [(business_type_field.name, '=', new_vals[business_type_field.name])]
                    domain += [('supplier_rank', '>', 0)]
            # Special case for x_studio_reason_code, do not find company/business type
            # Means do nothing
            elif model.model in ['x_reason_adms']:
                pass
            elif business_type_field and model.model not in model_exception:
                domain += [(business_type_field.name, '=', new_vals[business_type_field.name])]
            similar_adms_id = self.sudo().search(domain)
            if similar_adms_id:
                # Before writing, make sure that this object method hasn't been called
                # Special case on 17/18. let it pass
                able_overwrite = False
                if 'x_studio_nomorpolisi' in vals or 'x_studio_nomorstnk' in vals or 'x_studio_tanggalterimaspk' in vals or 'x_studio_bstbdate' in vals or 'x_studio_passondate' in vals:
                    able_overwrite = True
                else:
                    able_overwrite = self.check_method(model, similar_adms_id)
                if able_overwrite:
                    # Special for spk payment multi, we need to unlink first all spk payment related
                    if model.model in ['x_spk_payment_multi']:
                        spk_payment_vals = []
                        for x_spk_payment in similar_adms_id.x_studio_spk_payment:
                            spk_payment_vals += [(2, x_spk_payment.id)]
                        similar_adms_id.sudo().write({'x_studio_spk_payment': spk_payment_vals})
                    result = similar_adms_id.sudo().write(new_vals)
                return similar_adms_id
            else:
                # If they try to create bon hijau without the bon merah
                # Return Error
                if model.model in ['x_spk_payment'] and 'x_studio_bankaccountcancelid' in new_vals:
                    return "Can't create Bon Hijau without Posting Bon Merah"
                else:
                    result = self.sudo().create(new_vals)
                    return result
        return "Something Went Wrong"

    def iterate_and_compute(self, model, vals, business_type):
        new_vals = {}
        # We want business type to be searched upfront, so whatever the sequence of input
        # There will be no error
        business_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch'])
        if business_type_field:
            business_type_adms_key = 'x_studio_adms_id_' + business_type_field.name
        # Also find the Company field as we want to fill it automatically when we found the business type
        company_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'res.company' and x.ttype == 'many2one')

        # For every field in vals
        for key in vals:
            # If it's list. It can means 2 possibilities
            # Either create new record, or link (usually many2many)
            if isinstance(vals[key], list):
                # Need to change the model to the list field model
                field = self.env['ir.model.fields'].sudo().search([('model_id', '=', model.id), ('name', '=', key)])
                new_model = self.env['ir.model'].sudo().search([('model', '=', field.relation)], limit=1)
                component_business_type_field = new_model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch'])
                # One2many component of API call set did not "have" ADMS ID
                # At first we do not know this, so for work around, we just don't need to
                # find out if component already have ADMS id, just always unlink all and
                # create a new one
                new_vals[key] = []
                new_vals[key] += [(5, 0, 0)]
                for o2m in vals[key]:
                    # If it's 0, Means we need to define if it's creating new object or just
                    # editing it by checking the adms id
                    # If it's 6, Means we only relate the id, and so just need to find out the
                    # real id
                    if o2m[0] == 0:
                        res = self.iterate_and_compute(new_model, o2m[2], business_type)
                        new_vals[key] += [(0, 0, res)]
                    elif o2m[0] == 6:
                        new_o2mid = []
                        # Here we want to map between the ADMS id given by API to Odoo ID
                        for o2mid in o2m[2]:
                            # If Tax, need to know if it's for sale/purchase
                            if new_model.model in ['account.tax']:
                                if model.model in ['x_po_tax', 'purchase.order.line']:
                                    new_o2mid.append(self.env[new_model.model].sudo().search([('x_studio_adms_id', '=', o2mid), (component_business_type_field.name, '=', business_type.id), ('type_tax_use', '=', 'purchase')], limit=1).id)
                                else:
                                    new_o2mid.append(self.env[new_model.model].sudo().search([('x_studio_adms_id', '=', o2mid), (component_business_type_field.name, '=', business_type.id), ('type_tax_use', '=', 'sale')], limit=1).id)
                            else:
                                new_o2mid.append(self.env[new_model.model].sudo().search([('x_studio_adms_id', '=', o2mid), (component_business_type_field.name, '=', business_type.id)], limit=1).id)
                        new_vals[key] = [(6, 0, new_o2mid)]
            # If it's a share id field for many2one relation
            # Find the object based on field search
            elif "x_studio_adms_id_" in key:
                # We try to get the real field name
                # It's always the 18th word
                field_name = key[17:]
                field = self.env['ir.model.fields'].sudo().search([('model_id', '=', model.id), ('name', '=', field_name)])
                # We want to find real_id of x_studio_adms_id field because they throw
                # adms id
                # Here, we do not only find based by adms id but also, if the object have
                # business type, need to be searched on business type

                # But, iF the key is business type, we do not want to search on business type.
                # Obviously, it doesn't have business type
                if business_type_field and key == business_type_adms_key:
                    real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key])], limit=1)
                    # If it's Business type, means we automatically find the company
                    new_vals[company_type_field.name] = real_id.company_id.id
                # Except that
                else:
                    # If business type is present
                    # also include on our search business type domain
                    m2o_model = self.env['ir.model'].sudo().search([('model', '=', field.relation)])
                    m2o_business_type = m2o_model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch'])
                    m2o_company = m2o_model.field_id.sudo().filtered(lambda x: x.relation == 'res.company' and x.ttype == 'many2one')
                    # Special case for res.users object.
                    # It will always have 2 many2one related to business type, because mirror
                    # behavior of company
                    if m2o_model.model == 'res.users':
                        m2o_business_type = m2o_model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name == 'fal_business_type')
                    # Special case for Partner. Because ADMS split it's partner to customer and vendor
                    # Both table have different approach
                    if m2o_model.model in ['res.partner']:
                        # Split between Customer / Vendor Transaction.
                        if model.model in ['purchase.order', 'purchase.order.line', 'x_spkbbn'] or key in ['x_studio_adms_id_x_studio_vendor_biro_jasa']:
                            # Let's find it on business type level first, if not found, search again on company level
                            # Except for x_studio_adms_id_x_studio_vendor_biro_jasa
                            # need to find on supplier
                            real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id), (m2o_company.name, '=', business_type.company_id.id), ('supplier_rank', '>', 0)], limit=1)
                            if not real_id:
                                real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_company.name, '=', business_type.company_id.id), ('supplier_rank', '>', 0)], limit=1)
                        else:
                            # Let's find it on business type level first, if not found, search again on company level
                            real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id), (m2o_company.name, '=', business_type.company_id.id), ('customer_rank', '>', 0)], limit=1)
                            if not real_id:
                                real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_company.name, '=', business_type.company_id.id), ('customer_rank', '>', 0)], limit=1)
                    elif m2o_model.model in ['x_reason_adms']:
                        real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key])], limit=1)
                    elif m2o_model.model in ['account.tax']:
                        if model.model in ['x_po_tax', 'purchase.order.line']:
                            real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id), ('type_tax_use', '=', 'purchase')], limit=1)
                        else:
                            real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id), ('x_studio_adms_id', '=', vals[key]), ('type_tax_use', '=', 'sale')], limit=1)
                    elif business_type and m2o_business_type and m2o_model.model not in model_exception:
                        real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id)], limit=1)
                        # Let's find it on business type level first, if not found, search again on company level
                        if not real_id:
                            real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_company.name, '=', business_type.company_id.id)], limit=1)
                    # If the object doesn't have business type
                    else:
                        real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key])], limit=1)
                new_vals[key[17:]] = real_id.id
                new_vals[key] = vals[key]
            # Other field we just copy-paste
            else:
                new_vals[key] = vals[key]
        return new_vals

    def check_method(self, model, record):
        if model.model == 'purchase.order':
            if record.x_studio_journal_apvo or record.x_studio_journal_apvo_retur:
                return False
            else:
                return True
        elif model.model == 'x_adms_po_header':
            if record.x_studio_issue_journal:
                return False
            else:
                return True
        elif model.model == 'sale.order':
            if record.x_studio_issue_entry or record.invoice_ids or record.x_studio_transfer_journal or record.x_studio_issue_journal_cancel or record.x_studio_invoice_journal_cancel:
                return False
            else:
                return True
        elif model.model == 'x_spk_payment_multi':
            if record.x_studio_bon_merah:
                return False
            else:
                return True
        elif model.model == 'x_spk_payment':
            if record.x_studio_bon_hijau:
                return False
            else:
                return True
        elif model.model == 'x_inventory_transfer':
            if record.x_studio_journal_keluar_1 or record.x_studio_journal_masuk_2 or record.x_studio_journal_masuk:
                return False
            else:
                return True
        elif model.model == 'x_importinvadj':
            if record.x_studio_journal_out or record.x_studio_journal_in:
                return False
            else:
                return True
        return True
