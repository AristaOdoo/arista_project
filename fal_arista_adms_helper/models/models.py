# -*- coding: utf-8 -*-
from odoo import models, api
from lxml.builder import E

import logging
_logger = logging.getLogger(__name__)

# Model exception
model_exception = ['account.tax']


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
                if 'customer_rank' in new_vals and new_vals['customer_rank'] > 0:
                    domain += [(company_type_field.name, '=', new_vals[company_type_field.name])]
                else:
                    domain += [(company_type_field.name, '=', new_vals[company_type_field.name])]
                    domain += [(business_type_field.name, '=', new_vals[business_type_field.name])]
            elif business_type_field and model.model not in model_exception:
                domain += [(business_type_field.name, '=', new_vals[business_type_field.name])]
            similar_adms_id = self.sudo().search(domain)
            if similar_adms_id:
                result = similar_adms_id.sudo().write(new_vals)
                return similar_adms_id
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
                model = self.env['ir.model'].sudo().search([('model', '=', field.relation)], limit=1)
                component_business_type_field = model.field_id.sudo().filtered(lambda x: x.relation == 'fal.business.type' and x.ttype == 'many2one' and x.name not in ['x_studio_unitowner', 'x_studio_frombranch', 'x_studio_tobranch'])
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
                        res = self.iterate_and_compute(model, o2m[2], business_type)
                        new_vals[key] += [(0, 0, res)]
                    elif o2m[0] == 6:
                        new_o2mid = []
                        # Here we want to map between the ADMS id given by API to Odoo ID
                        for o2mid in o2m[2]:
                            new_o2mid.append(self.env[model.model].sudo().search([('x_studio_adms_id', '=', o2mid), (component_business_type_field.name, '=', business_type.id)], limit=1).id)
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
                        # Let's find it on business type level first, if not found, search again on company level
                        real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id), (m2o_company.name, '=', business_type.company_id.id)], limit=1)
                        if not real_id:
                            real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_company.name, '=', business_type.company_id.id)], limit=1)
                    elif business_type and m2o_business_type and m2o_model.model not in model_exception:
                        real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key]), (m2o_business_type.name, '=', business_type.id)], limit=1)
                    # If the object doesn't have business type
                    else:
                        real_id = self.env[field.relation].sudo().search([('x_studio_adms_id', '=', vals[key])], limit=1)
                new_vals[key[17:]] = real_id.id
                new_vals[key] = vals[key]
            # Other field we just copy-paste
            else:
                new_vals[key] = vals[key]
        return new_vals
