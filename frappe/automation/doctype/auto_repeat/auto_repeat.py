# Copyright (c) 2021, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.contacts.doctype.contact.contact import (
	get_contacts_linked_from,
	get_contacts_linking_to,
)
from frappe.core.doctype.communication.email import make
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	add_months,
	add_years,
	cint,
	cstr,
	get_first_day,
	get_last_day,
	getdate,
	now_datetime,
	nowdate,
	split_emails,
)
from frappe.utils.background_jobs import get_jobs
from frappe.utils.jinja import validate_template
from frappe.utils.user import get_system_managers

month_map = {"Monthly": 1, "Quarterly": 3, "Half-yearly": 6, "Yearly": 12}


class AutoRepeat(Document):
	def validate(self):
		self.update_status()
		self.validate_reference_doctype()
		self.validate_submit_after_creation()
		self.get_reference_title()
		self.validate_dates()
		self.validate_email_id()
		self.update_auto_repeat_id()
		self.set_dates()
		self.unlink_if_applicable()

		validate_template(self.subject or "")
		validate_template(self.message or "")

	def after_save(self):
		frappe.get_doc(self.reference_doctype, self.reference_document).notify_update()

	def on_trash(self):
		frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", "")
		frappe.get_doc(self.reference_doctype, self.reference_document).notify_update()

		for log in frappe.get_all(
			"Auto Repeat Log", filters={"auto_repeat": self.name}, fields=["name", "docstatus"]
		):
			if log.docstatus == 1:
				l = frappe.get_doc("Auto Repeat Log", log.name)
				l.flags.ignore_permissions = True
				l.cancel()

			frappe.delete_doc("Auto Repeat Log", l.name, force=True)

	def set_dates(self):
		doc_before_save = self.get_doc_before_save()
		if self.disabled:
			self.next_schedule_date = None
		elif doc_before_save and self.next_schedule_date:
			self.next_schedule_date = AutoRepeatScheduler(self).get_next_scheduled_date()
		elif not self.next_schedule_date:
			self.next_schedule_date = AutoRepeatScheduler(self).get_next_scheduled_date()

	def auto_repeat_is_pristine(self):
		return len(frappe.get_all(self.reference_doctype, filters={"auto_repeat": self.name})) <= 1

	def unlink_if_applicable(self):
		if self.status == "Completed" or self.disabled:
			for doc in frappe.get_all(self.reference_doctype, filters={"auto_repeat": self.name}):
				frappe.db.set_value(self.reference_doctype, doc.name, "auto_repeat", "")

	def validate_reference_doctype(self):
		if frappe.flags.in_test or frappe.flags.in_patch:
			return
		if not frappe.get_meta(self.reference_doctype).allow_auto_repeat:
			frappe.throw(
				_("Enable Allow Auto Repeat for the doctype {0} in Customize Form").format(
					self.reference_doctype
				)
			)

	def get_reference_title(self):
		title_field = frappe.get_meta(self.reference_doctype).get_title_field() or "name"
		title = frappe.db.get_value(self.reference_doctype, self.reference_document, title_field)
		if self.document_title != title:
			self.document_title = title

	def validate_submit_after_creation(self):
		if self.submit_after_creation and not frappe.get_meta(self.reference_doctype).is_submittable:
			frappe.throw(
				_("Cannot enable {0} for a non-submittable doctype").format(
					frappe.bold(_("Submit on Creation"))
				)
			)

	def validate_dates(self):
		if frappe.flags.in_patch:
			return

		if self.end_date:
			self.validate_from_to_dates("start_date", "end_date")

		if self.end_date == self.start_date:
			frappe.throw(
				_("{0} should not be same as {1}").format(frappe.bold("End Date"), frappe.bold("Start Date"))
			)

	def validate_email_id(self):
		if self.notify_by_email:
			if self.recipients:
				email_list = split_emails(self.recipients.replace("\n", ""))
				from frappe.utils import validate_email_address

				for email in email_list:
					if not validate_email_address(email):
						frappe.throw(_("{0} is an invalid email address in 'Recipients'").format(email))
			else:
				frappe.throw(_("'Recipients' not specified"))

	def update_auto_repeat_id(self):
		# check if document is already on auto repeat
		auto_repeat = frappe.db.get_value(self.reference_doctype, self.reference_document, "auto_repeat")
		if auto_repeat and auto_repeat != self.name and not self.disabled and not frappe.flags.in_patch:
			frappe.throw(
				_("The {0} is already on auto repeat {1}").format(self.reference_document, auto_repeat)
			)
		else:
			frappe.db.set_value(self.reference_doctype, self.reference_document, "auto_repeat", self.name)

	def update_status(self):
		if self.disabled:
			self.status = "Disabled"
		elif self.is_completed():
			self.status = "Completed"
		else:
			self.status = "Active"

	def is_completed(self):
		return self.end_date and getdate(self.end_date) < getdate(nowdate())

	def create_documents(self):
		try:
			new_doc = self.make_new_document()
			self.add_auto_repeat_log(new_doc)
			if self.notify_by_email and self.recipients:
				self.send_notification(new_doc)
		except Exception:
			error_log = self.log_error(_("Auto repeat failed"))

			self.disable_auto_repeat()

			if self.reference_document and not frappe.flags.in_test:
				self.notify_error_to_user(error_log)

	def make_new_document(self):
		reference_doc = frappe.get_doc(self.reference_doctype, self.reference_document)
		new_doc = frappe.copy_doc(reference_doc, ignore_no_copy=False)
		self.update_doc(new_doc, reference_doc)
		new_doc.insert(ignore_permissions=True)

		if self.submit_after_creation and new_doc.meta.is_submittable:
			new_doc.submit()

		return new_doc

	def update_doc(self, new_doc, reference_doc):
		new_doc.docstatus = 0
		if new_doc.meta.get_field("set_posting_time"):
			new_doc.set("set_posting_time", 1)

		if new_doc.meta.get_field("auto_repeat"):
			new_doc.set("auto_repeat", self.name)

		for fieldname in [
			"naming_series",
			"ignore_pricing_rule",
			"posting_time",
			"select_print_heading",
			"user_remark",
			"remarks",
			"owner",
		]:
			if new_doc.meta.get_field(fieldname):
				new_doc.set(fieldname, reference_doc.get(fieldname))

		for data in new_doc.meta.fields:
			if data.fieldtype == "Date" and data.reqd:
				new_doc.set(data.fieldname, self.next_schedule_date)

		self.set_auto_repeat_period(new_doc)

		auto_repeat_doc = frappe.get_doc("Auto Repeat", self.name)

		# for any action that needs to take place after the recurring document creation
		# on recurring method of that doctype is triggered
		new_doc.run_method("on_recurring", reference_doc=reference_doc, auto_repeat_doc=auto_repeat_doc)

	def set_auto_repeat_period(self, new_doc):
		mcount = month_map.get(self.frequency)
		if mcount and new_doc.meta.get_field("from_date") and new_doc.meta.get_field("to_date"):
			last_ref_doc = frappe.get_all(
				doctype=self.reference_doctype,
				fields=["name", "from_date", "to_date"],
				filters=[
					["auto_repeat", "=", self.name],
					["docstatus", "<", 2],
				],
				order_by="creation desc",
				limit=1,
			)

			if not last_ref_doc:
				return

			from_date = AutoRepeatScheduler(self, last_ref_doc[0].from_date).get_next_scheduled_date()

			if (cstr(get_first_day(last_ref_doc[0].from_date)) == cstr(last_ref_doc[0].from_date)) and (
				cstr(get_last_day(last_ref_doc[0].to_date)) == cstr(last_ref_doc[0].to_date)
			):
				to_date = get_last_day(from_date)
			else:
				to_date = add_days(AutoRepeatScheduler(self, from_date).get_next_date(from_date), -1)

			new_doc.set("from_date", from_date)
			new_doc.set("to_date", to_date)

	def send_notification(self, new_doc):
		"""Notify concerned people about recurring document generation"""
		subject = self.subject or ""
		message = self.message or ""

		if not self.subject:
			subject = _("New {0}: {1}").format(new_doc.doctype, new_doc.name)
		elif "{" in self.subject:
			subject = frappe.render_template(self.subject, {"doc": new_doc})

		print_format = self.print_format or "Standard"
		error_string = None

		try:
			attachments = [
				frappe.attach_print(
					new_doc.doctype, new_doc.name, file_name=new_doc.name, print_format=print_format
				)
			]

		except frappe.PermissionError:
			error_string = _("A recurring {0} {1} has been created for you via Auto Repeat {2}.").format(
				new_doc.doctype, new_doc.name, self.name
			)
			error_string += "<br><br>"

			error_string += _(
				"{0}: Failed to attach new recurring document. To enable attaching document in the auto repeat notification email, enable {1} in Print Settings"
			).format(frappe.bold(_("Note")), frappe.bold(_("Allow Print for Draft")))
			attachments = "[]"

		if error_string:
			message = error_string
		elif not self.message:
			message = _("Please find attached {0}: {1}").format(new_doc.doctype, new_doc.name)
		elif "{" in self.message:
			message = frappe.render_template(self.message, {"doc": new_doc})

		make(
			doctype=new_doc.doctype,
			name=new_doc.name,
			recipients=self.recipients,
			subject=subject,
			content=message,
			attachments=attachments,
			send_email=1,
		)

	@frappe.whitelist()
	def fetch_linked_contacts(self):
		if self.reference_doctype and self.reference_document:
			res = get_contacts_linking_to(
				self.reference_doctype, self.reference_document, fields=["email_id"]
			)
			res += get_contacts_linked_from(
				self.reference_doctype, self.reference_document, fields=["email_id"]
			)

			email_ids = {d.email_id for d in res}
			if not email_ids:
				frappe.msgprint(_("No contacts linked to document"), alert=True)
			else:
				self.recipients = ", ".join(email_ids)

	def disable_auto_repeat(self):
		frappe.db.set_value("Auto Repeat", self.name, "disabled", 1)

	def notify_error_to_user(self, error_log):
		recipients = list(get_system_managers(only_name=True))
		recipients.append(self.owner)
		subject = _("Auto Repeat Document Creation Failed")

		form_link = frappe.utils.get_link_to_form(self.reference_doctype, self.reference_document)
		auto_repeat_failed_for = _("Auto Repeat failed for {0}").format(form_link)

		error_log_link = frappe.utils.get_link_to_form("Error Log", error_log.name)
		error_log_message = _("Check the Error Log for more information: {0}").format(error_log_link)

		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			template="auto_repeat_fail",
			args={
				"auto_repeat_failed_for": auto_repeat_failed_for,
				"error_log_message": error_log_message,
			},
			header=[subject, "red"],
		)

	@frappe.whitelist()
	def get_auto_repeat_schedule(self):
		schedule = AutoRepeatScheduler(self).get_schedule()

		logs = frappe.get_all(
			"Auto Repeat Log",
			filters={
				"auto_repeat": self.name,
			},
			fields=["transaction_date", "generated_docname", "generated_doctype"],
			order_by="transaction_date DESC",
			limit=10,
		)
		max_log = max(getdate(x.transaction_date) for x in logs) if logs else getdate(nowdate())

		for log in logs:
			if not frappe.db.exists(log.generated_doctype, log.generated_docname):
				log.generated_doctype = "File deleted"

		return sorted(
			[
				dict(
					link=frappe.utils.get_link_to_form(x.generated_doctype, x.generated_docname)
					if x.generated_doctype != "File deleted"
					else _("File deleted"),
					**x
				)
				for x in logs
			]
			+ [dict(transaction_date=x) for x in list(schedule) if getdate(x) > getdate(max_log)][:5],
			key=lambda x: getdate(x["transaction_date"]),
			reverse=True,
		)

	def add_auto_repeat_log(self, doc):
		doc = frappe.get_doc(
			{
				"doctype": "Auto Repeat Log",
				"generation_date": now_datetime(),
				"transaction_date": self.next_schedule_date,
				"generated_doctype": doc.doctype,
				"generated_docname": doc.name,
				"auto_repeat": self.name,
			}
		)
		frappe.flags.ignore_permissions = True
		doc.insert()
		doc.submit()
		frappe.flags.ignore_permissions = False


