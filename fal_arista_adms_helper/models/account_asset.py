# -*- coding: utf-8 -*-
from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import UserError
from num2words import num2words


class AccountAsset(models.Model):
    _inherit = 'account.asset'

    accumulated_value = fields.Monetary(string="Accumulated Value", readonly=True, compute='_compute_accumulated_value', store=True, help="Sum of the posted depreciable value")

    @api.onchange('model_id')
    def _onchange_model_id(self):
        model = self.model_id
        if model:
            self.method = model.method
            self.method_number = model.method_number
            self.method_period = model.method_period
            self.method_progress_factor = model.method_progress_factor
            self.prorata = model.prorata
            self.prorata_date = fields.Date.today()
            self.account_analytic_id = model.account_analytic_id.id
            self.analytic_tag_ids = [(6, 0, model.analytic_tag_ids.ids)]
            self.account_asset_id = model.account_asset_id
            self.account_depreciation_id = model.account_depreciation_id
            self.account_depreciation_expense_id = model.account_depreciation_expense_id
            self.journal_id = model.journal_id

    # No need to block these
    @api.constrains('active', 'state')
    def _check_active(self):
        for record in self:
            if not record.active and record.state != 'close':
                continue

    @api.depends('value_residual', 'salvage_value', 'children_ids.book_value')
    def _compute_book_value(self):
        for record in self:
            # Change on Arista
            # They want book value not to count salvage
            record.book_value = record.value_residual + sum(record.children_ids.mapped('book_value'))
            record.gross_increase_value = sum(record.children_ids.mapped('original_value'))

    @api.depends('children_ids.book_value')
    def _compute_accumulated_value(self):
        for record in self:
            for children_id in record.children_ids:
                record.accumulated_value = sum(record.depreciation_move_ids.filtered(lambda x: x.state == 'posted').mapped('amount_total'))

    def manual_compute_accumulated_value(self):
        for record in self:
            record._compute_accumulated_value()
