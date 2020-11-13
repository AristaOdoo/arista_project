# -*- coding: utf-8 -*-
from odoo import fields, models, api
from lxml.builder import E


class RollBackADMS(models.Model):
    _name = 'x_rollback_adms'
    _description = "Models to rollback"

    model_id = fields.Many2one('ir.model', string='Models')
    record_ids = fields.Integer("Record Id")
    method_number = fields.Integer("Method Number")
