# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import msgprint, _
from frappe.utils.verified_command import get_signed_params, verify_request
from frappe.utils import get_url, now_datetime, cint

class EmailLimitCrossedError(frappe.ValidationError): pass

def get_emails_sent_this_month():
	return frappe.db.sql("""
		SELECT COUNT(*) FROM `tabEmail Queue`
		WHERE `status`='Sent' AND EXTRACT(YEAR_MONTH FROM `creation`) = EXTRACT(YEAR_MONTH FROM NOW())
	""")[0][0]

def get_emails_sent_today():
	return frappe.db.sql("""SELECT COUNT(`name`) FROM `tabEmail Queue` WHERE
		`status` in ('Sent', 'Not Sent', 'Sending') AND `creation` > (NOW() - INTERVAL '24' HOUR)""")[0][0]

def get_unsubscribe_message(unsubscribe_message, expose_recipients):
	if unsubscribe_message:
		unsubscribe_html = '''<a href="<!--unsubscribe url-->"
			target="_blank">{0}</a>'''.format(unsubscribe_message)
	else:
		unsubscribe_link = '''<a href="<!--unsubscribe url-->"
			target="_blank">{0}</a>'''.format(_('Unsubscribe'))
		unsubscribe_html = _("{0} to stop receiving emails of this type").format(unsubscribe_link)

	html = """<div class="email-unsubscribe">
			<!--cc message-->
			<div>
				{0}
			</div>
		</div>""".format(unsubscribe_html)

	if expose_recipients == "footer":
		text = "\n<!--cc message-->"
	else:
		text = ""
	text += "\n\n{unsubscribe_message}: <!--unsubscribe url-->\n".format(unsubscribe_message=unsubscribe_message)

	return frappe._dict({
		"html": html,
		"text": text
	})

def get_unsubcribed_url(reference_doctype, reference_name, email, unsubscribe_method, unsubscribe_params):
	params = {"email": email.encode("utf-8"),
		"doctype": reference_doctype.encode("utf-8"),
		"name": reference_name.encode("utf-8")}
	if unsubscribe_params:
		params.update(unsubscribe_params)

	query_string = get_signed_params(params)

	# for test
	frappe.local.flags.signed_query_string = query_string

	return get_url(unsubscribe_method + "?" + get_signed_params(params))

@frappe.whitelist(allow_guest=True)
def unsubscribe(doctype, name, email):
	# unsubsribe from comments and communications
	if not verify_request():
		return

	try:
		frappe.get_doc({
			"doctype": "Email Unsubscribe",
			"email": email,
			"reference_doctype": doctype,
			"reference_name": name
		}).insert(ignore_permissions=True)

	except frappe.DuplicateEntryError:
		frappe.db.rollback()

	else:
		frappe.db.commit()

	return_unsubscribed_page(email, doctype, name)

def return_unsubscribed_page(email, doctype, name):
	frappe.respond_as_web_page(_("Unsubscribed"),
		_("{0} has left the conversation in {1} {2}").format(email, _(doctype), name),
		indicator_color='green')

def flush(from_test=False):
	"""flush email queue, every time: called from scheduler
	"""
	from frappe.email.doctype.email_queue.email_queue import send_mail
	# To avoid running jobs inside unit tests
	if frappe.are_emails_muted():
		msgprint(_("Emails are muted"))
		from_test = True

	if cint(frappe.defaults.get_defaults().get("hold_queue"))==1:
		return

	for row in get_queue():
		try:
			func = send_mail if from_test else send_mail.enqueue
			is_background_task = not from_test
			func(email_queue_name = row.name, is_background_task = is_background_task)
		except Exception:
			frappe.log_error()

def get_queue():
	return frappe.db.sql('''select
			name, sender
		from
			`tabEmail Queue`
		where
			(status='Not Sent' or status='Partially Sent') and
			(send_after is null or send_after < %(now)s)
		order
			by priority desc, creation asc
		limit 500''', { 'now': now_datetime() }, as_dict=True)

def clear_outbox(days=None):
	"""Remove low priority older than 31 days in Outbox or configured in Log Settings.
	Note: Used separate query to avoid deadlock
	"""
	if not days:
		days=31

	email_queues = frappe.db.sql_list("""SELECT `name` FROM `tabEmail Queue`
		WHERE `priority`=0 AND `modified` < (NOW() - INTERVAL '{0}' DAY)""".format(days))

	if email_queues:
		frappe.db.sql("""DELETE FROM `tabEmail Queue` WHERE `name` IN ({0})""".format(
			','.join(['%s']*len(email_queues)
		)), tuple(email_queues))

		frappe.db.sql("""DELETE FROM `tabEmail Queue Recipient` WHERE `parent` IN ({0})""".format(
			','.join(['%s']*len(email_queues)
		)), tuple(email_queues))

def set_expiry_for_email_queue():
	''' Mark emails as expire that has not sent for 7 days.
		Called daily via scheduler.
	 '''
	frappe.db.sql("""
		UPDATE `tabEmail Queue`
		SET `status`='Expired'
		WHERE `modified` < (NOW() - INTERVAL '7' DAY)
		AND `status`='Not Sent'
		AND (`send_after` IS NULL OR `send_after` < %(now)s)""", { 'now': now_datetime() })