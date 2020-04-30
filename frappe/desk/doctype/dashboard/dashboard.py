# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
from frappe.model.document import Document
import frappe

class Dashboard(Document):
	def on_update(self):
		if self.is_default:
			# make all other dashboards non-default
			frappe.db.sql('''update
				tabDashboard set is_default = 0 where name != %s''', self.name)

@frappe.whitelist()
def get_permitted_charts(dashboard_name):
	permitted_charts = []
	dashboard = frappe.get_doc('Dashboard', dashboard_name)
	for chart in dashboard.charts:
		if frappe.has_permission('Dashboard Chart', doc=chart.chart):
			permitted_charts.append(chart)
	return permitted_charts

@frappe.whitelist()
def get_permitted_cards(dashboard_name):
	permitted_cards = []
	dashboard = frappe.get_doc('Dashboard', dashboard_name)
	for card in dashboard.cards:
		if frappe.has_permission('Number Card', doc=card.card):
			permitted_cards.append(card)
	return permitted_cards