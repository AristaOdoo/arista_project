odoo.define('fal_business_type.SwitchBusinessTypeMenu', function(require) {
"use strict";
/**
 * When Odoo is configured in multi-company mode, users should obviously be able
 * to switch their interface from one company to the other.  This is the purpose
 * of this widget, by displaying a dropdown menu in the systray.
 */

var config = require('web.config');
var core = require('web.core');
var session = require('web.session');
var SystrayMenu = require('web.SystrayMenu');
var SwitchCompanyMenu = require('web.SwitchCompanyMenu');
var Widget = require('web.Widget');

var _t = core._t;

var SwitchBusinessTypeMenu = Widget.extend({
    template: 'SwitchBusinessTypeMenu',
    events: {
        'click .dropdown-item[data-menu] div.log_into': '_onSwitchBusinessTypeClick',
        'click .dropdown-item[data-menu] div.toggle_company': '_onToggleBusinessTypeClick',
    },
    /**
     * @override
     */
    init: function () {
        this._super.apply(this, arguments);
        this.isMobile = config.device.isMobile;
        this._onSwitchBusinessTypeClick = _.debounce(this._onSwitchBusinessTypeClick, 1500, true);
    },

    /**
     * @override
     */
    willStart: function () {
        var self = this;
        // Company Parameter
        this.allowed_company_ids = String(session.user_context.allowed_company_ids)
                                    .split(',')
                                    .map(function (id) {return parseInt(id);});
        this.user_companies = session.user_companies.allowed_companies;
        this.current_company = this.allowed_company_ids[0];
        this.current_company_name = _.find(session.user_companies.allowed_companies, function (company) {
            return company[0] === self.current_company;
        })[1];
        // Business Type Parameter
        this.allowed_business_type_ids = session.user_business_types.business_types.map(function (id) {return parseInt(id);})
        this.user_business_types = session.user_business_types.allowed_business_types;
        this.current_business_type = session.user_business_types.current_business_type[0];
        this.current_business_type_name = session.user_business_types.current_business_type[1];
        this.company_business_type_mapping = session.company_business_type_map;
        // Auto click business type if mapping not match
        // Very dirty ways, but whatever
        for (var i = 0; i<this.company_business_type_mapping.length; i++){
            // Business type company are not match selected company
            // Automatically click setBusinessTypes
            // And also include the company in case it did not have
            if (this.company_business_type_mapping[i][1] === this.current_business_type){
                if (this.company_business_type_mapping[i][0] !== this.current_company){
                    var new_allowed_company_ids = this.allowed_company_ids
                    if (new_allowed_company_ids.indexOf(this.company_business_type_mapping[i][0]) === -1){
                        new_allowed_company_ids.push(this.company_business_type_mapping[i][0])
                    }
                    session.setBusinessTypes(this.current_business_type, this.allowed_business_type_ids, this.company_business_type_mapping[i][0], new_allowed_company_ids);
                }
            }
        }
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent|KeyEvent} ev
     * We manage Business Type Click Behavior
     * If we switch business type, means we need to switch the company too.
     * Also, when switching business type
     * So, we need to manage the allowed companies to match selected business type
     */
    _onSwitchBusinessTypeClick: function (ev) {
        var self = this;
        if (ev.type == 'keydown' && ev.which != $.ui.keyCode.ENTER && ev.which != $.ui.keyCode.SPACE) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        var dropdownItem = $(ev.currentTarget).parent();
        var dropdownMenu = dropdownItem.parent();
        var companyID = dropdownItem.data('company-id');
        var allowed_business_type_ids = this.allowed_business_type_ids;
        var company_business_type_mapping = this.company_business_type_mapping;
        if (dropdownItem.find('.fa-square-o').length) {
            // 1 enabled company: Stay in single company mode
            if (this.allowed_business_type_ids.length === 1) {
                dropdownMenu.find('.fa-check-square').removeClass('fa-check-square').addClass('fa-square-o');
                dropdownItem.find('.fa-square-o').removeClass('fa-square-o').addClass('fa-check-square');
                allowed_business_type_ids = [companyID]
            } else { // Multi company mode
                allowed_business_type_ids.push(companyID);
                dropdownItem.find('.fa-square-o').removeClass('fa-square-o').addClass('fa-check-square');
            }
        }
        $(ev.currentTarget).attr('aria-pressed', 'true');
        // We store current business type / business types
        // In case of any failure, it goes back to standard value without error
        var current_company_ids = this.allowed_company_ids
        var current_company_id = current_company_ids[0];
        for (var i = 0; i<company_business_type_mapping.length; i++){
            // If business type is the id selected, current company are the company of selected
            // Business type
            if (company_business_type_mapping[i][1] === companyID){
                current_company_id = company_business_type_mapping[i][0]
            }
            // If business type ids is allowed (which is logical), #TDE: Do we need 1st if?
            // If companies selected is not in allowed companies list, include it
            if (allowed_business_type_ids.indexOf(company_business_type_mapping[i][1]) !== -1){
                if (current_company_ids.indexOf(company_business_type_mapping[i][0]) === -1){
                    current_company_ids.push(company_business_type_mapping[i][0])
                }
            }
        }
        // Arista Special Case, If non-consolidation, user only allowed to see 1 business types
        session.user_has_group('fal_business_type.fal_arista_consolidation_group').then(function(has_group) {
            if (has_group) {
                session.setBusinessTypes(companyID, allowed_business_type_ids, current_company_id, current_company_ids);
            }else{
                allowed_business_type_ids = [companyID]
                current_company_ids = [current_company_id]
                session.setBusinessTypes(companyID, allowed_business_type_ids, current_company_id, current_company_ids);
            }
        });
        session.setBusinessTypes(companyID, allowed_business_type_ids, current_company_id, current_company_ids);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {MouseEvent|KeyEvent} ev
     * We manage Business Type toggle Behavior
     * If we toggle In business type, means we need to give allowed in the companies too.
     * If we toggle Out, doesn't means we do not want to see the companies, so do nothing
     */
    _onToggleBusinessTypeClick: function (ev) {
        var self = this;
        // Special Arista Case, If non-consolidation, user can't toggle business type
        session.user_has_group('fal_business_type.fal_arista_consolidation_group').then(function(has_group) {
            if (has_group) {
                if (ev.type == 'keydown' && ev.which != $.ui.keyCode.ENTER && ev.which != $.ui.keyCode.SPACE) {
                    return;
                }
                ev.preventDefault();
                ev.stopPropagation();
                var dropdownItem = $(ev.currentTarget).parent();
                var companyID = dropdownItem.data('company-id');
                var allowed_business_type_ids = self.allowed_business_type_ids;
                var current_business_unit_id = self.current_business_type;
                var company_business_type_mapping = self.company_business_type_mapping;
                if (dropdownItem.find('.fa-square-o').length) {
                    allowed_business_type_ids.push(companyID);
                    dropdownItem.find('.fa-square-o').removeClass('fa-square-o').addClass('fa-check-square');
                } else {
                    if (allowed_business_type_ids.length > 1 && current_business_unit_id != companyID){
                        allowed_business_type_ids.splice(allowed_business_type_ids.indexOf(companyID), 1);
                        dropdownItem.find('.fa-check-square').addClass('fa-square-o').removeClass('fa-check-square');
                    }
                }
                // We store current business type / business types
                // In case of any failure, it goes back to standard value without error
                var current_company_ids = self.allowed_company_ids
                var current_company_id = current_company_ids[0];
                for (var i = 0; i<company_business_type_mapping.length; i++){
                    if (allowed_business_type_ids.indexOf(company_business_type_mapping[i][1]) !== -1){
                        if (current_company_ids.indexOf(company_business_type_mapping[i][0]) === -1){
                            current_company_ids.push(company_business_type_mapping[i][0])
                        }
                    }
                }
                session.setBusinessTypes(current_business_unit_id, allowed_business_type_ids, current_company_id, current_company_ids);
            }else{
                return true;
            }
        });

    },

});

if (session.display_switch_business_types_menu) {
    var index = SystrayMenu.Items.indexOf(SwitchCompanyMenu);
    if (index >= 0) {
        SystrayMenu.Items.splice(index, 0, SwitchBusinessTypeMenu);
    }
    else{
        SystrayMenu.Items.push(SwitchBusinessTypeMenu);
    }
}

return SwitchBusinessTypeMenu;

});
