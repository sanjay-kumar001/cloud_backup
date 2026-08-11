# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for provider_service token-refresh orchestration and oauth wiring."""

import frappe
from frappe.integrations import google_oauth as _google_oauth
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from cloud_backup.providers.google_drive import (
	DRIVE_CALLBACK_METHOD,
	DRIVE_DOMAIN,
	DRIVE_SCOPE,
	DRIVE_SERVICE_VERSION,
)
from cloud_backup.services import oauth_service, provider_service


class TestProviderService(FrappeTestCase):
	def test_register_drive_domain(self):
		oauth_service.register_drive_domain()
		self.assertEqual(_google_oauth._DOMAIN_CALLBACK_METHODS[DRIVE_DOMAIN], DRIVE_CALLBACK_METHOD)
		self.assertEqual(_google_oauth._SERVICES[DRIVE_DOMAIN], DRIVE_SERVICE_VERSION)
		self.assertEqual(_google_oauth._SCOPES[DRIVE_DOMAIN], DRIVE_SCOPE)
		self.assertTrue(DRIVE_SCOPE.endswith("drive.file"))

	def _make_provider(self, expiry):
		return frappe.get_doc(
			{
				"doctype": "Cloud Backup Provider",
				"provider_name": frappe.generate_hash(length=8),
				"provider_type": "google_drive",
				"access_token": "old-access",
				"refresh_token": "refresh-1",
				"token_expiry": expiry,
				"authentication_status": "Authorized",
			}
		).insert(ignore_permissions=True)

	def test_refresh_triggered_when_expired(self):
		doc = self._make_provider(add_to_date(now_datetime(), hours=-1))
		calls = []
		original = oauth_service.refresh_token
		oauth_service.refresh_token = lambda d: calls.append(d.name)
		try:
			provider_service._ensure_valid_token(doc)
		finally:
			oauth_service.refresh_token = original
		self.assertEqual(calls, [doc.name])

	def test_refresh_skipped_when_valid(self):
		doc = self._make_provider(add_to_date(now_datetime(), hours=1))
		calls = []
		original = oauth_service.refresh_token
		oauth_service.refresh_token = lambda d: calls.append(d.name)
		try:
			provider_service._ensure_valid_token(doc)
		finally:
			oauth_service.refresh_token = original
		self.assertEqual(calls, [])

	def test_refresh_failure_marks_expired(self):
		doc = self._make_provider(add_to_date(now_datetime(), hours=-1))

		def boom(_refresh):
			raise _google_oauth.GoogleAuthenticationError("bad")

		original = oauth_service.get_drive_oauth
		oauth_service.get_drive_oauth = lambda: type("O", (), {"refresh_access_token": staticmethod(boom)})()
		try:
			with self.assertRaises(Exception):
				oauth_service.refresh_token(doc)
		finally:
			oauth_service.get_drive_oauth = original
		self.assertEqual(
			frappe.db.get_value("Cloud Backup Provider", doc.name, "authentication_status"),
			"Expired",
		)
