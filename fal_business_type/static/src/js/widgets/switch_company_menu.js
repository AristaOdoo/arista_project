odoo.define('fal_business_type.SwitchCompanyMenu', function(require) {
"use strict";

var SwitchCompanyMenu = require('web.SwitchCompanyMenu');
var session = require('web.session');

SwitchCompanyMenu.include({
    /**
     * @override
     *
     * @param {object} state - At Start add mapping
     * mapping is a list of company and business type relation (similar to many2many table)
     * structure [(company ID , business type ID)]
     * example [(1,1),(2,2)]
     */
    willStart: function (state) {
        var self = this;
        this.company_business_type_mapping = session.company_business_type_map;
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent|KeyEvent} ev
     * We manage Company Click Behavior
     * If we switch company, means we need to switch the business type too. But where is not problem
     * Just take the first business type correspond to the selected company in the mapping
     * Also, when switching company, there is a possibility to lose the allowed companies too
     * So, we need to manage the allowed business type to match allowed companies
     */
    _onSwitchCompanyClick: function (ev) {
        if (ev.type == 'keydown' && ev.which != $.ui.keyCode.ENTER && ev.which != $.ui.keyCode.SPACE) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        var dropdownItem = $(ev.currentTarget).parent();
        var dropdownMenu = dropdownItem.parent();
        var companyID = dropdownItem.data('company-id');
        // Special Arista Case, No one can click on Company
        return true

        var allowed_company_ids = this.allowed_company_ids;
        var company_business_type_mapping = this.company_business_type_mapping;
        if (dropdownItem.find('.fa-square-o').length) {
            // 1 enabled company: Stay in single company mode
            if (this.allowed_company_ids.length === 1) {
                if (this.isMobile) {
                    dropdownMenu = dropdownMenu.parent();
                }
                dropdownMenu.find('.fa-check-square').removeClass('fa-check-square').addClass('fa-square-o');
                dropdownItem.find('.fa-square-o').removeClass('fa-square-o').addClass('fa-check-square');
                allowed_company_ids = [companyID];
            } else { // Multi company mode
                allowed_company_ids.push(companyID);
                dropdownItem.find('.fa-square-o').removeClass('fa-square-o').addClass('fa-check-square');
            }
        }
        $(ev.currentTarget).attr('aria-pressed', 'true');
        // We store current business type / business types
        // In case of any failure, it goes back to standard value without error
        var current_company_business_type_id = session.user_business_types.current_business_type[0];
        var current_company_business_type_ids = session.user_business_types.business_types.map(function (id) {return parseInt(id);})
        var business_type_assigned = false
        for (var i = 0; i<company_business_type_mapping.length; i++){
            // If we find the company we are switching for, set the current business ID to the
            // business ID of the company, then stop assigning if later found again
            // Also push the business type ID into the bussiness type IDS
            if (company_business_type_mapping[i][0] === companyID && !business_type_assigned){
                current_company_business_type_id = company_business_type_mapping[i][1]
                current_company_business_type_ids.push(company_business_type_mapping[i][1])
                business_type_assigned = true
            }
            // We need to manage the allowed business types based on allowed companies
            // In this case, the allowed business type needed already managed above, so we
            // just need to remove other allowed business type that is not on allowed companies
            if (current_company_business_type_ids.indexOf(company_business_type_mapping[i][1]) !== -1){
                if (allowed_company_ids.indexOf(company_business_type_mapping[i][0]) === -1){
                    current_company_business_type_ids.splice(current_company_business_type_ids.indexOf(company_business_type_mapping[i][1]), 1);
                }
            }
        }

        session.setCompanies(companyID, allowed_company_ids, current_company_business_type_id, current_company_business_type_ids);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent|KeyEvent} ev
     * We manage Company Toggle Behavior
     * If we toggle check company, means we need to give at least 1 allowed in the business type
     * correspons to the toggle we select.
     * If we toggle uncheck company, means we need to uncheck all allowed business type correspond
     * to the company we uncheck
     */
    _onToggleCompanyClick: function (ev) {
        if (ev.type == 'keydown' && ev.which != $.ui.keyCode.ENTER && ev.which != $.ui.keyCode.SPACE) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        var dropdownItem = $(ev.currentTarget).parent();
        var companyID = dropdownItem.data('company-id');
        // Special Arista Case, No one can click on Company
        return true

        var allowed_company_ids = this.allowed_company_ids;
        var current_company_id = allowed_company_ids[0];
        var company_business_type_mapping = this.company_business_type_mapping;
        if (dropdownItem.find('.fa-square-o').length) {
            allowed_company_ids.push(companyID);
            dropdownItem.find('.fa-square-o').removeClass('fa-square-o').addClass('fa-check-square');
            $(ev.currentTarget).attr('aria-checked', 'true');
        } else {
            allowed_company_ids.splice(allowed_company_ids.indexOf(companyID), 1);
            dropdownItem.find('.fa-check-square').addClass('fa-square-o').removeClass('fa-check-square');
            $(ev.currentTarget).attr('aria-checked', 'false');
        }
        // We store current business type / business types
        // In case of any failure, it goes back to standard value without error
        var current_company_business_type_id = session.user_business_types.current_business_type[0];
        var current_company_business_type_ids = session.user_business_types.business_types.map(function (id) {return parseInt(id);})
        var company_already_checked = []
        for (var i = 0; i<company_business_type_mapping.length; i++){
            // If this is allowed company, and the business type correspond to the company
            // is not available, add it. Then, we store the companies that has been checked, so
            // we do not put all business type correspond to this company
            if (allowed_company_ids.indexOf(company_business_type_mapping[i][0]) !== -1){
                if (current_company_business_type_ids.indexOf(company_business_type_mapping[i][1]) === -1){
                    if (company_already_checked.indexOf(company_business_type_mapping[i][0]) === -1){
                        current_company_business_type_ids.push(company_business_type_mapping[i][1])
                    }
                }
                company_already_checked.push(company_business_type_mapping[i][0])
            // In contrast, if the company is not in available company
            // we need to remove the business type available in business type ids
            }else{
                if (current_company_business_type_ids.indexOf(company_business_type_mapping[i][1]) !== -1){
                    current_company_business_type_ids.splice(current_company_business_type_ids.indexOf(company_business_type_mapping[i][1]), 1);
                }
            }
        }
        session.setCompanies(current_company_id, allowed_company_ids, current_company_business_type_id, current_company_business_type_ids);
    },
});

});
