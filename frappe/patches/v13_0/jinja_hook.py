# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from click import secho

def execute():
	if frappe.get_hooks('jenv'):
		print()
		secho('WARNING: The hook "jenv" is deprecated. Follow the migration guide to use the new "jinja" hook.', fg='yellow')
		secho('https://github.com/frappe/frappe/wiki/Migrating-to-Version-13', fg='yellow')
		print()