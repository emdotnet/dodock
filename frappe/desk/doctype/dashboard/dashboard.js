// Copyright (c) 2019, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Dashboard', {
	refresh: function(frm) {
		frm.add_custom_button(__("Show Dashboard"), () => frappe.set_route('dashboard', frm.doc.name));

		if (!frappe.boot.developer_mode) {
			frm.disable_form();
		}

		frm.set_query("chart", "charts", function() {
			return {
				filters: {
					is_public: 1,
					is_standard: 1
				}
			};
		});

		frm.set_query("card", "cards", function() {
			return {
				filters: {
					is_public: 1,
					is_standard: 1
				}
			};
		});
	}
});
