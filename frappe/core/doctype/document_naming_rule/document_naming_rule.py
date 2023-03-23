# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import parse_naming_series
from frappe.utils.data import evaluate_filters


class DocumentNamingRule(Document):
	def validate(self):
		self.validate_fields_in_conditions()
		self.validate_prefix()

	def clear_doctype_map(self):
		frappe.cache_manager.clear_doctype_map(self.doctype, self.document_type)

	def on_update(self):
		self.clear_doctype_map()

	def on_trash(self):
		self.clear_doctype_map()

	def validate_fields_in_conditions(self):
		if self.has_value_changed("document_type"):
			docfields = [x.fieldname for x in frappe.get_meta(self.document_type).fields]
			for condition in self.conditions:
				if condition.field not in docfields:
					frappe.throw(
						_("{0} is not a field of doctype {1}").format(
							frappe.bold(condition.field), frappe.bold(self.document_type)
						)
					)

	def validate_prefix(self):
		if self.naming_by == "Format":
			if "#" not in self.prefix:
				frappe.throw(
					_("Prefix {0} should contain '#' symbols to be a valid format.").format(repr(self.prefix))
				)
			self.prefix_digits = 0
		else:  # Counter
			if "#" in self.prefix:
				frappe.msgprint(
					_("Prefix {0} should not contain a '#' symbol when using Naming Rule 'Counter'.").format(
						repr(self.prefix)
					),
					title=_("Error"),
					indicator="red",
				)

	def post_increment_counter(self) -> int:
		if self.naming_by == "Format":
			raise Exception("Cannot increment counter for non-numbered Document Naming Rule")
		else:  # Counter
			# TODO: Make this atomic
			counter = frappe.db.get_value(self.doctype, self.name, "counter", for_update=True) or 0
			frappe.db.set_value(self.doctype, self.name, "counter", counter + 1)
			return counter

	def apply(self, doc):
		"""
		Apply naming rules for the given document. Will set `name` if the rule is matched.
		"""
		if self.conditions:
			if not evaluate_filters(
				doc, [(self.document_type, d.field, d.condition, d.value) for d in self.conditions]
			):
				return

		if self.naming_by == "Format":
			naming_series = parse_naming_series(self.prefix, doc=doc, series_name=self.prefix)
			new_name = naming_series
		else:  # Counter
			naming_series = parse_naming_series(self.prefix, doc=doc)
			counter_format = "%0" + str(self.prefix_digits) + "d"
			counter = self.post_increment_counter()
			new_name = naming_series + counter_format % (counter + 1)

		doc.name = new_name


@frappe.whitelist()
def update_current(name, new_counter):
	frappe.only_for("System Manager")
	frappe.db.set_value("Document Naming Rule", name, "counter", new_counter)
