app_name = "cloud_backup"
app_title = "Cloud Backup"
app_publisher = "Sanjay Kumar"
app_description = "Automated backup upload to Cloud Storage for Frappe/ERPNext"
app_email = "sanjay.kumar001@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Runtime wiring: drive-domain registration + governed core patches
# ------------------
before_request = [
	"cloud_backup.services.oauth_service.register_drive_domain",
	"cloud_backup.overrides.patch_manager.apply_all_patches",
]
before_job = [
	"cloud_backup.services.oauth_service.register_drive_domain",
	"cloud_backup.overrides.patch_manager.apply_all_patches",
]
after_migrate = ["cloud_backup.overrides.patch_manager.apply_all_patches"]

# Scheduled Tasks
# ------------------
scheduler_events = {
	"all": [
		"cloud_backup.tasks.auto_upload_fallback",
		"cloud_backup.tasks.run_due_schedules",
	],
}

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "cloud_backup",
# 		"logo": "/assets/cloud_backup/logo.png",
# 		"title": "Cloud Backup",
# 		"route": "/cloud_backup",
# 		"has_permission": "cloud_backup.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/cloud_backup/css/cloud_backup.css"
# app_include_js = "/assets/cloud_backup/js/cloud_backup.js"

# include js, css files in header of web template
# web_include_css = "/assets/cloud_backup/css/cloud_backup.css"
# web_include_js = "/assets/cloud_backup/js/cloud_backup.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "cloud_backup/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "cloud_backup/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "cloud_backup.utils.jinja_methods",
# 	"filters": "cloud_backup.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "cloud_backup.install.before_install"
# after_install = "cloud_backup.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "cloud_backup.uninstall.before_uninstall"
# after_uninstall = "cloud_backup.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "cloud_backup.utils.before_app_install"
# after_app_install = "cloud_backup.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "cloud_backup.utils.before_app_uninstall"
# after_app_uninstall = "cloud_backup.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "cloud_backup.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "cloud_backup.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"cloud_backup.tasks.all"
# 	],
# 	"daily": [
# 		"cloud_backup.tasks.daily"
# 	],
# 	"hourly": [
# 		"cloud_backup.tasks.hourly"
# 	],
# 	"weekly": [
# 		"cloud_backup.tasks.weekly"
# 	],
# 	"monthly": [
# 		"cloud_backup.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "cloud_backup.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "cloud_backup.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "cloud_backup.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "cloud_backup.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["cloud_backup.utils.before_request"]
# after_request = ["cloud_backup.utils.after_request"]

# Job Events
# ----------
# before_job = ["cloud_backup.utils.before_job"]
# after_job = ["cloud_backup.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"cloud_backup.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