# called through hooks
@frappe.whitelist()
def make_auto_repeat_entry(auto_repeat=None):
	enqueued_method = "frappe.automation.doctype.auto_repeat.auto_repeat.create_repeated_entries"
	jobs = get_jobs()

	if not jobs or enqueued_method not in jobs[frappe.local.site]:
		data = get_auto_repeat_entries(auto_repeat=auto_repeat)
		frappe.enqueue(enqueued_method, data=data)


def get_auto_repeat_entries(date=None, auto_repeat=None):
	if not date:
		date = getdate(nowdate())
	query_filters = [["next_schedule_date", "<=", date], ["status", "=", "Active"]]

	if auto_repeat:
		query_filters.append(["name", "=", auto_repeat])

	return frappe.get_all(
		"Auto Repeat",
		filters=query_filters,
		fields=["name", "disabled", "next_schedule_date", "start_date"],
	)


def create_repeated_entries(data):
	for d in data:
		doc: AutoRepeat = frappe.get_doc("Auto Repeat", d.name)

		disabled = doc.disabled
		current_date = getdate(nowdate())
		schedule_date = getdate(doc.next_schedule_date)

		while schedule_date and schedule_date <= current_date and not disabled:
			doc: AutoRepeat = frappe.get_doc("Auto Repeat", d.name)
			doc.create_documents()
			schedule_date = AutoRepeatScheduler(doc, schedule_date).get_next_scheduled_date()
			disabled = frappe.db.get_value("Auto Repeat", doc.name, "disabled")
			if not disabled:
				doc.db_set("next_schedule_date", schedule_date)
			if not schedule_date:
				doc.db_set("disabled", True)
				doc.db_set("status", "Completed")


