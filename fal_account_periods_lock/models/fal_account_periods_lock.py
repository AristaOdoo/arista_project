# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.osv import expression
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
from odoo.exceptions import UserError, RedirectWarning
from odoo import api, fields, models, _


class fal_account_periods_lock(models.Model):
    _name = "fal.account.periods.lock"
    _inherit = ['mail.thread']
    _description = "Resurfacing Fiscal Year (v8)"
    _order = "date_start, id"

    def _get_business_type_default(self):
        user_id = self.env['res.users'].browse(self.env.uid)
        return user_id.fal_business_type_id or False

    name = fields.Char(
        string='Period Name', required=True,
        help="Filled it with the Name Of Year", track_visibility='onchange')
    code = fields.Char(string='Code', size=6, required=True, track_visibility='onchange')
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company, readonly=True, states={'draft': [('readonly', False)]})
    fal_business_type_id = fields.Many2one(
        'fal.business.type', string='Business Type', required=True,
        default=_get_business_type_default, readonly=True, states={'draft': [('readonly', False)]})
    date_start = fields.Date(string='Start Date', required=True, track_visibility='onchange', readonly=True, states={'draft': [('readonly', False)]})
    date_stop = fields.Date(string='End Date', required=True, track_visibility='onchange', readonly=True, states={'draft': [('readonly', False)]})
    period_ids = fields.One2many(
        'fal.account.periods.lock.line', 'fiscalyear_id', string='Periods', readonly=True, states={'draft': [('readonly', False)]})
    state = fields.Selection([
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('done', 'Closed'),
    ],
        string='Status', readonly=True, copy=False, default='draft', track_visibility='onchange')
    lock_gap_days_non_adviser = fields.Integer(
        'Lock Gap Days Non-Adviser', default=8, readonly=True, states={'draft': [('readonly', False)]})
    lock_gap_days_adviser = fields.Integer(
        'Lock Gap Days Adviser', default=10, readonly=True, states={'draft': [('readonly', False)]})

    @api.constrains('date_start', 'date_stop')
    def _check_duration(self):
        for lock in self:
            if lock.date_stop < lock.date_start:
                raise UserError(_(
                    'Error!\nThe start date of a fiscal year must precede '
                    'its end date.'))
            for line in lock.period_ids:
                if line.fiscalyear_id.date_stop < line.date_stop or \
                   line.fiscalyear_id.date_stop < line.date_start or \
                   line.fiscalyear_id.date_start > line.date_start or \
                   line.fiscalyear_id.date_start > line.date_stop:
                    raise UserError(_(
                        'Error!\n Start date of the first period and End date of the last period is not in between the date in the header.'))

    def create_period1(self):
        for fy in self:
            return self.create_period(interval=1)

    def create_period3(self):
        for fy in self:
            return self.create_period(interval=3)

    def action_done(self):
        for line in self.period_ids:
            line.action_line_lock()
        self.state = 'done'

    def action_open(self):
        self.state = 'open'

    def action_draft(self):
        for line in self.period_ids:
            line.action_line_open()
        self.state = 'draft'

    def create_period(self, interval=1):
        accountperiodlockline_obj = self.env['fal.account.periods.lock.line']
        for fy in self:
            ds = fy.date_start
            while ds < fy.date_stop:
                accountperiodlockline_obj.create(
                    self.prepare_account_period_lock_line_vals(
                        interval, fy, ds))
                ds = ds + relativedelta(months=interval)
        return True

    def prepare_account_period_lock_line_vals(self, interval, fy, ds):
        de = ds + relativedelta(months=interval, days=-1)
        non_ad_lock_de = de + relativedelta(days=fy.lock_gap_days_non_adviser)
        lock_de = de + relativedelta(days=fy.lock_gap_days_adviser)
        if de > fy.date_stop:
            de = fy.date_stop
        return {
            'name': ds.strftime('%m/%Y'),
            'code': ds.strftime('%m/%Y'),
            'date_start': ds.strftime('%Y-%m-%d'),
            'date_stop': de.strftime('%Y-%m-%d'),
            'non_adviser_locking_date': non_ad_lock_de.strftime('%Y-%m-%d'),
            'adviser_locking_date': lock_de.strftime('%Y-%m-%d'),
            'fiscalyear_id': fy.id,
        }

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=80):
        args = args or []
        domain = []
        if name:
            if operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = [('code', operator, name), ('name', operator, name)]
            else:
                domain = ['|', ('code', operator, name),
                          ('name', operator, name)]
        fys = self.search(expression.AND([domain, args]), limit=limit)
        return fys.name_get()

    def unlink(self):
        for period in self:
            if period.state == 'done':
                raise UserError(_('you cannot delete a Period that is already Closed'))
            raise UserError(_('you cannot delete a Period that is already Closed'))
        return super(fal_account_periods_lock, self).unlink()


