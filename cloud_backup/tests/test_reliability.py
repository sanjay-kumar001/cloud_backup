# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for secret scrubbing and retention selection/safety."""

import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from cloud_backup.services import log_service, provider_service, retention_service


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


class TestRetentionSelection(unittest.TestCase):
	def _rows(self, n):
		return [
			{"name": f"r{i}", "remote_file": f"R{i}", "completed_at": add_to_date(now_datetime(), hours=-i)}
			for i in range(n)
		]

	def test_count_keeps_latest(self):
		sel = retention_service._select_for_deletion(
			self._rows(12), _Settings(retention_type="Count", retention_count=10, retention_days=0)
		)
		self.assertEqual({r["name"] for r in sel}, {"r10", "r11"})

	def test_count_zero_keeps_all(self):
		sel = retention_service._select_for_deletion(
			self._rows(5), _Settings(retention_type="Count", retention_count=0, retention_days=0)
		)
		self.assertEqual(sel, [])

	def test_age_deletes_old_only(self):
		rows = [
			{"name": "old", "remote_file": "o", "completed_at": add_to_date(now_datetime(), days=-40)},
			{"name": "new", "remote_file": "n", "completed_at": add_to_date(now_datetime(), days=-5)},
		]
		sel = retention_service._select_for_deletion(
			rows, _Settings(retention_type="Age", retention_days=30, retention_count=0)
		)
		self.assertEqual([r["name"] for r in sel], ["old"])


class TestRetentionSafety(FrappeTestCase):
	def test_deletes_only_managed_rows(self):
		provider = frappe.get_doc(
			{
				"doctype": "Cloud Backup Provider",
				"provider_name": frappe.generate_hash(length=8),
				"provider_type": "google_drive",
				"destination_folder": "RF",
				"authentication_status": "Authorized",
			}
		).insert(ignore_permissions=True)
		tmp = frappe.get_site_path("private", "backups", "cb_ret.sql.gz")
		with open(tmp, "wb") as f:
			f.write(b"x")
		made = []
		for i in range(12):
			d = frappe.get_doc(
				{
					"doctype": "Cloud Backup History",
					"site": frappe.local.site,
					"provider": provider.name,
					"backup_type": "database",
					"local_file": tmp,
					"local_file_size": 1,
					"status": "Completed",
					"remote_file": f"RID{i}",
				}
			).insert(ignore_permissions=True)
			d.db_set("completed_at", add_to_date(now_datetime(), hours=-i))
			made.append(d.name)

		frappe.db.set_value(
			"Cloud Backup Settings",
			"Cloud Backup Settings",
			{"auto_delete_remote": 1, "retention_type": "Count", "retention_count": 10},
		)
		deleted = []
		self.patch(provider_service, "get_provider", lambda p: type("P", (), {"delete_file": lambda s, f: deleted.append(f)})())
		result = retention_service.run_cleanup()
		self.assertEqual(result["deleted"], 2)
		self.assertEqual(set(deleted), {"RID10", "RID11"})
		self.assertEqual(frappe.db.get_value("Cloud Backup History", made[0], "remote_deleted"), 0)

	def patch(self, obj, attr, value):
		original = getattr(obj, attr)
		setattr(obj, attr, value)
		self.addCleanup(setattr, obj, attr, original)
