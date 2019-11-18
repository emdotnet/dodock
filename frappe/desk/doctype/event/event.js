// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide("frappe.desk");

frappe.ui.form.on("Event", {
	onload: function(frm) {
		frm.set_query('reference_doctype', "event_participants", function() {
			return {
				"filters": {
					"issingle": 0,
				}
			};
		});
		frm.set_query('google_calendar', function() {
			return {
				filters: {
					"owner": frappe.session.user
				}
			};
		});
	},
	refresh: function(frm) {
		if(frm.doc.event_participants) {
			frm.doc.event_participants.forEach(value => {
				frm.add_custom_button(__(value.reference_docname), function() {
					frappe.set_route("Form", value.reference_doctype, value.reference_docname);
				}, __("Participants"));
			})
		}

		frm.page.set_inner_btn_group_as_primary(__("Add Participants"));

		frm.add_custom_button(__('Add Contacts'), function() {
			new frappe.desk.eventParticipants(frm, "Contact");
		}, __("Add Participants"));
	},
	repeat_this_event: function(frm) {
		if(frm.doc.repeat_this_event === 1) {
			new frappe.CalendarRecurrence(frm);
		}
	}
});

frappe.ui.form.on("Event Participants", {
	event_participants_remove: function(frm, cdt, cdn) {
		if (frm.doc.event_participants.length){
			frappe.call({
				type: "POST",
				method: "frappe.desk.doctype.event.event.delete_communication",
				args: {
					"event": frm.doc,
					"reference_doctype": cdt,
					"reference_docname": cdn
				},
				freeze: true,
				callback: function(r) {
					if(r.exc) {
						frappe.show_alert({
							message: __("{0}", [r.exc]),
							indicator: 'orange'
						});
					}
				}
			});
		}
	}
});

frappe.desk.eventParticipants = class eventParticipants {
	constructor(frm, doctype) {
		this.frm = frm;
		this.doctype = doctype;
		this.make();
	}

	make() {
		let me = this;

		let table = me.frm.get_field("event_participants").grid;
		new frappe.ui.form.LinkSelector({
			doctype: me.doctype,
			dynamic_link_field: "reference_doctype",
			dynamic_link_reference: me.doctype,
			fieldname: "reference_docname",
			target: table,
			txt: ""
		});
	}
};
