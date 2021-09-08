# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class AccessLog(Document):
	pass


@frappe.whitelist()
@frappe.write_only()
def make_access_log(doctype=None, document=None, method=None, file_type=None,
		report_name=None, filters=None, page=None, columns=None):

	user = frappe.session.user

	doc = frappe.get_doc({
		'doctype': 'Access Log',
		'user': user,
		'export_from': doctype,
		'reference_document': document,
		'file_type': file_type,
		'report_name': report_name,
		'page': page,
		'method': method,
		'filters': frappe.utils.cstr(filters) if filters else None,
		'columns': columns
	})
	doc.insert(ignore_permissions=True)

	# `frappe.db.commit` added because insert doesnt `commit` when called in GET requests like `printview`
	if frappe.request and frappe.request.method == 'GET':
		frappe.db.commit()