# called through hooks
def set_auto_repeat_as_completed():
	auto_repeat = frappe.get_all("Auto Repeat", filters={"status": ["!=", "Disabled"]})
	for entry in auto_repeat:
		doc = frappe.get_doc("Auto Repeat", entry.name)
		if doc.is_completed():
			doc.status = "Completed"
			doc.save()


@frappe.whitelist()
def make_auto_repeat(doctype, docname, frequency="Daily", start_date=None, end_date=None):
	if not start_date:
		start_date = getdate(nowdate())
	doc = frappe.new_doc("Auto Repeat")
	doc.reference_doctype = doctype
	doc.reference_document = docname
	doc.frequency = frequency
	doc.start_date = start_date
	if end_date:
		doc.end_date = end_date
	doc.save()
	return doc


# method for reference_doctype filter
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_auto_repeat_doctypes(doctype, txt, searchfield, start, page_len, filters):
	res = frappe.get_all(
		"Property Setter",
		{
			"property": "allow_auto_repeat",
			"value": "1",
		},
		["doc_type"],
	)
	docs = [r.doc_type for r in res]

	res = frappe.get_all(
		"DocType",
		{
			"allow_auto_repeat": 1,
		},
		["name"],
	)
	docs += [r.name for r in res]
	docs = set(list(docs))

	return [[d] for d in docs]