class fal_account_periods_lock_line(models.Model):
    _name = "fal.account.periods.lock.line"
    _description = "Period"
    _order = "date_start"

    name = fields.Char('Period Name', required=True, track_visibility='onchange')
    code = fields.Char('Code', size=12, track_visibility='onchange')
    date_start = fields.Date('Start of Period', required=True, readonly=True, track_visibility='onchange', states={'draft': [('readonly', False)]})
    date_stop = fields.Date('End of Period', required=True, readonly=True, states={'draft': [('readonly', False)]})
    fiscalyear_id = fields.Many2one(
        'fal.account.periods.lock', 'Periods Lock Name',
        required=True, index=True, readonly=True, states={'draft': [('readonly', False)]})
    adviser_locking_date = fields.Date(
        'Adviser Locking Date', required=True, readonly=True, states={'draft': [('readonly', False)]})
    non_adviser_locking_date = fields.Date(
        'Non-adviser locking Date', required=True, readonly=True, states={'draft': [('readonly', False)]})
    company_id = fields.Many2one(
        'res.company', string='Company', store=True,
        readonly=True, related='fiscalyear_id.company_id')
    fal_business_type_id = fields.Many2one(
        'fal.business.type', string='Business Type', store=True,
        readonly=True, related='fiscalyear_id.fal_business_type_id')
    state = fields.Selection([
        ('draft', 'Open'),
        ('done', 'Closed'),
    ], string='Status', readonly=True, copy=False, default='draft')

    _sql_constraints = [
        ('name_company_uniq', 'unique(name, fal_business_type_id)',
         'You have overlaps period'),
    ]

    def action_line_lock(self):
        for line in self:
            line.state = 'done'

    def action_line_open(self):
        for line in self:
            line.state = 'draft'

    @api.constrains('date_stop', 'date_start')
    def _check_year_limit(self):
        for line in self:
            if line.date_stop < line.date_start:
                raise UserError(_(
                    'Error!\nThe End date of a fiscal year must precede '
                    'its Start date.'))
            if line.fiscalyear_id.date_stop < line.date_stop or \
               line.fiscalyear_id.date_stop < line.date_start or \
               line.fiscalyear_id.date_start > line.date_start or \
               line.fiscalyear_id.date_start > line.date_stop:

                raise UserError(_(
                    'Error!\n Start date of the first period and End date of the last period is not in between the date in the header.'))

    # To be checked
    @api.returns('self')
    def next(self, period, step):
        ids = self.search([('date_start', '>', period.date_start)])
        if len(ids) >= step:
            return ids[step - 1]
        return False

    @api.model
    def find(self, dt=None, exception=True):
        if not dt:
            dt = fields.date.today()
        args = [('date_start', '<=', dt), ('date_stop', '>=', dt)]
        if self.env.context.get('company_id', False):
            company_id = self.env.context['company_id']
        else:
            user_id = self.env['res.users'].browse(self.env.uid)
            company_id = user_id.company_id.id
        if self.env.context.get('fal_business_type_id', False):
            fal_business_type_id = self.env.context['fal_business_type_id']
        else:
            user_id = self.env['res.users'].browse(self.env.uid)
            fal_business_type_id = user_id.fal_business_type_id.id
        args.append(('company_id', '=', company_id))
        args.append(('fal_business_type_id', '=', fal_business_type_id))
        ids = self.search(args)
        if not ids:
            if exception:
                obj_ref = self.env['ir.model.data'].get_object_reference
                model, action_id = obj_ref('fal_account_periods_lock',
                                           'action_fal_account_periods_lock')
                msg = _('There is no period defined for this date: %s.'
                        '\nPlease go to Configuration/Periods and configure '
                        'a fiscal year.') % dt
                raise UserError(msg)
            else:
                return []
        return ids

    # To be checked, see name_search in fal_account_periods_lock for reference
    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if operator in expression.NEGATIVE_TERM_OPERATORS:
            domain = [('code', operator, name), ('name', operator, name)]
        else:
            domain = ['|', ('code', operator, name), ('name', operator, name)]
        # ids = self.search(
        # expression.AND([domain, args]), limit=limit, context=self._context)
        ids = self.search(expression.AND([domain, args]), limit=limit)
        return ids.name_get()

    def _update_line(self, values):
        fiscalyear = self.mapped('fiscalyear_id')
        for year in fiscalyear:
            fiscal_lines = self.filtered(lambda x: x.fiscalyear_id == year)
            msg = ""
            for line in fiscal_lines:
                if line.date_start and 'date_start' in values:
                    msg += _("Start Of Period") + ": %s -> %s <br/>" % (line.date_start, values['date_start'])
                if line.date_stop and 'date_stop' in values:
                    msg += _("End Of Period") + ": %s -> %s <br/>" % (line.date_stop, values['date_stop'])
                if line.state and 'state' in values:
                    msg += _("Status") + ": %s -> %s <br/>" % (line.state, values['state'])
            if msg != "":
                year.message_post(body=msg)

    def write(self, vals):
        self._update_line(vals)
        return super(fal_account_periods_lock_line, self).write(vals)

    def unlink(self):
        for period in self:
            if period.state == 'done':
                raise UserError(_('you cannot delete a Period that is already Closed'))
        return super(fal_account_periods_lock_line, self).unlink()


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.constrains('date')
    def _check_lock_date_constrains(self):
        # to check lock date when create move
        return True

    # completly overide Odoo method
    def _check_fiscalyear_lock_date(self):
        for move in self:
            # Only check if it's not asset
            if self.env.context.get('force_check') or not(move.asset_id or move.asset_ids or move.asset_depreciated_value):
                period_line_obj = self.env['fal.account.periods.lock.line']
                period_ids = period_line_obj.with_context(
                    company_id=move.company_id.id, fal_business_type_id=move.fal_business_type.id).find(
                    dt=move.date)
                if period_ids:
                    lock_date = period_ids[0].non_adviser_locking_date
                    if self.user_has_groups('account.group_account_manager'):
                        lock_date = period_ids[0].adviser_locking_date
                    lckdt = lock_date
                    if fields.date.today() >= lckdt:
                        raise UserError(_(
                            "You cannot add/modify entries prior to and inclusive "
                            "of the lock date %s. Check the company settings or "
                            "ask someone with the 'Adviser' role") % lock_date)
                    if period_ids[0].state == 'done':
                        raise UserError(_(
                            "You cannot add/modify entries within the entries date period."
                            "The period is not open. Check the company settings or "
                            "ask someone with the 'Adviser' role"))
        return True

    def check_fiscalyear_lock_date_method(self, company_id=False, fal_business_type_id=False, date=False):
        if company_id and fal_business_type_id and date:
            period_line_obj = self.env['fal.account.periods.lock.line']
            period_ids = period_line_obj.with_context(
                company_id=company_id.id, fal_business_type_id=fal_business_type_id.id).find(
                dt=date, exception=False)
            if period_ids:
                lock_date = period_ids[0].non_adviser_locking_date
                if self.user_has_groups('account.group_account_manager'):
                    lock_date = period_ids[0].adviser_locking_date
                lckdt = lock_date
                if fields.date.today() >= lckdt:
                    return False
                if period_ids[0].state == 'done':
                    return False
            else:
                return False
            return True
        return False

    @api.returns('self', lambda value: value.id)
    def copy(self, default=None):
        default = default or {}
        # Duplicated Date should be today's date
        default['date'] = fields.Datetime.now()
        return super(AccountMove, self).copy(default=default)

    def action_post(self):
        for move in self:
            move.with_context(force_check=True)._check_fiscalyear_lock_date()
        result = super(AccountMove, self).action_post()
        return result


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'
