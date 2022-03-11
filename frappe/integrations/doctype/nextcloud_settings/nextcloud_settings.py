# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

import os
from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils.data import cint

from .client import NextcloudIntegrationClient


if any((os.getenv('CI'), frappe.conf.developer_mode, frappe.conf.allow_tests)):
	# Do not check certificates when in developer mode or while testing
	os.environ['NEXTCLOUD_DONT_VERIFY_CERTS'] = '1'
	# os.environ['CI_NEXTCLOUD_DISABLE'] = '1'


class NextcloudException(Exception):
	pass

class NextcloudSettings(Document):
	enabled: bool = False
	cloud_url: str = ''
	username: str = ''
	# password: str = ''

	enable_sync: bool = False
	enable_backups: bool = False
	enable_calendar: bool = False

	path_to_files_folder: str = ''
	last_filesync_dt: str = None
	next_filesync_ignore_id_conflicts: bool = False
	filesync_override_conflict_strategy: str = ''
	# TODO: store sync_datetime for each of the 3 modules + configurable interval

	# path_to_upload_folder: ? = None
	# send_email_for_successful_backup: ? = None
	# send_notifications_to: ? = None
	# path_to_backups_folder: ? = None
	# backup_frequency: ? = None

	def _get_credentials(self):
		password = self.get_password(fieldname='password', raise_exception=False)
		username = self.username
		return username, password

	def _get_cloud_url(self):
		return self.cloud_url.strip('/') + '/'

	def nc_connect(self, **kwargs):
		if not self.nc_ping_server():
			raise NextcloudException('nextcloud server is down')

		username, password = self._get_credentials()
		cloud_url = self._get_cloud_url()

		verify_certs = not cint(os.environ.get('NEXTCLOUD_DONT_VERIFY_CERTS', False))
		client = NextcloudIntegrationClient(cloud_url, verify_certs=verify_certs, **kwargs)
		client.login(username, password)

		return client

	def nc_ping_server(self, n_tries = 2, t_timeout = 5):
		from urllib.parse import urlsplit
		o = urlsplit(self._get_cloud_url())
		default_port = {'http': 80, 'https': 443}
		port = o.port or default_port.get(o.scheme, 80)
		host = o.hostname

		import socket
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.settimeout(t_timeout)

		for _ in range(n_tries):
			res = sock.connect_ex((host, port))
			if res == 0:
				return True
		return False

	def get_path_to_files_folder(self):
		return self.path_to_files_folder

	def get_last_filesync_dt(self):
		return frappe.utils.get_datetime(self.last_filesync_dt)

	def set_last_filesync_dt(self, dt_local: datetime):
		self.db_set('last_filesync_dt', dt_local, update_modified=False)
