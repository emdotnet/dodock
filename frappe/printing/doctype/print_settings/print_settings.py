# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE


import frappe
from frappe import _
from frappe.utils import cint

from frappe.model.document import Document

class PrintSettings(Document):
	def on_update(self):
		frappe.clear_cache()

@frappe.whitelist()
def is_print_server_enabled():
	if not hasattr(frappe.local, 'enable_print_server'):
		frappe.local.enable_print_server = cint(frappe.db.get_single_value('Print Settings',
			'enable_print_server'))

	return frappe.local.enable_print_server
