odoo.define('fal_ledger_report.fal_ledger_report', function (require) {
"use strict";

var Account_report_generic = require('account_reports.account_report');

Account_report_generic.include({
    render_searchview_buttons: function () {
        var self = this;
        this._super();
        if (this.report_options.filter_dms) {
            this.$searchview_buttons.find('.o_dms_reports_filter_input').val(this.report_options.filter_dms);
        }
        this.$searchview_buttons.find('.o_dms_reports_filter_button').click(function (event) {
            self.report_options.filter_dms = self.$searchview_buttons.find('.o_dms_reports_filter_input').val();
            self.reload()
        });
        return this.$searchview_buttons;
    },
});

});

