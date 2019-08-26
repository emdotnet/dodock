// Copyright (c) 2016, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Payment Gateway', {
	onload: function(frm) {
		frm.set_query('fee_account', function(doc) {
			return {
				filters: {
					"root_type": "Expense",
					"is_group": 0
				}
			};
		});

		frm.set_query('cost_center', function(doc) {
			return {
				filters: {
					"is_group": 0
				}
			};
		});
	}
});
