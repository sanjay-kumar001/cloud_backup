# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for enqueue_upload and the upload_backup job (Drive mocked)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from cloud_backup.jobs import upload_backup
from cloud_backup.services import backup_service, provider_service
from cloud_backup.tests.utils import make_provider
from cloud_backup.utils.exceptions import NetworkError
from cloud_backup.utils.file_utils import slugify_site


class _FakeProvider:
	def __init__(self, result=None, error=None):
		self._result = result or {"id": "rid", "name": "n", "size": 10, "checksum": "c"}
		self._error = error

	def upload_file(self, local_path, remote_target, remote_name=None):
		if self._error:
			raise self._error
		self.target = remote_target
		self.remote_name = remote_name
		return self._result


class TestUpload(FrappeTestCase):
	def setUp(self):
		self.tmp = frappe.get_site_path("private", "backups", "cb_test.sql.gz")
		with open(self.tmp, "wb") as f:
			f.write(b"x" * 1024)
		self.provider = make_provider("google_drive", destination_folder="folderX")

	def _history(self):
		return frappe.get_doc(
			{
				"doctype": "Cloud Backup History",
				"site": frappe.local.site,
				"provider": self.provider.name,
				"backup_type": "database",
				"local_file": self.tmp,
				"local_file_size": 1024,
				"status": "Queued",
			}
		).insert(ignore_permissions=True)

	def test_enqueue_upload_creates_history(self):
		enqueued = []
		self.patch(frappe, "enqueue", lambda *a, **k: enqueued.append(k))
		self.patch(backup_service, "find_latest_backup", lambda: {"database": self.tmp})
		names = backup_service.enqueue_upload(self.provider.name, "database")
		self.assertEqual(len(names), 1)
		self.assertEqual(frappe.db.get_value("Cloud Backup History", names[0], "status"), "Queued")
		self.assertEqual(enqueued[0]["artifact"], "database")

	def test_job_completes(self):
		fake = _FakeProvider()
		self.patch(provider_service, "get_provider", lambda p: fake)
		h = self._history()
		upload_backup.run(h.name, artifact="database")
		h.reload()
		self.assertEqual(h.status, "Completed")
		self.assertEqual(h.remote_file, "rid")
		self.assertEqual(fake.target, "folderX")
		self.assertTrue(fake.remote_name.startswith(f"{slugify_site(frappe.local.site)}_database_"))

	def test_job_failure_records_error(self):
		self.patch(provider_service, "get_provider", lambda p: _FakeProvider(error=NetworkError("nope")))
		h = self._history()
		with self.assertRaises(NetworkError):
			upload_backup.run(h.name, artifact="database")
		h.reload()
		self.assertEqual(h.status, "Failed")
		self.assertIn("nope", h.error)

	def patch(self, obj, attr, value):
		original = getattr(obj, attr)
		setattr(obj, attr, value)
		self.addCleanup(setattr, obj, attr, original)
