# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt


import frappe

def execute():
	frappe.reload_doctype('Custom Role')
	
	# set ref doctype in custom role for reports
	frappe.db.sql(""" update `tabCustom Role` set 
		`tabCustom Role`.ref_doctype = (select ref_doctype from `tabReport` where name = `tabCustom Role`.report)
		where `tabCustom Role`.report is not null""")
