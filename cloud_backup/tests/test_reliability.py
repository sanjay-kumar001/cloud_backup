# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for secret scrubbing and retention selection/safety."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from cloud_backup.services import log_service, provider_service, retention_service
from cloud_backup.tests.utils import make_provider


class TestScrub(unittest.TestCase):
	def test_secret_keys_redacted(self):
		out = log_service.scrub_secrets(
			{"client_secret": "x", "access_token": "y", "ok": "keep", "n": {"refresh_token": "z"}}
		)
		self.assertEqual(out["client_secret"], "***")
		self.assertEqual(out["access_token"], "***")
		self.assertEqual(out["n"]["refresh_token"], "***")
		self.assertEqual(out["ok"], "keep")

	def test_token_string_masked(self):
		self.assertEqual(log_service.scrub_secrets("t ya29.abcDEF"), "t ***")


class _Settings:
	def __init__(self, **kw):
		self.__dict__.update(kw)


def _stamp(hours_ago: int) -> str:
	return add_to_date(now_datetime(), hours=-hours_ago).strftime("%Y%m%d_%H%M%S")


class TestRetentionSelection(unittest.TestCase):
	def _items(self, n, label="database"):
		# Newest first (i=0) so the oldest are the last generated.
		return [{"id": f"R{i}", "label": label, "stamp": _stamp(i)} for i in range(n)]

	def test_count_keeps_latest(self):
		items = self._items(12)
		sel = retention_service._select_for_deletion(
			items, _Settings(retention_type="Count", retention_count=10, retention_days=0)
		)
		self.assertEqual({r["id"] for r in sel}, {"R10", "R11"})

	def test_count_is_per_artifact_type(self):
		# 6 database + 6 files, keep 5 each -> delete the oldest of each type.
		items = self._items(6, "database") + self._items(6, "files")
		sel = retention_service._select_for_deletion(
			items, _Settings(retention_type="Count", retention_count=5, retention_days=0)
		)
		self.assertEqual(len(sel), 2)
		self.assertEqual({r["label"] for r in sel}, {"database", "files"})

	def test_count_zero_keeps_all(self):
		sel = retention_service._select_for_deletion(
			self._items(5), _Settings(retention_type="Count", retention_count=0, retention_days=0)
		)
		self.assertEqual(sel, [])

	def test_age_deletes_old_only(self):
		items = [
			{"id": "old", "label": "database", "stamp": _stamp(24 * 40)},
			{"id": "new", "label": "database", "stamp": _stamp(24 * 5)},
		]
		sel = retention_service._select_for_deletion(
			items, _Settings(retention_type="Age", retention_days=30, retention_count=0)
		)
		self.assertEqual([r["id"] for r in sel], ["old"])


class _FakeProvider:
	def __init__(self, files, deleted):
		self._files = files
		self._deleted = deleted

	def list_files(self, folder_id=None):
		return self._files

	def delete_file(self, file_id):
		self._deleted.append(file_id)


class TestRetentionSafety(FrappeTestCase):
	def test_reconciles_remote_including_orphans(self):
		provider = make_provider("google_drive", destination_folder="RF")
		# 12 app-named remote files; only the newest two carry a History row.
		remote = [
			{"id": f"RID{i}", "name": f"site_database_{_stamp(i)}.sql.gz", "size": 1} for i in range(12)
		]
		# An unrelated file the app never named must be left untouched.
		remote.append({"id": "KEEP", "name": "user_upload.txt", "size": 1})
		tracked = frappe.get_doc(
			{
				"doctype": "Cloud Backup History",
				"site": frappe.local.site,
				"provider": provider.name,
				"backup_type": "database",
				"local_file": "/tmp/x.sql.gz",
				"local_file_size": 1,
				"status": "Completed",
				"remote_file": "RID11",
			}
		).insert(ignore_permissions=True)

		frappe.db.set_value(
			"Cloud Backup Settings",
			"Cloud Backup Settings",
			{"auto_delete_remote": 1, "retention_type": "Count", "retention_count": 10},
		)
		deleted = []
		self.patch(provider_service, "get_provider", lambda p: _FakeProvider(remote, deleted))
		result = retention_service.run_cleanup(provider=provider.name)
		self.assertEqual(result["deleted"], 2)
		self.assertEqual(set(deleted), {"RID10", "RID11"})
		self.assertNotIn("KEEP", deleted)
		# The deleted file that had a History row is marked; orphans just vanish.
		self.assertEqual(frappe.db.get_value("Cloud Backup History", tracked.name, "remote_deleted"), 1)

	def patch(self, obj, attr, value):
		original = getattr(obj, attr)
		setattr(obj, attr, value)
		self.addCleanup(setattr, obj, attr, original)
