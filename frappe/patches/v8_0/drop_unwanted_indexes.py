# Copyright (c) 2017, Frappe and Contributors
# MIT License. See license.txt
# -*- coding: utf-8 -*-


import frappe

def execute():
	# communication
	unwanted_indexes = ["communication_date_index", "message_id_index", "modified_index", 
		"creation_index", "reference_owner", "communication_date"]
		
	for k in unwanted_indexes:
		try:
			frappe.db.sql("drop index {0} on `tabCommunication`".format(k))
		except:
			pass