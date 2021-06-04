# Copyright (c) 2017, Frappe and Contributors
# MIT License. See license.txt


import frappe

def execute():
	""" change the XLS option as XLSX in the auto email report """

	frappe.reload_doc("email", "doctype", "auto_email_report")

	auto_email_list = frappe.get_all("Auto Email Report", filters={"format": "XLS"})
	for auto_email in auto_email_list:
		frappe.db.set_value("Auto Email Report", auto_email.name, "format", "XLSX")
