# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Tests for schedule due-evaluation and per-provider dedupe."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_to_date, now_datetime

from cloud_backup import tasks
from cloud_backup.services import backup_service
from cloud_backup.tests.utils import make_provider, make_schedule


class _Sched:
	def __init__(self, **kw):
		self.__dict__.update(kw)


class _Odb:
	backup_path_files = None
	backup_path_private_files = None

	def __init__(self, db_path):
		self.backup_path_db = db_path


class TestSchedules(FrappeTestCase):
	def test_is_due(self):
		now = now_datetime()
		self.assertTrue(tasks.is_due(_Sched(last_run=None), now))
		self.assertFalse(
			tasks.is_due(_Sched(last_run=now, schedule_type="Daily", frequency=None), now)
		)
		self.assertTrue(
			tasks.is_due(
				_Sched(last_run=add_to_date(now, days=-2), schedule_type="Daily", frequency=None), now
			)
		)
		self.assertTrue(
			tasks.is_due(
				_Sched(last_run=add_to_date(now, hours=-2), schedule_type="Custom", frequency="0 * * * *"),
				now,
			)
		)

	def test_enqueue_for_schedule_and_dedupe(self):
		tmp = frappe.get_site_path("private", "backups", "cb_sched.sql.gz")
		with open(tmp, "wb") as f:
			f.write(b"x" * 128)
		provider = make_provider("google_drive", destination_folder="SF")
		schedule = make_schedule("Daily", provider=provider.name)

		frappe.db.set_value(
			"Cloud Backup Settings",
			"Cloud Backup Settings",
			{"upload_database": 1, "upload_files": 0, "upload_full": 0},
		)
		self.patch(frappe, "enqueue", lambda *a, **k: None)
		names = backup_service.enqueue_for_schedule(schedule, _Odb(tmp))
		self.assertEqual(len(names), 1)
		self.assertEqual(
			frappe.db.get_value("Cloud Backup History", names[0], "provider"), provider.name
		)
		self.assertEqual(backup_service.enqueue_for_schedule(schedule, _Odb(tmp)), [])

	def patch(self, obj, attr, value):
		original = getattr(obj, attr)
		setattr(obj, attr, value)
		self.addCleanup(setattr, obj, attr, original)
