// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.views.formview');

frappe.views.FormFactory = class FormFactory extends frappe.views.Factory {
	make(route) {
		var doctype = route[1],
			doctype_layout = frappe.router.doctype_layout || doctype;

		if (!frappe.views.formview[doctype_layout]) {
			frappe.model.with_doctype(doctype, () => {
				this.page = frappe.container.add_page("form/" + doctype_layout);
				frappe.views.formview[doctype_layout] = this.page;
				this.page.frm = new frappe.ui.form.Form(doctype, this.page, true, frappe.router.doctype_layout);
				this.show_doc(route);
			});
		} else {
			this.show_doc(route);
		}
		this.setup_events();
	}

	setup_events() {
		if (!this.initialized) {
			$(document).on("page-change", function() {
				frappe.ui.form.close_grid_form();
			});

			frappe.realtime.on("doc_viewers", function(data) {
				// set users that currently viewing the form
				frappe.ui.form.set_users(data, 'viewers');
			});

			frappe.realtime.on("doc_typers", function(data) {
				// set users that currently typing on the form
				frappe.ui.form.set_users(data, 'typers');
			});
		}
		this.initialized = true;
	}

	show_doc(route) {
		var doctype = route[1],
			doctype_layout = frappe.router.doctype_layout || doctype,
			name = route.slice(2).join("/");

		if (frappe.model.new_names[name]) {
			// document has been renamed, reroute
			name = frappe.model.new_names[name];
			frappe.set_route("Form", doctype_layout, name);
			return;
		}

		const doc = frappe.get_doc(doctype, name);
		if (doc && (doc.__islocal || frappe.model.is_recent(doc))) {
			// is document available and recent?
			this.render(doctype_layout, name);
		} else {
			this.fetch_and_render(doctype, name, doctype_layout);
		}
	}

	fetch_and_render(doctype, name, doctype_layout) {
		frappe.model.with_doc(doctype, name, (name, r) => {
			if (r && r['403']) return; // not permitted

			if (!(locals[doctype] && locals[doctype][name])) {
				if (name && name==='new') {
					this.render_new_doc(doctype, name, doctype_layout);
				} else {
					frappe.show_not_found(route);
				}
				return;
			}
			this.render(doctype_layout, name);
		});
	}

	render_new_doc(doctype, name, doctype_layout) {
		const new_name = frappe.model.make_new_doc_and_get_name(doctype, true);
		if (new_name===name) {
			this.render(doctype_layout, name);
		} else {
			frappe.set_route("Form", doctype_layout, new_name);
		}
	}

	render(doctype_layout, name) {
		frappe.container.change_to("form/" + doctype_layout);
		frappe.views.formview[doctype_layout].frm.refresh(name);
	}
}
