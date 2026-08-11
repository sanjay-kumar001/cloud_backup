__version__ = "0.0.1"


def _apply_runtime_patches():
	"""Apply governed core patches at import time (all-process coverage)."""
	try:
		from cloud_backup.overrides.patch_manager import apply_all_patches

		apply_all_patches()
	except Exception:
		pass


_apply_runtime_patches()
