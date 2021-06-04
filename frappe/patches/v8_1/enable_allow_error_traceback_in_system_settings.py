# Copyright (c) 2017, Frappe and Contributors
# MIT License. See license.txt


import frappe

def execute():
	""" enable the allow_enable_traceback property in system settings """

	frappe.reload_doc("core", "doctype", "system_settings")
	doc = frappe.get_doc("System Settings", "System Settings")
	doc.allow_error_traceback = 1
	doc.flags.ignore_permissions=True
	doc.flags.ignore_mandatory=True
	doc.save()