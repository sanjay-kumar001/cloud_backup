# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for Cloud Backup Log."""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestCloudBackupLog(FrappeTestCase):
	def test_timestamp_defaulted(self):
		doc = frappe.get_doc(
			{
				"doctype": "Cloud Backup Log",
				"event": "test_event",
				"level": "INFO",
				"source": "test",
				"message": "hello",
			}
		).insert(ignore_permissions=True)
		self.assertIsNotNone(doc.timestamp)
