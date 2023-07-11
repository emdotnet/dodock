# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
from datetime import timedelta
from urllib.parse import quote

import arrow
import google.oauth2.credentials
import requests
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

import frappe
from frappe import _
from frappe.integrations.google_oauth import GoogleOAuth
from frappe.model.document import Document
from frappe.utils import (
	convert_utc_to_system_timezone,
	get_datetime,
	get_request_site_address,
	get_system_timezone,
)
from frappe.utils.password import set_encrypted_password

SCOPES = "https://www.googleapis.com/auth/calendar"


class GoogleCalendar(Document):
	def validate(self):
		google_settings = frappe.get_single("Google Settings")
		if not google_settings.enable:
			frappe.throw(_("Enable Google API in Google Settings."))

		if (not google_settings.client_id and not frappe.conf.google_client_id) or (
			not google_settings.client_secret and not frappe.conf.google_client_secret
		):
			frappe.throw(_("Enter Client Id and Client Secret in Google Settings."))

		return google_settings

	def get_access_token(self):
		google_settings = self.validate()

		if not self.refresh_token:
			button_label = frappe.bold(_("Allow Google Calendar Access"))
			raise frappe.ValidationError(_("Click on {0} to generate Refresh Token.").format(button_label))

		data = {
			"client_id": google_settings.client_id or frappe.conf.google_client_id,
			"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False)
			or frappe.conf.google_client_secret,
			"refresh_token": self.refresh_token,
			"grant_type": "refresh_token",
			"scope": SCOPES,
		}

		try:
			r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()
		except requests.exceptions.HTTPError:
			button_label = frappe.bold(_("Allow Google Calendar Access"))
			frappe.throw(
				_(
					"Something went wrong during the token generation. Click on {0} to generate a new one."
				).format(button_label)
			)

		return r.get("access_token")


@frappe.whitelist()
def get_reference_options():
	return [x for x in frappe.get_hooks("gcalendar_integrations")]


@frappe.whitelist()
def authorize_access(g_calendar, reauthorize=None):
	"""
	If no Authorization code get it from Google and then request for Refresh Token.
	Google Calendar Name is set to flags to set_value after Authorization Code is obtained.
	"""
	google_settings = frappe.get_doc("Google Settings")
	google_calendar = frappe.get_doc("Google Calendar", g_calendar)
	google_calendar.check_permission("write")

	redirect_uri = (
		get_request_site_address(True)
		+ "?cmd=frappe.integrations.doctype.google_calendar.google_calendar.google_callback"
	)

	if not google_calendar.authorization_code or reauthorize:
		frappe.cache.hset("google_calendar", "google_calendar", google_calendar.name)
		return get_authentication_url(
			client_id=google_settings.client_id or frappe.conf.google_client_id,
			redirect_uri=redirect_uri,
		)
	else:
		try:
			data = {
				"code": google_calendar.get_password(fieldname="authorization_code", raise_exception=False),
				"client_id": google_settings.client_id or frappe.conf.google_client_id,
				"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False)
				or frappe.conf.google_client_secret,
				"redirect_uri": redirect_uri,
				"grant_type": "authorization_code",
			}
			r = requests.post(GoogleOAuth.OAUTH_URL, data=data).json()

			if "refresh_token" in r:
				frappe.db.set_value(
					"Google Calendar", google_calendar.name, "refresh_token", r.get("refresh_token")
				)
				frappe.db.set_value("Google Calendar", google_calendar.name, "next_sync_token", None)
				frappe.db.commit()

				frappe.local.response["type"] = "redirect"
				frappe.local.response["location"] = "/app/Form/{}/{}".format(
					quote("Google Calendar"), quote(google_calendar.name)
				)

				frappe.msgprint(_("Google Calendar has been configured."))
			else:
				frappe.msgprint(
					_("Google Calendar configuration failed : {0}.").format(r.get("error_description") or str(r))
				)

		except Exception as e:
			frappe.throw(e)


def get_authentication_url(client_id=None, redirect_uri=None):
	return {
		"url": "https://accounts.google.com/o/oauth2/v2/auth?access_type=offline&response_type=code&prompt=consent&client_id={}&include_granted_scopes=true&scope={}&redirect_uri={}".format(
			client_id, SCOPES, redirect_uri
		)
	}


