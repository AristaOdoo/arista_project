from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    npwp = fields.Char(string='No. NPWP', size=25)
    pkp_status = fields.Selection([
        ('pkp', 'PKP'),
        ('nonpkp', 'Non PKP')],
        index=True, default='pkp', string='Status PKP')
    ppkp = fields.Char(string='No. PPKP')
