# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    npwp = fields.Char(string='NPWP', size=25)
    ppkp = fields.Char(string='PPKP')
    nomor_faktur_pajak = fields.Char(string='Nomor Faktur Pajak', size=16, copy=False)
    faktur_pajak_id = fields.Many2one('faktur.pajak', string='Faktur Pajak', copy=False)

    def action_create_faktur(self):
        faktur_obj = self.env['faktur.pajak']
        today = fields.Date.context_today(self)
        for inv in self:
            faktur = inv.faktur_pajak_id
            vals = {
                'date_used': today,
                'invoice_id': inv.id,
                'partner_id': inv.partner_id.id,
                'dpp': inv.amount_untaxed or 0.0,
                'tax_amount': inv.amount_tax or 0.0,
                'currency_id': inv.currency_id.id,
                'company_id': inv.company_id.id,
            }
            if inv.type == 'out_invoice' and inv.faktur_pajak_id:
                vals.update({
                    'pajak_type': 'out',
                })
                faktur.sudo().used()
                faktur.write(vals)
            if inv.type == 'in_invoice' and inv.nomor_faktur_pajak:
                kode_transkasi = inv.nomor_faktur_pajak[:2]
                categ = inv.nomor_faktur_pajak[2:3]
                kode_cabang = inv.nomor_faktur_pajak[3:6]
                tahun = inv.nomor_faktur_pajak[6:8]
                nomor_fp = inv.nomor_faktur_pajak[-8:]
                vals.update({
                    'pajak_type': 'in',
                    'kode_transaksi': kode_transkasi,
                    'category': categ,
                    'nomor_urut': kode_cabang,
                    'tahun_penerbit': tahun,
                    'nomor_urut': nomor_fp,
                })
                if len(inv.nomor_faktur_pajak) != 16:
                    raise ValidationError(_('Nomor faktur pajak tidak sesuai range referensi (16 digits)'))
                if kode_transkasi not in ['01', '02', '03', '04', '05', '06', '07', '08', '09']:
                    raise ValidationError(_('Kode transkasi pada nomor faktur pajak tidak sesuai'))
                if categ not in ['0', '1']:
                    raise ValidationError(_('Kode status pada nomor faktur pajak tidak sesuai'))
                if faktur:
                    faktur.write(vals)
                else:
                    faktur = faktur_obj.create(vals)
                    inv.write({'faktur_pajak_id': faktur.id})
                    faktur.sudo().used()

    def action_post(self):
        for inv in self:
            inv.action_create_faktur()
        return super(AccountMove, self).action_post()

    def button_cancel(self):
        for inv in self:
            inv.faktur_pajak_id.cancel()
        return super(AccountMove, self).button_cancel()

    def button_draft(self):
        for inv in self:
            inv.faktur_pajak_id.set_to_draft()
        return super(AccountMove, self).button_draft()

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        res = super(AccountMove, self)._onchange_partner_id()
        if self.partner_id:
            self.npwp = self.partner_id.npwp
            if self.partner_id.pkp_status == 'pkp':
                self.ppkp = self.partner_id.ppkp
        return res