@frappe.whitelist()
def update_reference(docname, reference):
	result = ""
	try:
		frappe.db.set_value("Auto Repeat", docname, "reference_document", reference)
		result = "success"
	except Exception as e:
		result = "error"
		raise e
	return result


@frappe.whitelist()
def generate_message_preview(reference_dt, reference_doc, message=None, subject=None):
	frappe.has_permission("Auto Repeat", "write", throw=True)
	doc = frappe.get_doc(reference_dt, reference_doc)
	subject_preview = _("Please add a subject to your email")
	msg_preview = frappe.render_template(message, {"doc": doc})
	if subject:
		subject_preview = frappe.render_template(subject, {"doc": doc})

	return {"message": msg_preview, "subject": subject_preview}


class AutoRepeatScheduler:
	def __init__(self, auto_repeat, current_date=None):
		self.auto_repeat = auto_repeat
		self.current_date = current_date or nowdate()
		self.frequency_map = {
			"Daily": self.add_day,
			"Weekly": self.add_week,
			"Monthly": self.add_month,
			"Quarterly": self.add_quarter,
			"Half-yearly": self.add_semester,
			"Yearly": self.add_year,
		}

	def get_schedule(self):
		if self.auto_repeat.end_date:
			end_date = getdate(self.auto_repeat.end_date)
		else:
			end_date = add_years(getdate(nowdate()), 2)

		initial_date = getdate(self.auto_repeat.start_date)
		scheduled_date = initial_date
		offset = 0
		while getdate(scheduled_date) <= end_date:
			offset += 1
			scheduled_date = self.get_next_date(initial_date, offset)
			yield scheduled_date

	def get_next_date(self, initial_date, offset: int = 1):
		next_date = self.get_next_date_pure(initial_date, offset)
		if self.auto_repeat.frequency == "Monthly" and self.auto_repeat.repeat_on_last_day:
			return get_last_day(next_date)
		elif (
			self.auto_repeat.frequency in ["Monthly", "Quarterly", "Half-yearly", "Yearly"]
			and cint(self.auto_repeat.repeat_on_day) > 0
		):
			return add_days(
				get_first_day(next_date),
				cint(self.auto_repeat.repeat_on_day) - 1,
			)
		else:
			return next_date

	def get_next_date_pure(self, initial_date, offset: int):
		return self.frequency_map.get(self.auto_repeat.frequency)(initial_date, n=offset)

	def add_day(self, date, n=1):
		return add_days(date, n)

	def add_week(self, date, n=1):
		return add_days(date, 7 * n)

	def add_month(self, date, n=1):
		return add_months(date, n)

	def add_quarter(self, date, n=1):
		return add_months(date, 3 * n)

	def add_semester(self, date, n=1):
		return add_months(date, 6 * n)

	def add_year(self, date, n=1):
		return add_years(date, n)

	def get_already_generated(self):
		return [
			getdate(x.transaction_date)
			for x in frappe.get_all(
				"Auto Repeat Log",
				filters={"auto_repeat": self.auto_repeat.name},
				fields=["transaction_date"],
				order_by="transaction_date DESC",
			)
		]

	def get_next_scheduled_date(self):
		already_generated = self.get_already_generated()
		# Ensure that the next date is neither in the past nor the current date
		min_date = max(getdate(self.current_date), getdate(nowdate()))
		next_dates = (
			getdate(x)
			for x in self.get_schedule()
			if getdate(x) > min_date and getdate(x) not in already_generated
		)
		return min(next_dates, default=None)
