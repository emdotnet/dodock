import { createApp } from "vue";
import TemplateFieldSelectorDialog from "./TemplateFieldSelector.vue";
import EventEmitterMixin from "frappe/public/js/frappe/event_emitter";

frappe.provide("frappe.field_selector_updates");

export default class TemplateFieldSelector {
	constructor(opts) {
		Object.assign(this, opts);
		frappe.field_selector_updates = {};
		Object.assign(frappe.field_selector_updates, EventEmitterMixin);

		if (!this.editor) {
			throw new Error("`editor` parameter");
		}

		this.make_dialog();

		frappe.field_selector_updates.on("done", () => {
			this.selector_area.$destroy();
		});
	}

	make_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Select a field"),
			fields: [
				{
					label: __("Select a reference DocType"),
					fieldname: "references",
					fieldtype: "Link",
					options: "DocType",
					default: this.default_doctype,
					onchange: () => {
						const value = this.dialog.fields_dict.references.value;
						this.default_doctype = value;
						if (value) {
							frappe.field_selector_updates.trigger("reference_update", value);
						} else {
							frappe.field_selector_updates.trigger("clear");
						}
					},
				},
				{
					fieldtype: "HTML",
					fieldname: "upload_area",
				},
			],
			primary_action_label: __("Add"),
			primary_action: () => {
				frappe.field_selector_updates.trigger("submit");
				this.dialog.hide();
			},
		});

		this.wrapper = this.dialog.fields_dict.upload_area.$wrapper[0];

		const app = createApp(TemplateFieldSelectorDialog, {
			quill: this.editor.quill,
			Quill: this.editor.Quill,
			doctype: this.default_doctype,
		});
		app.mount(this.wrapper);
		this.selector_area = app;

		this.dialog.show();
	}
}
