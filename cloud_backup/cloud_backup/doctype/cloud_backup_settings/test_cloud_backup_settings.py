# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for Cloud Backup Settings."""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCloudBackupSettings(FrappeTestCase):
	def test_singleton_loads(self):
		settings = frappe.get_single("Cloud Backup Settings")
		self.assertEqual(settings.doctype, "Cloud Backup Settings")

	def test_negative_retention_rejected(self):
		settings = frappe.get_single("Cloud Backup Settings")
		settings.retention_days = -5
		self.assertRaises(frappe.ValidationError, settings.save, ignore_permissions=True)