@frappe.whitelist()
def google_callback(code=None):
	"""
	Authorization code is sent to callback as per the API configuration
	"""
	google_calendar = frappe.cache.hget("google_calendar", "google_calendar")
	frappe.db.set_value("Google Calendar", google_calendar, "authorization_code", code)
	frappe.db.commit()

	authorize_access(google_calendar)


def sync_all_calendars():
	google_calendars = frappe.get_list("Google Calendar", filters={"enable": 1})
	for g in google_calendars:
		sync_events_from_google_calendar(g.name)


@frappe.whitelist()
def sync(g_calendar):
	return sync_events_from_google_calendar(g_calendar)


def get_google_calendar_object(g_calendar):
	"""
	Returns an object of Google Calendar along with Google Calendar doc.
	"""
	google_settings = frappe.get_doc("Google Settings")
	account = frappe.get_doc("Google Calendar", g_calendar)

	credentials_dict = {
		"token": account.get_access_token(),
		"refresh_token": account.refresh_token,
		"token_uri": GoogleOAuth.OAUTH_URL,
		"client_id": google_settings.client_id or frappe.conf.google_client_id,
		"client_secret": google_settings.get_password(fieldname="client_secret", raise_exception=False)
		or frappe.conf.google_client_secret,
		"scopes": "https://www.googleapis.com/auth/calendar/v3",
	}

	credentials = google.oauth2.credentials.Credentials(**credentials_dict)
	google_calendar = build(
		serviceName="calendar", version="v3", credentials=credentials, static_discovery=False
	)

	check_google_calendar(account, google_calendar)

	account.load_from_db()
	return google_calendar, account


