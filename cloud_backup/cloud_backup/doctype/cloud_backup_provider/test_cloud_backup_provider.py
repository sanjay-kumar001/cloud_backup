# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for Cloud Backup Provider."""

import frappe
from frappe.tests.utils import FrappeTestCase

from cloud_backup.tests.utils import make_provider
from cloud_backup.utils.constants import PROVIDER_STORAGE_KIND, StorageKind


class TestCloudBackupProvider(FrappeTestCase):
	def test_storage_kind_map_matches_select(self):
		options = frappe.get_meta("Cloud Backup Provider").get_field("provider_type").options
		self.assertEqual(set(options.split("\n")), set(PROVIDER_STORAGE_KIND))

	def test_section_visibility_bound_to_storage_kind(self):
		meta = frappe.get_meta("Cloud Backup Provider")
		self.assertIn(StorageKind.FOLDER, meta.get_field("sb_destination").depends_on)
		self.assertIn(StorageKind.OBJECT, meta.get_field("sb_s3").depends_on)

	def test_autoname_from_provider_type(self):
		doc = make_provider("dropbox")
		self.assertEqual(doc.name, "Dropbox")

	def test_storage_kind_set_on_validate(self):
		doc = make_provider("amazon_s3", enabled=1, bucket="my-bucket", destination_folder=None)
		self.assertEqual(doc.storage_kind, StorageKind.OBJECT)

	def test_default_authentication_status(self):
		doc = make_provider("google_drive", authentication_status=None, destination_folder=None)
		self.assertEqual(doc.authentication_status, "Not Configured")

	def test_secret_encrypted_at_rest(self):
		doc = make_provider("google_drive", client_secret="s3cr3t-value", destination_folder=None)
		self.assertEqual(doc.get_password("client_secret"), "s3cr3t-value")
		reloaded = frappe.get_doc("Cloud Backup Provider", doc.name)
		self.assertNotEqual(reloaded.client_secret, "s3cr3t-value")

	def test_s3_requires_bucket_when_enabled(self):
		if frappe.db.exists("Cloud Backup Provider", "Amazon S3"):
			frappe.delete_doc("Cloud Backup Provider", "Amazon S3", force=True, ignore_permissions=True)
		doc = frappe.get_doc(
			{"doctype": "Cloud Backup Provider", "provider_type": "amazon_s3", "enabled": 1}
		)
		self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)
