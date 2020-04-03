# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json,datetime
from urllib.parse import urlencode, parse_qs
from six import string_types, text_type
from frappe.utils import get_request_session
from frappe import _
from frappe.model.document import Document

def make_get_request(url, auth=None, headers=None, data=None):
	if not auth:
		auth = ''
	if not data:
		data = {}
	if not headers:
		headers = {}

	try:
		s = get_request_session()
		frappe.flags.integration_request = s.get(url, data={}, auth=auth, headers=headers)
		frappe.flags.integration_request.raise_for_status()
		return frappe.flags.integration_request.json()

	except Exception as exc:
		frappe.log_error(frappe.get_traceback())
		raise exc

def make_post_request(url, auth=None, headers=None, data=None):
	if not auth:
		auth = ''
	if not data:
		data = {}
	if not headers:
		headers = {}

	try:
		s = get_request_session()
		frappe.flags.integration_request = s.post(url, data=data, auth=auth, headers=headers)
		frappe.flags.integration_request.raise_for_status()

		if frappe.flags.integration_request.headers.get("content-type") == "text/plain; charset=utf-8":
			return parse_qs(frappe.flags.integration_request.text)

		return frappe.flags.integration_request.json()
	except Exception as exc:
		frappe.log_error()
		raise exc

def create_request_log(data, integration_type, service_name, name=None):
	if isinstance(data, string_types):
		data = json.loads(data)

	integration_request = frappe.get_doc({
		"doctype": "Integration Request",
		"integration_type": integration_type,
		"integration_request_service": service_name,
		"reference_doctype": data.get("reference_doctype"),
		"reference_docname": data.get("reference_docname"),
		"data": json.dumps(data, default=json_handler, indent=4)
	})

	if name:
		integration_request.flags._name = name

	integration_request.insert(ignore_permissions=True)
	frappe.db.commit()

	return integration_request

def get_payment_gateway_controller(payment_gateway):
	'''Return payment gateway controller'''
	gateway = frappe.get_doc("Payment Gateway", payment_gateway)
	if gateway.gateway_controller is None:
		try:
			return frappe.get_doc("{0} Settings".format(payment_gateway))
		except Exception:
			frappe.throw(_("{0} Settings not found").format(payment_gateway))
	else:
		try:
			return frappe.get_doc(gateway.gateway_settings, gateway.gateway_controller)
		except Exception:
			frappe.throw(_("{0} Settings not found").format(payment_gateway))


@frappe.whitelist(allow_guest=True, xss_safe=True)
def get_checkout_url(**kwargs):
	try:
		if kwargs.get('payment_gateway'):
			doc = frappe.get_doc("{0} Settings".format(kwargs.get('payment_gateway')))
			return doc.get_payment_url(**kwargs)
		else:
			raise Exception
	except Exception:
		frappe.respond_as_web_page(_("Something went wrong"),
			_("Looks like something is wrong with this site's payment gateway configuration. No payment has been made."),
			indicator_color='red',
			http_status_code=frappe.ValidationError.http_status_code)

def create_payment_gateway(gateway, settings=None, controller=None):
	# NOTE: we don't translate Payment Gateway name because it is an internal doctype
	if not frappe.db.exists("Payment Gateway", gateway):
		payment_gateway = frappe.get_doc({
			"doctype": "Payment Gateway",
			"gateway": gateway,
			"gateway_settings": settings,
			"gateway_controller": controller
		})
		payment_gateway.insert(ignore_permissions=True)

def json_handler(obj):
	if isinstance(obj, (datetime.date, datetime.timedelta, datetime.datetime)):
		return text_type(obj)

def get_gateway_controller(doctype, docname):
	reference_doc = frappe.get_doc(doctype, docname)
	gateway_controller = frappe.db.get_value("Payment Gateway",\
		reference_doc.payment_gateway, "gateway_controller")
	return gateway_controller

class PaymentGatewayController(Document):
	def finalize_request(self, reference_no=None):
		redirect_to = self.data.get('redirect_to') or 'payment-success'
		redirect_message = self.data.get('redirect_message') or None

		if self.flags.status_changed_to in ["Completed", "Autorized", "Pending"] and self.reference_document:
			custom_redirect_to = None
			try:
				custom_redirect_to = self.reference_document\
					.run_method("on_payment_authorized", self.flags.status_changed_to, reference_no)
			except Exception:
				frappe.log_error(frappe.get_traceback(), _("Payment custom redirect error"))

			if custom_redirect_to and custom_redirect_to != "no-redirection":
				redirect_to = custom_redirect_to

			redirect_url = self.redirect_url if self.get("redirect_url") else 'payment-success'

		else:
			redirect_url = 'payment-failed'

		if redirect_to and redirect_to != "no-redirection":
			redirect_url += '?' + urlencode({'redirect_to': redirect_to})
		if redirect_message:
			redirect_url += '&' + urlencode({'redirect_message': redirect_message})

		return {
			"redirect_to": redirect_url,
			"status": self.integration_request.status
		}

	def change_integration_request_status(self, status, type, error):
		if hasattr(self, "integration_request"):
			self.flags.status_changed_to = status
			self.integration_request.db_set('status', status, update_modified=True)
			self.integration_request.db_set(type, error, update_modified=True)

	def change_linked_integration_requests_status(self, status):
		try:
			linked_docs = frappe.get_all("Integration Request",\
				filters={"reference_doctype": self.reference_document.doctype,\
					"reference_docname": self.reference_document.name})

			for linked_doc in linked_docs:
				frappe.db.set_value("Integration Request", linked_doc.name, "status", status)
		except Exception:
			frappe.log_error(frappe.get_traceback(), _("Integration request status update error"))