def check_google_calendar(account, google_calendar):
	"""
	Checks if Google Calendar is present with the specified name.
	If not, creates one.
	"""
	account.load_from_db()
	try:
		if account.google_calendar_id:
			google_calendar.calendars().get(calendarId=account.google_calendar_id).execute()
		else:
			# If no Calendar ID create a new Calendar
			calendar = {
				"summary": account.calendar_name,
				"timeZone": frappe.db.get_single_value("System Settings", "time_zone"),
			}
			created_calendar = google_calendar.calendars().insert(body=calendar).execute()
			frappe.db.set_value(
				"Google Calendar", account.name, "google_calendar_id", created_calendar.get("id")
			)
			frappe.db.commit()
	except HttpError as err:
		frappe.msgprint(f'{_("Google Error")}: {json.loads(err.content)["error"]["message"]}')
		frappe.throw(
			_("Google Calendar - Could not create Calendar for {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)


def sync_events_from_google_calendar(g_calendar, method=None, page_length=2000):
	"""
	Syncs Events from Google Calendar in Framework Calendar.
	Google Calendar returns nextSyncToken when all the events in Google Calendar are fetched.
	nextSyncToken is returned at the very last page
	https://developers.google.com/calendar/v3/sync
	"""
	google_calendar, account = get_google_calendar_object(g_calendar)

	if not account.pull_from_google_calendar:
		return

	sync_token = account.get_password(fieldname="next_sync_token", raise_exception=False) or None
	events = frappe._dict()
	results = []
	while True:
		try:
			# API Response listed at EOF
			events = (
				google_calendar.events()
				.list(
					calendarId=account.google_calendar_id,
					maxResults=page_length,
					singleEvents=False,
					showDeleted=True,
					syncToken=sync_token,
					pageToken=events.get("nextPageToken"),
				)
				.execute()
			)
		except HttpError as err:
			msg = _("Google Calendar - Could not fetch event from Google Calendar, error code {0}.").format(
				err.resp.status
			)

			if err.resp.status == 410:
				set_encrypted_password("Google Calendar", account.name, "", "next_sync_token")
				frappe.db.commit()
				msg += " " + _("Sync token was invalid and has been resetted, Retry syncing.")
				frappe.msgprint(msg, title="Invalid Sync Token", indicator="blue")
			else:
				frappe.throw(msg)

		for event in events.get("items", []):
			results.append(event)

		if not events.get("nextPageToken"):
			if events.get("nextSyncToken"):
				account.next_sync_token = events.get("nextSyncToken")
				account.save()
			break

	for idx, event in enumerate(results):
		frappe.publish_realtime(
			"import_google_calendar",
			dict(progress=idx + 1, total=len(results)),
			user=frappe.session.user,
		)

		# If Google Calendar Event if confirmed, then create an Event
		if event.get("status") == "confirmed":
			recurrence = None
			if event.get("recurrence"):
				try:
					recurrence = event.get("recurrence")[0]
				except IndexError:
					pass

			if not frappe.db.exists(
				account.reference_document, {"google_calendar_event_id": event.get("id")}
			):
				call_calendar_hook(
					"pull_insert", **{"account": account, "event": event, "recurrence": recurrence}
				)
			elif (get_datetime(event.get("updated")) - get_datetime(event.get("created"))) < timedelta(
				seconds=2
			):
				continue
			else:
				call_calendar_hook(
					"pull_update", **{"account": account, "event": event, "recurrence": recurrence}
				)
		elif event.get("status") == "cancelled":
			call_calendar_hook("pull_delete", **{"account": account, "event": event})
		else:
			pass

	if not results:
		return _("No Google Calendar Event to sync.")
	elif len(results) == 1:
		return _("1 Google Calendar Event synced.")
	else:
		return _("{0} Google Calendar Events synced.").format(len(results))


def call_calendar_hook(hook, **kwargs):
	reference_document = kwargs.get("account", {}).get("reference_document")
	if reference_document:
		hook_method = (
			frappe.get_hooks("gcalendar_integrations").get(reference_document, {}).get(hook, [])[-1]
		)
	)
	calendar_event.save(ignore_permissions=True)


def insert_event_in_google_calendar(doc, method=None):
	"""
	Insert Events in Google Calendar if sync_with_google_calendar is checked.
	"""
	if (
		not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
		or doc.pulled_from_google_calendar
		or not doc.sync_with_google_calendar
	):
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	event = {"summary": doc.subject, "description": doc.description, "google_calendar_event": 1}
	event.update(
		format_date_according_to_google_calendar(
			doc.all_day, get_datetime(doc.starts_on), get_datetime(doc.ends_on) if doc.ends_on else None
		)
	)

	if doc.repeat_on:
		event.update({"recurrence": repeat_on_to_google_calendar_recurrence_rule(doc)})

	event.update({"attendees": get_attendees(doc)})

	conference_data_version = 0

	if doc.add_video_conferencing:
		event.update({"conferenceData": get_conference_data(doc)})
		conference_data_version = 1

	try:
		event = (
			google_calendar.events()
			.insert(
				calendarId=doc.google_calendar_id,
				body=event,
				conferenceDataVersion=conference_data_version,
				sendUpdates="all",
			)
			.execute()
		)

		frappe.db.set_value(
			"Event",
			doc.name,
			{"google_calendar_event_id": event.get("id"), "google_meet_link": event.get("hangoutLink")},
			update_modified=False,
		)

		frappe.msgprint(_("Event Synced with Google Calendar."))
	except HttpError as err:
		frappe.throw(
			_("Google Calendar - Could not insert event in Google Calendar {0}, error code {1}.").format(
				account.name, err.resp.status
			)
		)


def update_event_in_google_calendar(doc, method=None):
	"""
	Updates Events in Google Calendar if any existing event is modified in Frappe Calendar
	"""
	# Workaround to avoid triggering updation when Event is being inserted since
	# creation and modified are same when inserting doc
	if (
		not frappe.db.exists("Google Calendar", {"name": doc.google_calendar})
		or doc.modified == doc.creation
		or not doc.sync_with_google_calendar
	):
		return

	if doc.sync_with_google_calendar and not doc.google_calendar_event_id:
		# If sync_with_google_calendar is checked later, then insert the event rather than updating it.
		insert_event_in_google_calendar(doc)
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = (
			google_calendar.events()
			.get(calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id)
			.execute()
		)

		event["summary"] = doc.subject
		event["description"] = doc.description
		event["recurrence"] = repeat_on_to_google_calendar_recurrence_rule(doc)
		event["status"] = (
			"cancelled" if doc.status == "Cancelled" or doc.status == "Closed" else event.get("status")
		)
		event.update(
			format_date_according_to_google_calendar(
				doc.all_day, get_datetime(doc.starts_on), get_datetime(doc.ends_on) if doc.ends_on else None
			)
		)

		conference_data_version = 0

		if doc.add_video_conferencing:
			event.update({"conferenceData": get_conference_data(doc)})
			conference_data_version = 1
		elif doc.get_doc_before_save().add_video_conferencing or event.get("hangoutLink"):
			# remove google meet from google calendar event, if turning off add_video_conferencing
			event.update({"conferenceData": None})
			conference_data_version = 1

		event.update({"attendees": get_attendees(doc)})

		event = (
			google_calendar.events()
			.update(
				calendarId=doc.google_calendar_id,
				eventId=doc.google_calendar_event_id,
				body=event,
				conferenceDataVersion=conference_data_version,
				sendUpdates="all",
			)
			.execute()
		)

		# if add_video_conferencing enabled or disabled during update, overwrite
		frappe.db.set_value(
			"Event",
			doc.name,
			{"google_meet_link": event.get("hangoutLink")},
			update_modified=False,
		)
		doc.notify_update()

		frappe.msgprint(_("Event Synced with Google Calendar."))
	except HttpError as err:
		frappe.throw(
			_("Google Calendar - Could not update Event {0} in Google Calendar, error code {1}.").format(
				doc.name, err.resp.status
			)
		)


def delete_event_from_google_calendar(doc, method=None):
	"""
	Delete Events from Google Calendar if Frappe Event is deleted.
	"""

	if not frappe.db.exists("Google Calendar", {"name": doc.google_calendar}):
		return

	google_calendar, account = get_google_calendar_object(doc.google_calendar)

	if not account.push_to_google_calendar:
		return

	try:
		event = (
			google_calendar.events()
			.get(calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id)
			.execute()
		)
		event["recurrence"] = None
		event["status"] = "cancelled"

		google_calendar.events().update(
			calendarId=doc.google_calendar_id, eventId=doc.google_calendar_event_id, body=event
		).execute()
	except HttpError as err:
		frappe.msgprint(
			_("Google Calendar - Could not delete Event {0} from Google Calendar, error code {1}.").format(
				doc.name, err.resp.status
			)
		)


def google_calendar_to_repeat_on(start, end, recurrence=None):
	"""
	recurrence is in the form ['RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH']
	has the frequency and then the days on which the event recurs

	Both have been mapped in a dict for easier mapping.
	"""
	repeat_on = {
		"starts_on": (
			get_datetime(start.get("date"))
			if start.get("date")
			else parser.parse(start.get("dateTime"))
			.astimezone(ZoneInfo(get_system_timezone()))
			.replace(tzinfo=None)
		),
		"ends_on": (
			get_datetime(end.get("date"))
			if end.get("date")
			else parser.parse(end.get("dateTime"))
			.astimezone(ZoneInfo(get_system_timezone()))
			.replace(tzinfo=None)
		),
		"all_day": 1 if start.get("date") else 0,
		"repeat_this_event": 1 if recurrence else 0,
		"repeat_on": None,
		"repeat_till": None,
		"sunday": 0,
		"monday": 0,
		"tuesday": 0,
		"wednesday": 0,
		"thursday": 0,
		"friday": 0,
		"saturday": 0,
	}

	# recurrence rule "RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH"
	if recurrence:
		# google_calendar_frequency = RRULE:FREQ=WEEKLY, byday = BYDAY=MO,TU,TH, until = 20191028
		google_calendar_frequency, until, byday = get_recurrence_parameters(recurrence)
		repeat_on["repeat_on"] = google_calendar_frequencies.get(google_calendar_frequency)

		if repeat_on["repeat_on"] == "Daily":
			repeat_on["ends_on"] = None
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None

		if byday and repeat_on["repeat_on"] == "Weekly":
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None
			byday = byday.split("=")[1].split(",")
			for repeat_day in byday:
				repeat_on[google_calendar_days[repeat_day]] = 1

		if byday and repeat_on["repeat_on"] == "Monthly":
			byday = byday.split("=")[1]
			repeat_day_week_number, repeat_day_name = None, None

			for num in ["-2", "-1", "1", "2", "3", "4", "5"]:
				if num in byday:
					repeat_day_week_number = num
					break

			for day in ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]:
				if day in byday:
					repeat_day_name = google_calendar_days.get(day)
					break

			# Only Set starts_on for the event to repeat monthly
			start_date = parse_google_calendar_recurrence_rule(int(repeat_day_week_number), repeat_day_name)
			repeat_on["starts_on"] = start_date
			repeat_on["ends_on"] = add_to_date(start_date, minutes=5)
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None

		if repeat_on["repeat_till"] == "Yearly":
			repeat_on["ends_on"] = None
			repeat_on["repeat_till"] = datetime.strptime(until, "%Y%m%d") if until else None

	return repeat_on


