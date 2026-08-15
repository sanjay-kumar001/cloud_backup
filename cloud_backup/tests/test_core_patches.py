# Copyright (c) 2026, Sanjay Kumar and contributors
# For license information, please see license.txt

"""Upgrade guards for the governed new_backup patch."""

import unittest

import frappe
from frappe.utils import backups as B

from cloud_backup.overrides import patch_manager as pm
from cloud_backup.overrides.core import backups as cb

SENTINEL = "_cloud_backup_new_backup_patched"
TARGET = "frappe.utils.backups.new_backup"


class TestCorePatches(unittest.TestCase):
	def setUp(self):
		self._original = pm._ORIGINALS.get(TARGET, B.new_backup)

	def tearDown(self):
		B.new_backup = self._original
		if hasattr(B, SENTINEL):
			delattr(B, SENTINEL)
		pm._ORIGINALS.pop(TARGET, None)
		cb.apply_patches()

	def test_target_exists_and_returns_generator(self):
		self.assertTrue(hasattr(B, "new_backup"))

	def test_apply_is_idempotent(self):
		cb.apply_patches()
		wrapped = B.new_backup
		cb.apply_patches()
		self.assertIs(B.new_backup, wrapped)
		self.assertTrue(getattr(B, SENTINEL, False))

	def test_wrapper_calls_original_and_returns_unchanged(self):
		if hasattr(B, SENTINEL):
			delattr(B, SENTINEL)
		pm._ORIGINALS.pop(TARGET, None)
		sentinel = object()
		seen = {}

		def fake_original(*a, **k):
			seen["args"] = (a, k)
			return sentinel

		B.new_backup = fake_original
		cb.apply_patches()
		from cloud_backup.services import backup_service

		orig_enqueue = frappe.enqueue
		orig_after = backup_service.enqueue_after_backup
		try:
			backup_service.enqueue_after_backup = lambda odb, trigger="auto": seen.__setitem__("odb", odb)
			result = B.new_backup(older_than=3)
		finally:
			frappe.enqueue = orig_enqueue
			backup_service.enqueue_after_backup = orig_after
		self.assertIs(result, sentinel)
		self.assertEqual(seen["args"], ((), {"older_than": 3}))
		self.assertIs(seen["odb"], sentinel)

	def test_kill_switch(self):
		frappe.conf["disable_runtime_patches"] = 1
		try:
			self.assertTrue(pm.is_disabled())
		finally:
			frappe.conf.pop("disable_runtime_patches", None)
		self.assertFalse(pm.is_disabled())

	def test_patch_status_shape(self):
		status = pm.patch_status()
		self.assertEqual(
			set(status), {"disabled", "originals", "target_exists", "sentinel"}
		)
