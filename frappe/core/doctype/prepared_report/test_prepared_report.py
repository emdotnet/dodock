# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import json
import time
import unittest
from contextlib import contextmanager

import frappe
from frappe.desk.query_report import generate_report_result, get_report_doc
from frappe.tests.utils import FrappeTestCase, timeout


@unittest.skip("Skipped in CI")
class TestPreparedReport(FrappeTestCase):
	@classmethod
	def tearDownClass(cls):
		for r in frappe.get_all("Prepared Report", pluck="name"):
			frappe.delete_doc("Prepared Report", r, force=True, delete_permanently=True)

		frappe.db.commit()

	@timeout(seconds=20)
	def wait_for_status(self, report, status):
		frappe.db.commit()  # Flush changes first
		while True:
			frappe.db.rollback()  # read new data
			report.reload()
			if report.status == status:
				break
			# Cheap blocking behaviour
			time.sleep(0.5)

	def create_prepared_report(self, report=None, commit=True):
		doc = frappe.get_doc(
			{
				"doctype": "Prepared Report",
				"report_name": report or "Database Storage Usage By Tables",
			}
		).insert()

		if commit:
			frappe.db.commit()

		return doc

	def test_queueing(self):
		doc = self.create_prepared_report()
		self.assertEqual("Queued", doc.status)
		self.assertTrue(doc.queued_at)

		self.wait_for_status(doc, "Completed")

		doc = frappe.get_last_doc("Prepared Report")
		self.assertTrue(doc.job_id)
		self.assertTrue(doc.report_end_time)

	def test_prepared_data(self):
		doc = self.create_prepared_report()
		self.wait_for_status(doc, "Completed")

		prepared_data = json.loads(doc.get_prepared_data().decode("utf-8"))
		generated_data = generate_report_result(get_report_doc("Database Storage Usage By Tables"))
		self.assertEqual(len(prepared_data["columns"]), len(generated_data["columns"]))
		self.assertEqual(len(prepared_data["result"]), len(generated_data["result"]))
		self.assertEqual(len(prepared_data), len(generated_data))

	def test_start_status(self):
		if frappe.db.db_type == "postgres":
			return

		with test_report(report_type="Query Report", query="select sleep(5)") as report:
			doc = self.create_prepared_report(report.name)
			self.wait_for_status(doc, "Started")


@contextmanager
def test_report(**args):
	try:
		report = frappe.new_doc("Report")
		report.update(args)
		if not report.report_name:
			report.report_name = frappe.generate_hash()
		if not report.ref_doctype:
			report.ref_doctype = "ToDo"
		report.insert()
		yield report
	finally:
		report.delete()
