from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo.tools import partition, collections, lazy_property


class ResUsers(models.Model):
    _inherit = 'res.users'

    def _default_get_business_type_ids(self):
        default_main_business_type = self.env.ref("fal_business_type.main_business_type", raise_if_not_found=False)
        if default_main_business_type:
            return [(6, 0, default_main_business_type.ids)]
        else:
            return False

    def _default_get_business_type_id(self):
        default_main_business_type = self.env.ref("fal_business_type.main_business_type", raise_if_not_found=False)
        if default_main_business_type:
            return default_main_business_type
        else:
            return False

    fal_allowed_business_type_ids = fields.Many2many(
        'fal.business.type', 'fal_allowed_business_type_users_rel', 'user_id', 'business_type_id',
        string="Allowed Business Types", domain="[('company_id', 'in', company_ids)]",
        default=lambda self: self._default_get_business_type_ids(),
        )
    fal_business_type_ids = fields.Many2many(
        'fal.business.type', 'fal_business_type_users_rel', 'user_id', 'business_type_id',
        string="Business Types", domain="[('id', 'in', fal_allowed_business_type_ids)]",
        default=lambda self: self._default_get_business_type_ids(), help="Similar to Odoo Companies, you can view several business type by selecting this field. But it will not change the Allowed business type.")
    fal_business_type_id = fields.Many2one(
        'fal.business.type', string="Current Business Type", default=lambda self: self._default_get_business_type_id(), required=True)

    @api.onchange('fal_allowed_business_type_ids')
    def _onchange_fal_allowed_business_type_ids(self):
        if self.fal_allowed_business_type_ids:
            self.fal_business_type_ids = [(6, 0, self.fal_allowed_business_type_ids.ids)]
        if not self.fal_business_type_id and self.fal_allowed_business_type_ids:
            self.fal_business_type_id = self.fal_allowed_business_type_ids[0]

    @api.onchange('fal_business_type_ids')
    def _onchnage_business_type(self):
        pass

    @api.constrains('fal_allowed_business_type_ids', 'fal_business_type_id', 'fal_business_type_ids')
    def _check_business_type(self):
        if any(user.fal_business_type_id and user.fal_business_type_id not in user.fal_allowed_business_type_ids for user in self):
            raise ValidationError(_('The chosen business type is not in the allowed business type for this user'))
        if any(user.fal_business_type_ids and user.fal_business_type_id and user.fal_business_type_id not in user.fal_business_type_ids for user in self):
            raise ValidationError(_('The chosen business type is not in the allowed business type for this user'))
        for user in self:
            for business_type in user.fal_business_type_ids:
                if business_type not in user.fal_allowed_business_type_ids:
                    raise ValidationError(_('The chosen business types is not in the allowed company for this user'))

    @api.constrains('fal_business_type_ids', 'company_ids', 'company_id')
    def _check_business_type_in_company(self):
        for user in self:
            for business_type in user.fal_business_type_ids:
                if business_type.company_id not in user.company_ids:
                    raise ValidationError(_('The chosen business type is not in the allowed company for this user'))

    def sudo_write(self, vals):
        admin = self.env.ref('base.user_admin')
        self.with_user(admin).write(vals)

    def write(self, vals):
        result = super(ResUsers, self).write(vals)
        self.env['ir.model.access'].call_cache_clearing_methods()
        self.env['ir.rule'].clear_caches()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        users = super(ResUsers, self).create(vals_list)
        self.env['ir.model.access'].call_cache_clearing_methods()
        self.env['ir.rule'].clear_caches()
        return users
