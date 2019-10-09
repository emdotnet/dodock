// Copyright (c) 2016, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Integration Request', {
	refresh: function(frm) {
		frm.page.clear_actions_menu();
		if(frm.doc.status !== 'Completed'){
			frm.page.add_action_item(
				__('Set status as Completed'),
				() => {
					frappe.db.set_value(frm.doctype, frm.doc.name, "status", "Completed", r => {
						frm.reload_doc()
					})
				}
			);
		}

		if(frm.doc.integration_type === 'Webhook' && (frm.doc.status !== 'Completed' || frm.doc.error == 'This type of event is not handled by dokos')) {
			frm.page.add_action_item(
				__('Retry processing the webhook'),
				() => {
					frappe.call({method: "retry_webhook", doc: frm.doc})
					.then(r => {
						frappe.show_alert({message:__("Processing in progress"), indicator:'green'});
						frm.reload_doc()
					})
				}
			);
		}

	}
});
