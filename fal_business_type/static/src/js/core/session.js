odoo.define('fal_business_type.Session', function (require) {
"use strict";

var Session = require('web.Session');
var utils = require('web.utils');



Session.include({
    setBusinessTypes: function (main_company_id, company_ids, main_business_company_id, business_company_ids) {
        // Write into odoo via rpc
        this.rpc('/web/dataset/call_kw/res.users/sudo_write', {
                "model": "res.users",
                "method": "sudo_write",
                "args": [this.uid, {fal_business_type_id: main_company_id, fal_business_type_ids: [[6, 0, company_ids]], company_id: main_business_company_id}],
                "kwargs": {}
            }).then(function () {
            // Also Call Odoo SetCompanies Method
            var hash = $.bbq.getState()
            hash.cids = business_company_ids.sort(function(a, b) {
                if (a === main_business_company_id) {
                    return -1;
                } else if (b === main_business_company_id) {
                    return 1;
                } else {
                    return a - b;
                }
            }).join(',');
            utils.set_cookie('cids', hash.cids || String(main_business_company_id));
            $.bbq.pushState({'cids': hash.cids}, 0);
            window.location.reload();
        });
    },

    setCompanies: function (main_company_id, company_ids, current_company_business_type_id, current_company_business_type_ids) {
        // Write into odoo via rpc
        // No need to manage companies here, as odoo will manage with cids
        this.rpc('/web/dataset/call_kw/res.users/sudo_write', {
                "model": "res.users",
                "method": "sudo_write",
                "args": [this.uid, {fal_business_type_id: current_company_business_type_id, fal_business_type_ids: [[6, 0, current_company_business_type_ids]]}],
                "kwargs": {}
            }).then(function () {
            // Call Odoo standard
            var hash = $.bbq.getState()
            hash.cids = company_ids.sort(function(a, b) {
                if (a === main_company_id) {
                    return -1;
                } else if (b === main_company_id) {
                    return 1;
                } else {
                    return a - b;
                }
            }).join(',');
            utils.set_cookie('cids', hash.cids || String(main_company_id));
            $.bbq.pushState({'cids': hash.cids}, 0);
            location.reload();
        });
    },
});

});