def format_date_according_to_google_calendar(all_day, starts_on, ends_on=None):
	if not ends_on:
		ends_on = starts_on + timedelta(minutes=10)

	date_format = {
		"start": {
			"dateTime": starts_on.isoformat(),
			"timeZone": get_system_timezone(),
		},
		"end": {
			"dateTime": ends_on.isoformat(),
			"timeZone": get_system_timezone(),
		},
	}

	if all_day:
		# If all_day event, Google Calendar takes date as a parameter and not dateTime
		date_format["start"].pop("dateTime")
		date_format["end"].pop("dateTime")

		date_format["start"].update({"date": starts_on.date().isoformat()})
		date_format["end"].update({"date": ends_on.date().isoformat()})

	return date_format


def get_timezone_naive_datetime(gcalendar_date_object):
	iso_date = arrow.get(gcalendar_date_object.get("dateTime"))
	naive = iso_date.to("UTC").naive

	return convert_utc_to_system_timezone(naive).strftime("%Y-%m-%d %H:%M:%S")


"""API Response
	{
		'kind': 'calendar#events',
		'etag': '"etag"',
		'summary': 'Test Calendar',
		'updated': '2019-07-25T06:09:34.681Z',
		'timeZone': 'Asia/Kolkata',
		'accessRole': 'owner',
		'defaultReminders': [],
		'nextSyncToken': 'token',
		'items': [
			{
				'kind': 'calendar#event',
				'etag': '"etag"',
				'id': 'id',
				'status': 'confirmed' or 'cancelled',
				'htmlLink': 'link',
				'created': '2019-07-25T06:08:21.000Z',
				'updated': '2019-07-25T06:09:34.681Z',
				'summary': 'asdf',
				'creator': {
					'email': 'email'
				},
				'organizer': {
					'email': 'email',
					'displayName': 'Test Calendar',
					'self': True
				},
				'start': {
					'dateTime': '2019-07-27T12:00:00+05:30', (if all day event the its 'date' instead of 'dateTime')
					'timeZone': 'Asia/Kolkata'
				},
				'end': {
					'dateTime': '2019-07-27T13:00:00+05:30', (if all day event the its 'date' instead of 'dateTime')
					'timeZone': 'Asia/Kolkata'
				},
				'recurrence': *recurrence,
				'iCalUID': 'uid',
				'sequence': 1,
				'reminders': {
					'useDefault': True
				}
			}
		]
	}
	*recurrence
		- Daily Event: ['RRULE:FREQ=DAILY']
		- Weekly Event: ['RRULE:FREQ=WEEKLY;BYDAY=MO,TU,TH']
		- Monthly Event: ['RRULE:FREQ=MONTHLY;BYDAY=4TH']
			- BYDAY: -2, -1, 1, 2, 3, 4 with weekdays (-2 edge case for April 2017 had 6 weeks in a month)
		- Yearly Event: ['RRULE:FREQ=YEARLY;']
		- Custom Event: ['RRULE:FREQ=WEEKLY;WKST=SU;UNTIL=20191028;BYDAY=MO,WE']"""
