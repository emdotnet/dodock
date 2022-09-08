# Copyright (c) 2021, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.doctype.website_settings.website_settings import get_website_settings


class TestWebsiteSettings(FrappeTestCase):
	def test_child_items_in_top_bar(self):
		ws = frappe.get_doc("Website Settings")
		ws.append(
			"top_bar_items",
			{"label": "Parent Item"},
		)
		ws.append(
			"top_bar_items",
			{"parent_label": "Parent Item", "label": "Child Item"},
		)
		ws.save()

		context = get_website_settings()

		for item in context.top_bar_items:
			if item.label == "Parent Item":
				self.assertEqual(item.child_items[0].label, "Child Item")
				break
		else:
			self.fail("Child items not found")
