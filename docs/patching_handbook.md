# User Guide for Patching Frappe & ERPNext Core

**Production‑Grade Methodology for Runtime Monkey Patching**  
*For Frappe Architects, ERPNext Architects, Enterprise Solution Designers, Framework Maintainers, and Developers modifying core behaviour*

---

## Index

### Part 1 – Introduction and Decision Framework
- [Chapter 1 – Executive Summary](#chapter-1--executive-summary)
- [Chapter 2 – When Patching Is Necessary](#chapter-2--when-patching-is-necessary)
- [Chapter 3 – The Decision Framework: Override vs. Patch](#chapter-3--the-decision-framework-override-vs-patch)
- [Chapter 4 – The Five Scenarios Analysed](#chapter-4--the-five-scenarios-analysed)

### Part 2 – Understanding Frappe Runtime Architecture
- [Chapter 5 – Frappe Runtime Architecture Overview](#chapter-5--frappe-runtime-architecture-overview)
- [Chapter 6 – Process Types and Execution Contexts](#chapter-6--process-types-and-execution-contexts)
- [Chapter 7 – Why Monkey Patching Exists](#chapter-7--why-monkey-patching-exists)

### Part 3 – Patching Mechanisms and Registration
- [Chapter 8 – Hook Deep Dive](#chapter-8--hook-deep-dive)
- [Chapter 9 – Python Import System and the Role of `__init__.py`](#chapter-9--python-import-system-and-the-role-of-__init__py)
- [Chapter 10 – Frontend JavaScript Patching Mechanisms](#chapter-10--frontend-javascript-patching-mechanisms)
- [Chapter 11 – Backend Python Patching Mechanisms](#chapter-11--backend-python-patching-mechanisms)
- [Chapter 12 – Complete Pros & Cons Analysis](#chapter-12--complete-pros--cons-analysis)
- [Chapter 13 – The Universal Solution: Safe `__init__.py` Patching](#chapter-13--the-universal-solution-safe-__init__py-patching)
- [Chapter 14 – Hybrid Registration Architecture](#chapter-14--hybrid-registration-architecture)

### Part 4 – Enterprise Patch Framework
- [Chapter 15 – Enterprise Patch Manager Architecture](#chapter-15--enterprise-patch-manager-architecture)
- [Chapter 16 – Enterprise Patch Registry Design](#chapter-16--enterprise-patch-registry-design)
- [Chapter 17 – Idempotent Monkey Patching Pattern](#chapter-17--idempotent-monkey-patching-pattern)
- [Chapter 18 – Backend Monkey Patching Framework](#chapter-18--backend-monkey-patching-framework)
- [Chapter 19 – Frontend Monkey Patching Framework](#chapter-19--frontend-monkey-patching-framework)

### Part 5 – Scenario‑Specific Implementations
- [Chapter 20 – Scenario 1: `Dashboard.setup_dashboard_sections()`](#chapter-20--scenario-1-dashboardsetup_dashboard_sections)
- [Chapter 21 – Scenario 2: `QueryReport.prepare_columns()`](#chapter-21--scenario-2-queryreportprepare_columns)
- [Chapter 22 – Scenario 3: Frontend `TaxesAndTotals.calculate_item_values()`](#chapter-22--scenario-3-frontend-taxesandtotalscalculate_item_values)
- [Chapter 23 – Scenario 4: Backend `calculate_item_values()`](#chapter-23--scenario-4-backend-calculate_item_values)
- [Chapter 24 – Scenario 5: `update_outgoing_rate_on_transaction()`](#chapter-24--scenario-5-update_outgoing_rate_on_transaction)

### Part 6 – Complete Sample Codebase and Architecture
- [Chapter 25 – Complete Sample Codebase](#chapter-25--complete-sample-codebase)
- [Chapter 26 – Complete `__init__.py`](#chapter-26--complete-__init__py)
- [Chapter 27 – Complete `runtime_patches.js`](#chapter-27--complete-runtime_patchesjs)
- [Chapter 28 – Complete `hooks.py` Architecture](#chapter-28--complete-hookspy-architecture)
- [Chapter 29 – Complete `patch_manager.py`](#chapter-29--complete-patch_managerpy)
- [Chapter 30 – Complete `patch_registry.py`](#chapter-30--complete-patch_registrypy)

### Part 7 – Testing, Validation, and Observability
- [Chapter 31 – Testing Framework for Runtime Patches](#chapter-31--testing-framework-for-runtime-patches)
- [Chapter 32 – Bench Console Validation](#chapter-32--bench-console-validation)
- [Chapter 33 – Worker Validation](#chapter-33--worker-validation)
- [Chapter 34 – Repost Item Valuation Validation](#chapter-34--repost-item-valuation-validation)
- [Chapter 35 – Verification and Debugging](#chapter-35--verification-and-debugging)
- [Chapter 36 – Observability and Logging](#chapter-36--observability-and-logging)

### Part 8 – Production Deployment and Governance
- [Chapter 37 – Production Deployment Architecture](#chapter-37--production-deployment-architecture)
- [Chapter 38 – Upgrade Governance and Compatibility Testing](#chapter-38--upgrade-governance-and-compatibility-testing)
- [Chapter 39 – Rollback Strategy](#chapter-39--rollback-strategy)
- [Chapter 40 – Security Considerations](#chapter-40--security-considerations)
- [Chapter 41 – Enterprise Governance Model](#chapter-41--enterprise-governance-model)
- [Chapter 42 – Final Architect Recommendations](#chapter-42--final-architect-recommendations)

### Part 9 – Appendices and Reference
- [Appendix A – File Structure Reference](#appendix-a--file-structure-reference)
- [Appendix B – Execution Context Matrix](#appendix-b--execution-context-matrix)
- [Appendix C – Gotchas, Edge Cases & FAQ](#appendix-c--gotchas-edge-cases--faq)
- [Appendix D – Safety, Idempotency & Upgrade Proofing](#appendix-d--safety-idempotency--upgrade-proofing)
- [Appendix E – Documentation Template (patches.txt)](#appendix-e--documentation-template-patchestxt)

---

## Part 1 – Introduction and Decision Framework

### Chapter 1 – Executive Summary

#### Purpose of this Handbook

This handbook is intended for:

- Frappe Architects
- ERPNext Architects
- Enterprise Solution Designers
- Framework Maintainers
- Developers modifying ERPNext core behaviour

The primary objective is to establish a **production‑grade methodology** for patching Frappe and ERPNext core classes, functions, and JavaScript components while **minimising upgrade risk**.

#### Scope

This handbook focuses on runtime patching of:

**Frontend**  
- `frappe.ui.form.Dashboard.prototype.setup_dashboard_sections`  
- `frappe.views.QueryReport.prototype.prepare_columns`  
- `erpnext.taxes_and_totals.prototype.calculate_item_values`

**Backend**  
- `erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals.calculate_item_values`  
- `erpnext.stock.stock_ledger.update_entries_after.update_outgoing_rate_on_transaction`

#### What This Handbook Does NOT Cover

This handbook does **not** focus on:

- `doc_events`
- `override_doctype_class`
- `override_whitelisted_methods`

because those are official extension mechanisms rather than runtime monkey patches.

---

### Chapter 2 – When Patching Is Necessary

Frappe Framework provides a rich set of declarative extension points for most common customisation needs. However, certain scenarios require **monkey patching** — the runtime replacement of a class or function — because the target code:

- Is not a DocType controller, so `override_doctype_class` does not apply.
- Is not a whitelisted method, so `override_whitelisted_methods` does not apply.
- Does not expose a `doc_events` hook because the modification occurs outside the document lifecycle.
- Is a JavaScript class deep in the desk UI where no extension mechanism exists.

> **Monkey patching is a last-resort tool. It must be used only when all declarative mechanisms are exhausted.** 

The five scenarios analysed in this guide are **legitimate patch cases** because they fall outside Frappe's declarative extension system:

| Scenario | Target | Why No Declarative Hook Exists |
|----------|--------|-------------------------------|
| `setup_dashboard_sections()` | Frappe `FormDashboard` | Internal dashboard builder; no event hook for injecting custom sections |
| `prepare_columns()` | Frappe `QueryReport` | Core report rendering pipeline; no `doc_events` or `override` target |
| `calculate_item_values()` (JS) | ERPNext `TaxesAndTotals` | Client-side calculator; no extension point in the frontend mirror logic |
| `calculate_item_values()` (Py) | ERPNext `calculate_taxes_and_totals` | Internal calculation step; no `doc_events` after individual row processing |
| `update_outgoing_rate_on_transaction()` | ERPNext `update_entries_after` | Called during repost cascade which writes via direct SQL, bypassing lifecycle hooks entirely |

---

### Chapter 3 – The Decision Framework: Override vs. Patch

Before implementing any patch, verify that no official override mechanism exists:

```python
# IN YOUR CUSTOM APP'S hooks.py — The Official Extension Points

# 1. Replace an entire DocType controller
override_doctype_class = {
    "Sales Order": "your_app.overrides.sales_order.SalesOrderOverride"
}

# 2. Replace a whitelisted method
override_whitelisted_methods = {
    "frappe.desk.search.search_link": "your_app.overrides.queries.search_link"
}

# 3. React to document lifecycle events
doc_events = {
    "Sales Order": {
        "on_submit": "your_app.events.sales_order.on_submit",
        "validate": "your_app.events.sales_order.validate"
    }
}

# 4. Extend boot info
extend_bootinfo = "your_app.boot.extend_bootinfo"

# 5. Run after migration
after_migrate = "your_app.tasks.after_migrate"
```

Only when none of the above apply — which is the case for all five scenarios — should you proceed with monkey patching.

#### Preferred Extension Order

| Level | Mechanism                         |
|-------|-----------------------------------|
| 1     | `doc_events` (Official Hooks)     |
| 2     | `override_doctype_class`          |
| 3     | `override_whitelisted_methods`    |
| 4     | Runtime Monkey Patching (`Class.method = replacement`) – only when **no official mechanism exists**. |

---

### Chapter 4 – The Five Scenarios Analysed

#### Scenario 1: `setup_dashboard_sections()` in `frappe.ui.form.Dashboard`

**Source file:** `apps/frappe/frappe/public/js/frappe/form/dashboard.js`

```javascript
// Lines 5-8
frappe.ui.form.Dashboard = class FormDashboard {
    constructor(parent, frm) {
        this.parent = parent;
        this.frm = frm;
        this.setup_dashboard_sections();  // Called at construction
    }
    setup_dashboard_sections() {
        this.progress_area = this.make_section({...});
        this.heatmap_area = this.make_section({...});
        this.chart_area = this.make_section({...});
        this.stats_area = this.make_section({...});
        this.links_area = this.make_section({...});
    }
    // ...
}
```

- **Method signature:** `setup_dashboard_sections()` — no arguments, returns `undefined`
- **Called when:** A new form dashboard is instantiated
- **Effect:** Builds the five standard dashboard sections (Progress, Activity/Heatmap, Graph, Stats, Connections)
- **Why patch:** To inject a custom sixth section into every form dashboard, which no declarative API supports

#### Scenario 2: `prepare_columns(columns)` in `frappe.views.QueryReport`

**Source file:** `apps/frappe/frappe/public/js/frappe/views/reports/query_report.js`

```javascript
// Lines 12-13
frappe.views.QueryReport = class QueryReport extends frappe.views.BaseList {
    // ...
    prepare_columns(columns) {
        // Processes column definitions for DataTable rendering
        // Returns the prepared columns array
    }
}
```

- **Method signature:** `prepare_columns(columns)` — receives column definitions, **returns** the prepared array
- **Called when:** A query report initialises or refreshes
- **Why patch:** To globally modify column formatting (e.g., aligning all Currency fields right, adding custom column attributes)
- **Critical:** This method returns a value — the wrapper MUST return it

#### Scenario 3: `calculate_item_values()` in `erpnext.taxes_and_totals` (JavaScript)

**Source file:** `apps/erpnext/erpnext/public/js/controllers/taxes_and_totals.js`

```javascript
// Lines 5-6
erpnext.taxes_and_totals = class TaxesAndTotals extends erpnext.payments {
    // Contains calculate_item_values() - calculates rate * qty per row
}
```

- **Method signature:** `calculate_item_values()` — no arguments, returns `undefined`
- **Called when:** The frontend recalculates totals after any item or tax change
- **Purpose:** Mirror of the server-side item value calculation for immediate UI feedback
- **Why patch:** To inject derived field calculations (e.g., custom_amount_per_kg) without waiting for a server round-trip

#### Scenario 4: `calculate_item_values()` in `class calculate_taxes_and_totals` (Python)

**Source file:** `apps/erpnext/erpnext/controllers/taxes_and_totals.py`

```python
# Lines 16-45
class calculate_taxes_and_totals:
    def __init__(self, doc: Document):
        self.doc = doc
        self.calculate()
    
    def calculate(self, ...):
        self.calculate_item_values()    # called here
        self.validate_item_tax_template()
        # ... proceeds to taxes, totals
```

- **Method signature:** `def calculate_item_values(self)` — no arguments beyond `self`
- **Called when:** Any transaction document validates/calculates totals — typically in `validate` or `on_submit`
- **Why patch:** To perform custom row-level calculations AFTER base values are computed but BEFORE taxes are applied

#### Scenario 5: `update_outgoing_rate_on_transaction(self, sle)` in `class update_entries_after`

**Source file:** `apps/erpnext/erpnext/stock/stock_ledger.py`

```python
# The repost engine calls this method when recalculating outgoing rates
class update_entries_after:
    def update_outgoing_rate_on_transaction(self, sle):
        # Dispatches to voucher-specific rate update methods
        # Writes new valuation rates via frappe.db.set_value / db_update()
```

- **Method signature:** `def update_outgoing_rate_on_transaction(self, sle)` — takes a Stock Ledger Entry dict
- **Called when:** The `repost_item_valuation` background job or a transaction submission triggers re-valuation
- **Critical context:** Writes are performed via direct SQL/db_update, **NOT** document lifecycle → `doc_events` never fire
- **Why patch:** To react to a rate change on ANY voucher type (not just Stock Entry) when the repost engine runs

---

## Part 2 – Understanding Frappe Runtime Architecture

### Chapter 5 – Frappe Runtime Architecture Overview

Most patching failures occur because developers do not understand where code executes.

**High‑Level Architecture**

```
                    ┌──────────────┐
                    │ Browser      │
                    └──────┬───────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │ Gunicorn Worker  │
                  └──────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
 ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
 │ RQ Worker    │  │ Scheduler    │  │ SocketIO     │
 └──────────────┘  └──────────────┘  └──────────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ MariaDB         │
                  └─────────────────┘
```

---

### Chapter 6 – Process Types and Execution Contexts

#### Process 1 – Web Worker

- **Started by:** `bench start` or `supervisor` or `gunicorn`
- **Purpose:** Desk, Forms, REST APIs, Whitelisted Methods, Reports, Print Formats

**Hook Coverage**

| Hook            | Fires        |
|-----------------|--------------|
| `before_request`| Yes          |
| `before_job`    | No           |
| `boot_session`  | Yes          |
| `after_request` | Yes          |

#### Process 2 – Queue Worker

- **Started by:** `bench worker`
- **Purpose:** `frappe.enqueue()` jobs, e.g. `repost_item_valuation()`, `send_emails()`, long running reports

**Hook Coverage**

| Hook            | Fires        |
|-----------------|--------------|
| `before_request`| No           |
| `before_job`    | Yes          |

#### Process 3 – Scheduler

- **Started by:** `bench schedule`
- **Purpose:** `scheduler_events` execution (hourly, daily, weekly)

> **Important**  
> Scheduler itself does **not** execute jobs – it enqueues them. Workers execute them. Therefore `before_job` still fires.

#### Process 4 – SocketIO

**Purpose:** Realtime Events, Notifications, Presence. Generally irrelevant for ERPNext patching.

#### Process 5 – Bench Console

- **Started by:** `bench --site mysite console`
- **Execution model:** IPython with initialised Frappe context.

**Hook Coverage**

| Hook            | Fires |
|-----------------|-------|
| `before_request`| No    |
| `before_job`    | No    |
| `boot_session`  | No    |

#### Process 6 – Bench Execute

- **Started by:** `bench execute`
- **Example:** `bench execute custom_app.api.test`
- **Execution:** `frappe.init()`, `frappe.connect()`, execute – no request/worker lifecycle.

**Hook Coverage**

| Hook            | Fires |
|-----------------|-------|
| `before_request`| No    |
| `before_job`    | No    |

---

### Chapter 7 – Why Monkey Patching Exists

Frappe provides official extension points – **use them whenever possible**. Monkey patching is only needed when:

- The target code is not part of a DocType controller
- No event hooks are available (e.g., internal class methods)
- The code executes outside the document lifecycle (e.g., stock repost engine)
- Frontend components lack extension APIs

---

## Part 3 – Patching Mechanisms and Registration

### Chapter 8 – Hook Deep Dive

#### `before_request`

- **Location:** `frappe.app.init_request()`
- **Purpose:** Run code before every HTTP request

**Coverage**

| Context   | Works |
|-----------|-------|
| Desk      | Yes   |
| REST API  | Yes   |
| Worker    | No    |
| Console   | No    |
| Execute   | No    |

**Pros:** Explicit, easy to debug, framework‑supported  
**Cons:** Misses console, execute, workers

#### `before_job`

- **Location:** `frappe.utils.background_jobs.execute_job()`
- **Purpose:** Run code before worker job execution

**Coverage**

| Context         | Works |
|-----------------|-------|
| Desk            | No    |
| Worker          | Yes   |
| Scheduler Jobs  | Yes   |
| Console         | No    |
| Execute         | No    |

**Pros:** Covers workers, repost jobs  
**Cons:** Misses console, execute, web requests

#### `boot_session`

- **Location:** `frappe.sessions.get()`
- **Purpose:** Modify Desk boot payload – only Desk, not suitable for patch loading.

#### `after_install` / `after_migrate`

- Run only once during `bench install-app` or `bench migrate` – **not suitable for runtime patching**.

#### `scheduler_events`

Used for scheduled tasks – not suitable for runtime patch registration.

#### `app_include_js`

Frontend equivalent of runtime patch registration.

```python
app_include_js = [
    "/assets/custom_app/js/runtime_patches.js"
]
```

**Coverage:** Every Desk session. Recommended for Dashboard, QueryReport, TaxesAndTotals patches.

#### Hook Coverage Matrix

| Hook             | Web | Worker | Scheduler | Console | Execute |
|------------------|-----|--------|-----------|---------|---------|
| `before_request` | Yes | No     | No        | No      | No      |
| `before_job`     | No  | Yes    | Yes       | No      | No      |
| `boot_session`   | Partial | No | No      | No      | No      |
| `after_install`  | No  | No     | No        | No      | No      |
| `after_migrate`  | No  | No     | No        | No      | No      |
| `app_include_js` | Browser only | N/A | N/A | N/A | N/A |

**Architect Conclusion:** There is no single Frappe hook that covers Web, Worker, Scheduler, Console and Execute simultaneously. Serious runtime patch frameworks eventually combine `before_request` and `before_job` with `custom_app.__init__.py` (or an equivalent startup mechanism).

---

### Chapter 9 – Python Import System and the Role of `__init__.py`

#### 9.1 Understanding Python Package Initialisation

Consider:

```
custom_app/
│
├── __init__.py
├── hooks.py
├── api.py
└── services/
    └── patch_manager.py
```

- `import custom_app` → executes `custom_app/__init__.py`
- `import custom_app.api` → executes `__init__.py` then `api.py`
- `import custom_app.services.patch_manager` → executes `__init__.py` then `services/patch_manager.py`

#### 9.2 Python Import Cache

A module is imported **only once per process**. `custom_app.__init__.py` executes exactly once per process lifetime.

#### 9.3 Why This Matters for Monkey Patching

If `__init__.py` contains:

```python
from custom_app.services.patch_manager import apply_all_patches
apply_all_patches()
```

then the moment any process imports `custom_app`, all patches become active – **no hook registration required**. However, this creates **import‑time side effects**, which are generally discouraged.

#### 9.4 How Frappe Loads Applications

- **Installed Applications:** e.g. `frappe`, `erpnext`, `payments`, `custom_app`
- **Application Discovery:** Frappe reads `sites/apps.txt`.
- **Hook Loading Process:** `frappe.get_hooks()` loads `<app>.hooks` via `importlib.import_module(f"{app}.hooks")`.
- **Hidden Import Chain:** When Frappe imports `custom_app.hooks`, Python **first** imports `custom_app` (executing `__init__.py`), then `hooks.py`. This means `__init__.py` often reaches more execution contexts than developers expect.

#### 9.5 Why `__init__.py` Reaches Console, Execute, Workers, and Scheduler

All the following flows eventually execute `custom_app.__init__` because Frappe loads hooks at startup:

- **Bench Console** → `frappe.init()` → load hooks → import `custom_app`
- **Bench Execute** → `frappe.init()` + `frappe.connect()` → load hooks → import `custom_app`
- **Web Requests** → `init_request()` → `frappe.get_hooks()` → import `custom_app`
- **Queue Workers** → Worker startup → `frappe.get_hooks()` → import `custom_app`
- **Scheduler** → Scheduler startup → load hooks → import `custom_app`

> Many developers think `__init__.py` executes only on explicit `import custom_app`. However, Frappe **indirectly imports** applications while loading hooks.

#### 9.6 Complete Analysis of `__init__.py`

**Advantages**

| Context    | Covered |
|------------|---------|
| Web        | Yes     |
| Worker     | Yes     |
| Scheduler  | Yes     |
| Console    | Yes     |
| Execute    | Yes     |

- **Universal coverage** – its biggest strength
- **Automatic initialisation** – no need for `before_request` / `before_job`
- **Earliest possible registration**

**Disadvantages**

- **Hidden behaviour** – developer may not realise ERPNext behaviour changed during import
- **Harder debugging** – unclear where behaviour changed
- **Build‑time execution** – may execute during `bench build`, `bench migrate`, etc.
- **Test side effects** – unit tests may unintentionally activate patches
- **Upgrade risk** – if patched class structure changes, startup may fail

---

### Chapter 10 – Frontend JavaScript Patching Mechanisms

#### 10.1 The `app_include_js` Hook

For frontend JavaScript patches, Frappe provides the `app_include_js` hook, which injects your script **after** the core Frappe/ERPNext desk bundles have loaded:

```python
# your_app/hooks.py
app_include_js = [
    "/assets/your_app/js/core_overrides.js"
]
```

This mechanism ensures that the target classes you intend to patch already exist on the `window` object (via `frappe` or `erpnext` namespaces). Your script runs **once** at desk load, affecting all subsequent instances.

#### 10.2 JavaScript Patch Pattern (Prototype Method Replacement)

```javascript
// your_app/public/js/core_overrides.js
(function() {
    // 1. Guard: verify target exists
    if (!frappe.ui.form.Dashboard) return;
    
    const proto = frappe.ui.form.Dashboard.prototype;
    
    // 2. Idempotency: skip if already patched
    if (proto._your_app_patched) return;
    
    // 3. Store original
    const original = proto.setup_dashboard_sections;
    
    // 4. Override with wrapper
    proto.setup_dashboard_sections = function() {
        // Call original
        original.apply(this, arguments);
        
        // YOUR CUSTOM CODE HERE
        this.your_custom_section = this.make_section({
            label: __("Custom Section"),
            collapsible: 1
        });
    };
    
    // 5. Set sentinel
    proto._your_app_patched = true;
})();
```

#### 10.3 Critical: Handling Return Values

When patching a method that **returns** a value (like `prepare_columns`), you must explicitly capture and return it:

```javascript
// CORRECT — captures and returns
const original = proto.prepare_columns;
proto.prepare_columns = function(columns) {
    const result = original.call(this, columns);
    // modify result...
    return result;  // ← CRITICAL: must return
};

// INCORRECT — breaks the report
proto.prepare_columns = function(columns) {
    original.call(this, columns);
    // forgot to return — the report will have no columns
};
```

---

### Chapter 11 – Backend Python Patching Mechanisms

#### 11.1 The Two Registration Approaches

Frappe offers two ways to apply backend monkey patches:

| Aspect | `hooks.py` Lifecycle Hooks | `__init__.py` Import-Time |
|--------|---------------------------|--------------------------|
| **Registration** | `before_request = ["app.overrides.apply"]` `before_job = ["app.overrides.apply"]` | `apply_patches()` called at module top-level |
| **When it runs** | Per HTTP request / per background job | First time app package is imported in a process |
| **Coverage** | Web + worker + scheduled jobs | Every Frappe context including `bench console` and `bench execute` |
| **Self-healing** | Yes — rechecked every time | No — one shot |
| **Side effects** | None during build/migrate | Runs during `bench migrate`, `bench build`, tooling |

#### 11.2 The Safe Production Pattern (Centralised Override Loader)

Monkey patches **must not** be applied directly in `hooks.py` — this causes Redis serialisation errors, bench command failures, and cache rebuild instability.

The correct pattern uses three files:

```
your_app/
├── __init__.py           ← guarded loader
├── core_overrides.py     ← central patch dispatcher
└── overrides/
    └── taxes_and_totals.py   ← custom logic
```

#### 11.3 The Central Override Dispatcher

```python
# your_app/core_overrides.py
import frappe

def apply():
    """Apply all monkey patches — idempotent, safe to call many times."""
    frappe.logger("your_app").info("Applying core overrides")
    
    # Import and call each patch module's apply function
    from your_app.overrides.taxes_and_totals import apply as apply_taxes_patch
    from your_app.overrides.stock_ledger import apply as apply_stock_patch
    
    apply_taxes_patch()
    apply_stock_patch()
    
    frappe.logger("your_app").info("Core overrides applied")
```

#### 11.4 Individual Patch Module Pattern

```python
# your_app/overrides/taxes_and_totals.py
import frappe

_PATCH_APPLIED = "_your_app_patched_calc_item_values"

def apply():
    """Apply the calculate_item_values patch — idempotent."""
    from erpnext.controllers import taxes_and_totals as module
    
    cls = module.calculate_taxes_and_totals
    if getattr(cls, _PATCH_APPLIED, False):
        return
    
    original = cls.calculate_item_values
    
    def patched(self):
        # Call original ERPNext logic
        original(self)
        
        # CUSTOM CODE — post-calculation
        self.doc.custom_calculated = True
    
    cls.calculate_item_values = patched
    setattr(cls, _PATCH_APPLIED, True)
    frappe.logger("your_app").debug("calculate_item_values patched")
```

---

### Chapter 12 – Complete Pros & Cons Analysis

#### 12.1 `__init__.py` Import-Time Side Effect

| Aspect | Assessment |
|--------|------------|
| **Coverage** | ✅ **Universal** — web, worker, scheduler, `bench console`, `bench execute`, `bench migrate`, every Frappe process |
| **Self-Healing** | ❌ One-shot — if the patch fails the first time (e.g., target module not yet imported), the process stays unpatched |
| **Discoverability** | ❌ Hidden — no visibility in `hooks.py`; maintainers must know to look in `__init__.py` |
| **Context Safety** | ⚠️ Runs in build/migrate/tooling — patched in contexts where it may be unintended or cause errors |
| **Testing** | ❌ Affects every import of the app, including test runs |
| **Complexity** | ⚠️ Requires `frappe.local.site` guard and exception swallowing |

**When to use:** Only when you specifically need `bench console` / `bench execute` to have the patch applied automatically without manual invocation — typically during data migration scripts or interactive debugging.

#### 12.2 `hooks.py` Lifecycle Hooks

| Aspect | Assessment |
|--------|------------|
| **Coverage** | ✅ Web + worker + scheduled jobs (via `before_request` + `before_job`) |
| **Missing Coverage** | ❌ `bench console`, `bench execute` — these do NOT trigger lifecycle hooks |
| **Self-Healing** | ✅ Re-checked on every request/job; if a patch fails once, the next attempt applies it |
| **Discoverability** | ✅ Explicit — visible in `hooks.py`; the framework-recommended approach |
| **Context Safety** | ✅ Does NOT run during `bench migrate`, `bench build`, or app discovery |
| **Testing** | ✅ Does not interfere with test suite imports |
| **Complexity** | ✅ Simple — no guard needed (Frappe only runs hooks when a site is loaded) |

**When to use:** **Production default.** This is the safer, more maintainable, and explicitly declared approach.

#### 12.3 Frontend `app_include_js`

| Aspect | Assessment |
|--------|------------|
| **Coverage** | ✅ Every desk page load (all forms, reports, lists) |
| **Self-Healing** | ✅ Reloaded on page refresh; no persistent state issues |
| **Discoverability** | ✅ Declared in `hooks.py` |
| **Build Requirement** | ⚠️ Requires `bench build` after changes (or `bench clear-cache` in dev) |
| **Load Order** | ⚠️ Must ensure script loads AFTER target framework code (automatic but dependent on app install order) |

---

### Chapter 13 – The Universal Solution: Safe `__init__.py` Patching

To make your patch work in **all Frappe execution contexts** — including `bench console`, `bench execute`, and `frappe.enqueue(..., now=True)` — you must move beyond the `before_request` + `before_job` lifecycle hooks. Those hooks only cover HTTP requests and regular background jobs (enqueued with `now=False`). They do **not** cover:

- Interactive `bench console` sessions  
- One‑off `bench execute` scripts  
- Inline (synchronous) jobs enqueued with `now=True`  
- The Frappe test runner (`bench run-tests`)  

The only mechanism that **natively** reaches every Frappe process is the **import‑time side effect** placed in your app’s `__init__.py`. This file runs the first time your app package is imported in any process — and Frappe **always** imports every installed app’s `hooks` module during process initialisation (via `frappe.get_hooks()`). That import triggers your `__init__.py` before any request, job, console command, or script executes.

#### 13.1 Safe `__init__.py` Pattern

Use the following pattern to apply your patches **everywhere** without breaking `bench migrate`, `bench build`, or other CLI tools.

```python
# your_app/__init__.py
from __future__ import unicode_literals

__version__ = "0.0.1"

# --------------------------------------------------------------------------
# SAFE UNIVERSAL PATCH APPLIER
# --------------------------------------------------------------------------
def _apply_patches():
    """Apply all monkey patches – idempotent, safe to call multiple times."""
    try:
        import frappe
        # Only apply when we have a live site connection
        if not getattr(frappe, "local", None) or not getattr(frappe.local, "site", None):
            return
    except ImportError:
        return

    try:
        from your_app.core_overrides import apply
        apply()
    except Exception as e:
        # Log but never crash app discovery or bench commands
        import sys
        if "bench" not in sys.argv and "migrate" not in sys.argv:
            print(f"Warning: Could not apply patches: {e}")

# Actually call the patcher – this runs the first time your_app is imported
_apply_patches()
```

#### 13.2 Why this works in every context

| Context | When does `__init__.py` run? |
|---------|------------------------------|
| Web request (`gunicorn`) | Frappe imports all apps’ hooks before handling the request. |
| Background job (RQ worker) | `execute_job()` calls `frappe.get_hooks()`, which imports every app’s `hooks` module → triggers `__init__.py`. |
| `frappe.enqueue(..., now=True)` | The job runs inline in the calling process. If the app was already imported, the patch is already applied. If not, the import happens. |
| `bench console` | Frappe loads the site and imports all app hooks when you enter the console. |
| `bench execute some_method` | Same as console – hooks are loaded before your script runs. |
| `bench migrate` / `bench build` | Frappe still imports app hooks (to read `hooks.py`). Our guard (`frappe.local.site`) prevents patching during these metadata operations, because no site is connected yet. |

#### 13.3 Addressing the Cons of `__init__.py` Patching

| Original Con | Mitigation |
|--------------|-------------|
| **Import‑time side effect (anti‑pattern)** | Add a comment in `__init__.py` and `hooks.py` that explains the patch is applied universally for robustness. Keep the `core_overrides.apply()` function idempotent. |
| **Runs in unwanted contexts (build/migrate)** | The `frappe.local.site` guard prevents execution during CLI commands that have no site. |
| **No retry / not self‑healing** | The patcher is called only once per process. If it fails (e.g., target class not yet loaded), the process stays unpatched. **Mitigation:** In `core_overrides.apply()`, wrap each patch in its own try/except and log errors. For truly critical patches, you can also keep the `before_request` hooks as a fallback (see hybrid approach below). |
| **Hidden / implicit** | Document the patching strategy in your `README.md` and `patches.txt`. Also add a note in `hooks.py` that points to `__init__.py`. |

---

### Chapter 14 – Hybrid Registration Architecture

If you want the **self‑healing** property of `before_request`/`before_job` **plus** universal coverage, you can use both mechanisms together:

```python
# your_app/__init__.py
_apply_patches()   # covers console, execute, now=True

# your_app/hooks.py
from your_app import _apply_patches as apply
before_request = [apply]
before_job = [apply]
```

Because the patch is idempotent (the sentinel prevents re‑patching), the extra calls in web/worker contexts are cheap and harmless.

#### Why Hybrid Registration Is Best

| Context          | `before_request` | `before_job` | `__init__.py` |
|------------------|------------------|--------------|---------------|
| Web              | Yes              | No           | Yes           |
| API              | Yes              | No           | Yes           |
| Worker           | No               | Yes          | Yes           |
| Scheduler        | No               | Yes          | Yes           |
| Console          | No               | No           | Yes           |
| Execute          | No               | No           | Yes           |
| `enqueue(now=True)` | No            | No           | Yes           |
| Docker restart   | Depends          | Depends      | Yes           |
| Kubernetes pod restart | Depends    | Depends      | Yes           |

**Result:** 100% runtime coverage, self‑healing registration, console and worker support.

---

## Part 4 – Enterprise Patch Framework

### Chapter 15 – Enterprise Patch Manager Architecture

#### 15.1 Design Goals

- Centralised Registration
- Idempotency
- Upgrade Safety
- Logging
- Testing Support

#### 15.2 Recommended Folder Structure

```
custom_app/
│
├── __init__.py
├── hooks.py
│
├── services/
│   ├── patch_manager.py
│   └── patch_registry.py
│
├── overrides/
│   ├── backend/
│   │   ├── stock_ledger.py
│   │   ├── taxes_and_totals.py
│   │   └── reports.py
│   └── frontend/
│
├── public/
│   └── js/
│       └── runtime_patches.js
│
└── tests/
    └── test_patches.py
```

#### 15.3 Patch Manager

```python
# custom_app/services/patch_manager.py

_PATCHED = False

def apply_all_patches():
    global _PATCHED
    if _PATCHED:
        return

    from custom_app.overrides.backend.stock_ledger import patch_stock_ledger
    from custom_app.overrides.backend.taxes_and_totals import patch_taxes_and_totals

    patch_stock_ledger()
    patch_taxes_and_totals()

    _PATCHED = True
```

#### 15.4 Why Idempotency Is Mandatory

Without `if _PATCHED: return`, multiple executions can cause double wrapping, recursive calls, memory growth, and unexpected behaviour.

#### 15.5 Class‑Level Sentinel Pattern

```python
def patch_stock_ledger():
    from erpnext.stock import stock_ledger
    cls = stock_ledger.update_entries_after

    if getattr(cls, "_custom_app_patched", False):
        return

    original = cls.update_outgoing_rate_on_transaction

    def patched(self, sle):
        original(self, sle)
        # custom logic

    cls.update_outgoing_rate_on_transaction = patched
    cls._custom_app_patched = True
```

This is the **safest monkey‑patching pattern** in Frappe/ERPNext.

---

### Chapter 16 – Enterprise Patch Registry Design

#### 16.1 Why a Patch Registry Is Required

A central registry avoids scattered patches and makes maintenance, testing, and upgrades manageable.

#### 16.2 Enterprise Architecture

```
custom_app/
├── services/
│   ├── patch_manager.py
│   └── patch_registry.py
├── overrides/
│   ├── backend/
│   │   ├── stock_ledger.py
│   │   ├── taxes_and_totals.py
│   │   └── reports.py
│   └── frontend/
└── public/js/
```

#### 16.3 Patch Registry

```python
# patch_registry.py

PATCH_REGISTRY = [
    "custom_app.overrides.backend.stock_ledger.patch",
    "custom_app.overrides.backend.taxes_and_totals.patch",
    "custom_app.overrides.backend.reports.patch",
]
```

#### 16.4 Patch Manager with Registry

```python
# patch_manager.py

from importlib import import_module

_PATCHED = False

def apply_all_patches():
    global _PATCHED
    if _PATCHED:
        return

    from custom_app.services.patch_registry import PATCH_REGISTRY

    for patch_path in PATCH_REGISTRY:
        module_path, function_name = patch_path.rsplit(".", 1)
        module = import_module(module_path)
        getattr(module, function_name)()

    _PATCHED = True
```

#### 16.5 Advantages

- **Centralised** – all runtime patches registered in one place
- **Upgrade friendly** – review Registry and patch modules during upgrades
- **Test friendly** – individual patches can be enabled/disabled

---

### Chapter 17 – Idempotent Monkey Patching Pattern

#### 17.1 The Biggest Mistake

Incorrect:

```python
cls.method = patched_method
```

Executed multiple times → recursive wrapping.

#### 17.2 Safe Pattern

Always use:

```python
if getattr(cls, "_custom_app_patched", False):
    return
```

#### 17.3 Complete Example

```python
def patch():
    from erpnext.stock import stock_ledger
    cls = stock_ledger.update_entries_after

    if getattr(cls, "_custom_app_patched", False):
        return

    original = cls.update_outgoing_rate_on_transaction

    def patched(self, sle):
        original(self, sle)
        custom_logic(self, sle)

    cls.update_outgoing_rate_on_transaction = patched
    cls._custom_app_patched = True
```

#### 17.4 Why Class‑Level Sentinel Is Better

- Bad: Module‑level `_PATCHED` protects only the current module.
- Good: `cls._custom_app_patched` protects the actual target class across all modules.

#### 17.5 Multi‑Worker Safety

Each process has its own memory, classes and sentinel → patch once per worker – safe.

---

### Chapter 18 – Backend Monkey Patching Framework

#### 18.1 Standard Backend Patch Layout

```
custom_app/
└── overrides/
    └── backend/
        ├── stock_ledger.py
        ├── taxes_and_totals.py
        └── reports.py
```

#### 18.2 Generic Pattern

```python
def patch():
    cls = SomeClass
    if getattr(cls, "_patched", False):
        return

    original = cls.some_method

    def patched(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        custom_logic()
        return result

    cls.some_method = patched
    cls._patched = True
```

#### 18.3 Preserve Signature

Always use `*args, **kwargs` because ERPNext upgrades may add parameters.

#### 18.4 Always Call Original First

Recommended:

```python
result = original(...)
custom_logic()
return result
```

#### 18.5 Exception Handling

```python
try:
    custom_logic()
except Exception:
    frappe.log_error(...)
```

Never break ERPNext core processing.

---

### Chapter 19 – Frontend Monkey Patching Framework

#### 19.1 Frontend Architecture

Frontend patches use `app_include_js`.

#### 19.2 Registration

```python
# hooks.py
app_include_js = [
    "/assets/custom_app/js/runtime_patches.js"
]
```

#### 19.3 Folder Structure

```
custom_app/
├── public/
│   └── js/
│       └── runtime_patches.js
└── hooks.py
```

#### 19.4 Prototype Patching

```javascript
const proto = SomeClass.prototype;

if (proto._patched) return;

const original = proto.method;

proto.method = function () {
    const result = original.apply(this, arguments);
    customLogic();
    return result;
};

proto._patched = true;
```

#### 19.5 Why Prototype Patching Works

All instances share the same prototype, so changing `SomeClass.prototype.method` changes behaviour globally.

#### 19.6 Build Process

After changing JS, run `bench build` or `bench watch`.

---

## Part 5 – Scenario‑Specific Implementations

### Chapter 20 – Scenario 1: `Dashboard.setup_dashboard_sections()`

#### 20.1 Target

- **File:** `frappe/public/js/frappe/form/dashboard.js`
- **Class:** `frappe.ui.form.Dashboard`
- **Method:** `setup_dashboard_sections()`

#### 20.2 Production Patch

```javascript
// custom_app/public/js/runtime_patches.js

(() => {
    const proto = frappe.ui.form.Dashboard.prototype;
    if (proto._custom_dashboard_patched) return;

    const original = proto.setup_dashboard_sections;

    proto.setup_dashboard_sections = function () {
        original.apply(this, arguments);
        this.custom_section = this.make_section({
            label: __("Custom Insights"),
            css_class: "custom-insights",
            collapsible: true,
            hidden: 0,
            is_dashboard_section: 1,
        });
    };

    proto._custom_dashboard_patched = true;
})();
```

#### 20.3 Registration

```python
app_include_js = ["/assets/custom_app/js/runtime_patches.js"]
```

#### 20.4 Risks

- Method rename (`setup_dashboard_sections`)
- Internal refactor (e.g., `make_section` may disappear)

#### 20.5 Upgrade Audit Checklist

- Verify `frappe.ui.form.Dashboard` exists
- Verify `setup_dashboard_sections` exists
- Verify `make_section` exists

---

### Chapter 21 – Scenario 2: `QueryReport.prepare_columns()`

#### 21.1 Target

- **File:** `apps/frappe/frappe/public/js/frappe/views/reports/query_report.js`
- **Class:** `frappe.views.QueryReport`
- **Method:** `prepare_columns(columns)`

#### 21.2 Typical Use Cases

- Global currency formatting
- Column injection (metadata, audit, KPI)
- Dynamic width adjustment

#### 21.3 Production Implementation

```javascript
(() => {
    const proto = frappe.views.QueryReport.prototype;
    if (proto._custom_prepare_columns_patched) return;

    const original = proto.prepare_columns;

    proto.prepare_columns = function(columns) {
        const prepared = original.call(this, columns);

        prepared.forEach((col) => {
            if (col.fieldtype === "Currency") {
                col.align = "right";
                col.width = Math.max(col.width || 120, 140);
            }
            if (col.fieldtype === "Link") {
                col.width = Math.max(col.width || 180, 220);
            }
        });

        return prepared;
    };

    proto._custom_prepare_columns_patched = true;
})();
```

#### 21.4 Common Mistake

**Wrong:** not returning the prepared columns → reports may fail.

#### 21.5 Upgrade Audit Checklist

- Verify `frappe.views.QueryReport` exists
- Verify `prepare_columns` exists
- Verify method still returns columns (Frappe v16 changes)

---

### Chapter 22 – Scenario 3: Frontend `TaxesAndTotals.calculate_item_values()`

#### 22.1 Target

- **File:** `apps/erpnext/erpnext/public/js/controllers/taxes_and_totals.js`
- **Class:** `erpnext.taxes_and_totals`
- **Method:** `calculate_item_values()`

#### 22.2 Production Implementation

```javascript
(() => {
    if (!window.erpnext || !erpnext.taxes_and_totals) return;

    const proto = erpnext.taxes_and_totals.prototype;
    if (proto._custom_calc_item_values) return;

    const original = proto.calculate_item_values;

    proto.calculate_item_values = function() {
        original.apply(this, arguments);

        for (const item of this.frm.doc.items || []) {
            item.custom_margin_pct = item.amount ?
                ((item.amount - item.valuation_rate) / item.amount) * 100 : 0;
        }

        this.frm.fields_dict.items.grid.refresh();
    };

    proto._custom_calc_item_values = true;
})();
```

#### 22.3 Limitation

This is **UI logic only** – server validation can still override values. Often a **frontend + backend patch** is required.

---

### Chapter 23 – Scenario 4: Backend `calculate_item_values()`

#### 23.1 Target

- **File:** `erpnext/controllers/taxes_and_totals.py`
- **Class:** `calculate_taxes_and_totals`
- **Method:** `calculate_item_values()`

#### 23.2 Enterprise Patch Pattern

```python
def patch():
    from erpnext.controllers import taxes_and_totals

    cls = taxes_and_totals.calculate_taxes_and_totals

    if getattr(cls, "_custom_patched", False):
        return

    original = cls.calculate_item_values

    def patched(self):
        original(self)
        for item in (self.doc.items or []):
            if item.amount and item.weight:
                item.cost_per_kg = item.amount / item.weight

    cls.calculate_item_values = patched
    cls._custom_patched = True
```

#### 23.3 Why Safer Than Doc Events

Execution occurs **inside** the ERPNext calculator, not after validation – no recalculation race conditions.

#### 23.4 Upgrade Risk

**High** – core accounting component. Every major upgrade must verify the method signature.

---

### Chapter 24 – Scenario 5: `update_outgoing_rate_on_transaction()`

#### 24.1 Target

- **File:** `erpnext/stock/stock_ledger.py`
- **Class:** `update_entries_after`
- **Method:** `update_outgoing_rate_on_transaction()`

#### 24.2 Why Doc Events Fail Here

The repost engine often uses `frappe.db.set_value()` or `doc.db_update()`, bypassing document lifecycle hooks. Therefore **patching is required**.

#### 24.3 Production Patch

```python
def patch():
    from erpnext.stock import stock_ledger

    cls = stock_ledger.update_entries_after

    if getattr(cls, "_custom_outgoing_rate_patch", False):
        return

    original = cls.update_outgoing_rate_on_transaction

    def patched(self, sle):
        original(self, sle)
        try:
            if sle.voucher_type == "Stock Entry":
                sync_custom_costing(sle)
        except Exception:
            frappe.log_error(frappe.get_traceback(), "Custom Patch Failure")

    cls.update_outgoing_rate_on_transaction = patched
    cls._custom_outgoing_rate_patch = True
```

#### 24.4 Critical Rule

**Never replace `original(self, sle)`** unless you intentionally replace ERPNext valuation logic. Preferred: call core first, then extend.

---

## Part 6 – Complete Sample Codebase and Architecture

### Chapter 25 – Complete Sample Codebase

Full app structure:

```
custom_app/
│
├── __init__.py
├── hooks.py
│
├── services/
│   ├── patch_manager.py
│   ├── patch_registry.py
│   └── rollback_manager.py
│
├── overrides/
│   ├── backend/
│   │   ├── stock_ledger.py
│   │   ├── taxes_and_totals.py
│   │   └── reports.py
│   └── frontend/
│       ├── dashboard.js
│       ├── query_report.js
│       └── taxes_and_totals.js
│
├── public/
│   └── js/
│       └── runtime_patches.js
│
└── tests/
    └── test_patches.py
```

---

### Chapter 26 – Complete `__init__.py`

```python
# custom_app/__init__.py

from __future__ import unicode_literals

__version__ = "0.0.1"

def _apply_patches():
    """Apply all monkey patches – idempotent, safe to call multiple times."""
    try:
        import frappe
        # Only apply when we have a live site connection
        if not getattr(frappe, "local", None) or not getattr(frappe.local, "site", None):
            return
    except ImportError:
        return

    try:
        from custom_app.services.patch_manager import apply_all_patches
        apply_all_patches()
    except Exception as e:
        # Log but never crash app discovery or bench commands
        import sys
        if "bench" not in sys.argv and "migrate" not in sys.argv:
            print(f"Warning: Could not apply patches: {e}")

_apply_patches()
```

**Discussion:**  
- `__init__.py` executes when Frappe loads the app (during hooks discovery).  
- The `try/except` prevents startup failure if a patch target is missing (e.g. after upgrade).  
- The `frappe.local.site` guard prevents execution during CLI commands that have no site.

---

### Chapter 27 – Complete `runtime_patches.js`

```javascript
// custom_app/public/js/runtime_patches.js

(() => {
    function patch_dashboard() {
        const proto = frappe.ui.form.Dashboard.prototype;
        if (proto._custom_dashboard) return;
        const original = proto.setup_dashboard_sections;
        proto.setup_dashboard_sections = function () {
            original.apply(this, arguments);
            // custom dashboard additions
        };
        proto._custom_dashboard = true;
    }

    function patch_query_report() {
        const proto = frappe.views.QueryReport.prototype;
        if (proto._custom_query_report) return;
        const original = proto.prepare_columns;
        proto.prepare_columns = function (columns) {
            const result = original.call(this, columns);
            // modify columns
            return result;
        };
        proto._custom_query_report = true;
    }

    function patch_taxes_and_totals() {
        if (!erpnext || !erpnext.taxes_and_totals) return;
        const proto = erpnext.taxes_and_totals.prototype;
        if (proto._custom_taxes_patch) return;
        const original = proto.calculate_item_values;
        proto.calculate_item_values = function () {
            original.apply(this, arguments);
            // custom calculations
        };
        proto._custom_taxes_patch = true;
    }

    patch_dashboard();
    patch_query_report();
    patch_taxes_and_totals();
})();
```

---

### Chapter 28 – Complete `hooks.py` Architecture

```python
# custom_app/hooks.py

app_name = "custom_app"
app_title = "Custom App"

# ---------------------------------------------------------------------
# Runtime Patch Registration
# ---------------------------------------------------------------------
_PATCH_MANAGER = "custom_app.services.patch_manager.apply_all_patches"

before_request = [_PATCH_MANAGER]
before_job = [_PATCH_MANAGER]

# ---------------------------------------------------------------------
# Frontend Runtime Patches
# ---------------------------------------------------------------------
app_include_js = ["/assets/custom_app/js/runtime_patches.js"]
```

**Why use a constant reference:** single source of truth, less typing, easy refactoring.

**Hook execution coverage:**  

| Context          | `before_request` | `before_job` |
|------------------|------------------|--------------|
| Desk             | Yes              | No           |
| REST API         | Yes              | No           |
| Worker           | No               | Yes          |
| Scheduler Job    | No               | Yes          |
| Console          | No               | No           |
| Execute          | No               | No           |

Thus `hooks.py` alone is **insufficient** – need `__init__.py` as well (see hybrid approach).

---

### Chapter 29 – Complete `patch_manager.py`

```python
# custom_app/services/patch_manager.py

from importlib import import_module

_PATCHED = False

def apply_all_patches():
    global _PATCHED
    if _PATCHED:
        return

    from custom_app.services.patch_registry import PATCH_REGISTRY

    for patch_path in PATCH_REGISTRY:
        try:
            module_path, fn_name = patch_path.rsplit(".", 1)
            module = import_module(module_path)
            patch_fn = getattr(module, fn_name)
            patch_fn()
        except Exception:
            import frappe
            frappe.log_error(title="Patch Registration Failed", message=frappe.get_traceback())

    _PATCHED = True
```

**Why this design:** modular, scalable, maintainable, upgrade‑friendly.

---

### Chapter 30 – Complete `patch_registry.py`

```python
# custom_app/services/patch_registry.py

PATCH_REGISTRY = [
    # Backend
    "custom_app.overrides.backend.stock_ledger.patch",
    "custom_app.overrides.backend.taxes_and_totals.patch",
    "custom_app.overrides.backend.query_reports.patch",
]
```

**Benefits:**  
- Single file to review for all runtime modifications.  
- Can be compared against ERPNext upgrade changes in CI/CD.  
- Enterprise enhancement: use a dictionary to group patches by domain.

---

## Part 7 – Testing, Validation, and Observability

### Chapter 31 – Testing Framework for Runtime Patches

#### 31.1 Why Testing Is Critical

Runtime patches modify core framework, business logic, accounting, stock valuation, UI – must be tested for registration, execution, idempotency, upgrade compatibility, and rollback safety.

#### 31.2 Testing Pyramid

```
        ┌──────────────┐
        │ UAT          │
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │ Integration  │
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │ Runtime      │
        │ Validation   │
        └──────┬───────┘
               │
        ┌──────▼───────┐
        │ Unit Tests   │
        └──────────────┘
```

#### 31.3 Patch Registration Test

```python
from custom_app.services.patch_manager import apply_all_patches
apply_all_patches()
from erpnext.stock import stock_ledger
assert getattr(stock_ledger.update_entries_after, "_custom_app_patched", False) is True
```

#### 31.4 Idempotency Test

Call `apply_all_patches()` three times – expect no exception, no double wrapping, no duplicate logging.

#### 31.5 Wrapper Validation Test

Compare `id(original_method)` before and after patching – method should be replaced once, not on every call.

#### 31.6 Frontend Testing

Verify prototype flags exist: `frappe.ui.form.Dashboard.prototype._custom_dashboard_patch`, etc.

#### 31.7 Runtime Coverage Test Matrix

| Scenario               | Expected                 |
|------------------------|--------------------------|
| Web Request            | Patch active             |
| REST API               | Patch active             |
| Worker Job             | Patch active             |
| Scheduler Job          | Patch active             |
| Console                | Patch active             |
| Execute                | Patch active             |
| `enqueue(now=True)`    | Patch active             |

---

### Chapter 32 – Bench Console Validation

Console bypasses `before_request` and `before_job` completely. Yet many use `bench console` for debugging, data repair, bulk updates, migrations.

#### Verification Script

```python
from erpnext.stock import stock_ledger
print(getattr(stock_ledger.update_entries_after, "_custom_app_patched", False))
# Expected: True
```

#### Validate Method Replacement

```python
print(stock_ledger.update_entries_after.update_outgoing_rate_on_transaction)
# Expected: custom wrapper function
```

#### Console Validation Checklist

- Patch registry loaded
- Patch manager loaded
- Sentinel present
- Method replaced

**Enterprise recommendation:** include `bench --site mysite console` validation in every major release deployment QA.

---

### Chapter 33 – Worker Validation

Most ERPNext heavy processing (repost item valuation, email queue, background reports) occurs in workers.

#### Test Worker Patch

```python
def test_worker_patch():
    from erpnext.stock import stock_ledger
    frappe.logger().info(getattr(stock_ledger.update_entries_after, "_custom_app_patched", False))

frappe.enqueue(test_worker_patch)
# Expected log: True
```

#### Validate Multiple Workers

Each worker (short, default, long) should independently report `True` because each process maintains its own memory space.

#### Common Failure

Patch works in web request but not in worker → cause: only `before_request` used. Solution: `before_request` + `before_job`.

---

### Chapter 34 – Repost Item Valuation Validation

This is the **most important test** for stock‑related patches (`update_outgoing_rate_on_transaction`, `update_rate_on_stock_entry`).

#### Validation Procedure

1. Create Purchase Receipt
2. Create Stock Entry
3. Create Backdated Purchase Receipt
4. Run **Repost Item Valuation**
5. Verify custom logic executed (via logs)

#### Validation Matrix

| Scenario                    | Expected            |
|-----------------------------|---------------------|
| Stock Entry                 | Works               |
| Delivery Note               | Works               |
| Purchase Receipt            | Works               |
| Sales Invoice               | Works               |
| Repost Item Valuation       | Works               |
| Backdated Transaction       | Works               |

---

### Chapter 35 – Verification and Debugging

#### 35.1 Verify Patch Status (Python)

```python
# Run in bench console
from erpnext.controllers import taxes_and_totals
from erpnext.stock import stock_ledger

# Check sentinel presence
print("calculate_item_values patched:", 
      getattr(taxes_and_totals.calculate_taxes_and_totals, 
              "_your_app_patched_calc_item_values", False))

print("update_outgoing_rate_on_transaction patched:", 
      getattr(stock_ledger.update_entries_after, 
              "_your_app_patched_outgoing_rate", False))
```

#### 35.2 Verify Patch Status (JavaScript)

Open browser console on any desk page:

```javascript
// Check if patches were applied
console.log("Dashboard patched:", 
            frappe.ui.form.Dashboard.prototype._your_app_dashboard_patched);
console.log("QueryReport patched:", 
            frappe.views.QueryReport.prototype._your_app_report_columns_patched);
console.log("TaxesAndTotals patched:", 
            erpnext.taxes_and_totals.prototype._your_app_item_values_patched);
```

#### 35.3 Monitor Logs

Enable debug logging to confirm patches load:

```python
# In core_overrides.py
frappe.logger("your_app").info("Applying core overrides")
```

View logs:

```bash
bench --site yoursite console
tail -f logs/frappe.log | grep "your_app"
```

---

### Chapter 36 – Observability and Logging

#### 36.1 Why Logging Is Mandatory

Without logging you cannot answer: Patch applied? Executed? Failed?

#### 36.2 Registration Logging

```python
frappe.logger().info("Stock Ledger Patch Applied")
```

#### 36.3 Execution Logging

```python
frappe.logger().info(f"Voucher: {sle.voucher_no}")
```

#### 36.4 Error Logging

```python
try:
    custom_logic()
except Exception:
    frappe.log_error(frappe.get_traceback(), "Custom Patch Failure")
```

#### 36.5 Structured Logging

```python
frappe.logger().info({
    "patch": "stock_ledger",
    "voucher": sle.voucher_no,
    "item": sle.item_code
})
```

#### 36.6 Log Categories

- `PATCH_REGISTRATION`
- `PATCH_EXECUTION`
- `PATCH_FAILURE`
- `PATCH_ROLLBACK`
- `PATCH_VALIDATION`

---

## Part 8 – Production Deployment and Governance

### Chapter 37 – Production Deployment Architecture

#### 37.1 Single Server Deployment

Enable `before_request`, `before_job` and `__init__.py`.

#### 37.2 Multi‑Worker Deployment

Each process (web, worker‑default, worker‑short, worker‑long, scheduler) has its own memory → patch once per process – expected.

#### 37.3 Docker Deployment

Container restart creates fresh process memory → `__init__.py` ensures automatic patch registration.

#### 37.4 Kubernetes Deployment

Pods restart frequently (rolling update, autoscaling, node failure) – `__init__.py` guarantees patches are applied on new pods.

#### 37.5 Enterprise Recommendation

Use **all three**: `before_request`, `before_job`, and `custom_app.__init__.py` with an idempotent, safe, logged, tested patch manager.

#### 37.6 Final Deployment Matrix

| Context                | `before_request` | `before_job` | `__init__.py` |
|------------------------|------------------|--------------|---------------|
| Desk                   | Yes              | No           | Yes           |
| API                    | Yes              | No           | Yes           |
| Worker                 | No               | Yes          | Yes           |
| Scheduler              | No               | Yes          | Yes           |
| Console                | No               | No           | Yes           |
| Execute                | No               | No           | Yes           |
| `enqueue(now=True)`    | No               | No           | Yes           |
| Docker restart         | Depends          | Depends      | Yes           |
| Kubernetes pod restart | Depends          | Depends      | Yes           |

---

### Chapter 38 – Upgrade Governance and Compatibility Testing

#### 38.1 Why Upgrade Governance Is Mandatory

Runtime patches depend on internal classes, functions, signatures, private APIs – they have **no compatibility guarantees**. Frappe v16 introduced framework, UI, reporting and background processing changes.

#### 38.2 Upgrade Risk Categories

| Risk Level | Example                         |
|------------|---------------------------------|
| Low        | 16.20.0 → 16.21.0 (bug fix)     |
| Medium     | 16.15.x → 16.21.x (minor refactor) |
| High       | 15.x → 16.x, 16.x → 17.x (major) |

#### 38.3 Patch Inventory Requirement

Every patch must be documented:

```yaml
Patch ID: STOCK-001
Target: erpnext.stock.stock_ledger.update_entries_after
Method: update_outgoing_rate_on_transaction
Business Reason: Synchronise custom costing
Risk Level: HIGH
Owner: ERP Team
```

#### 38.4 Upgrade Audit Checklist

For every patched method:

- Verify class exists (`hasattr(stock_ledger, "update_entries_after")`)
- Verify method exists (`hasattr(cls, "update_outgoing_rate_on_transaction")`)
- Verify signature (use `inspect.signature`)
- Verify return type (e.g., `prepare_columns` returns array)
- Verify namespace (e.g., `erpnext.taxes_and_totals` exists)

#### 38.5 Automated Upgrade Validation

```python
def test_patch_targets_exist():
    from erpnext.stock import stock_ledger
    assert hasattr(stock_ledger.update_entries_after, "update_outgoing_rate_on_transaction")
```

Run in CI/CD, upgrade testing, release validation.

#### 38.6 Enterprise Upgrade Workflow

1. ERPNext upgrade announced
2. Review release notes
3. Review patch registry
4. Verify targets
5. Run automated tests
6. Run UAT
7. Deploy

---

### Chapter 39 – Rollback Strategy

#### 39.1 Why Rollback Matters

Patches can fail due to renamed methods, removed classes, changed signatures, framework refactors.

#### 39.2 Never Destroy Original References

**Bad:** `cls.method = patched` without saving original.  
**Good:** `original = cls.method`

#### 39.3 Registry‑Based Rollback

```python
PATCH_STATE = {}
# During patch
PATCH_STATE["stock_ledger"] = cls.update_outgoing_rate_on_transaction
# Rollback
cls.update_outgoing_rate_on_transaction = PATCH_STATE["stock_ledger"]
```

#### 39.4 Enterprise Rollback Service

```python
# rollback_manager.py
def rollback_all():
    rollback_stock_patch()
    rollback_tax_patch()
    rollback_report_patch()
```

#### 39.5 Emergency Disable Switch

```json
{ "disable_runtime_patches": 1 }
```

```python
if frappe.conf.get("disable_runtime_patches"):
    return
```

Allows production recovery without code deployment.

---

### Chapter 40 – Security Considerations

#### 40.1 Why Security Matters

Monkey patches execute inside core ERPNext processes (accounting, stock valuation, payroll, financial posting). Mistakes affect data integrity, security, audit trails, compliance.

#### 40.2 Never Bypass Permissions

**Bad:** `frappe.set_value(...)` without validation.

#### 40.3 Preserve Original Security

Preferred: call `original(...)` then `custom_logic(...)`.

#### 40.4 Avoid Direct SQL

Avoid `frappe.db.sql("UPDATE tabSales Invoice...")` unless absolutely necessary.

#### 40.5 Audit Trail Requirements

Every custom update must be logged, traceable, documented.

#### 40.6 Financial Patch Rule

If a patch affects GL Entry, Stock Ledger, Valuation or Taxes – **mandatory review** before deployment.

---

### Chapter 41 – Enterprise Governance Model

#### 41.1 Patch Approval Process

Business Request → Technical Review → Architecture Review → Development → Testing → Deployment

#### 41.2 Required Documentation

Every patch must have: Business Requirement, Technical Design, Risk Assessment, Upgrade Impact, Rollback Plan.

#### 41.3 Ownership

Every patch must have: Technical Owner, Business Owner, Support Owner.

#### 41.4 Patch Lifecycle

Requested → Approved → Developed → Tested → Released → Maintained → Retired

#### 41.5 Technical Debt Management

Review annually: still required? Can official hook replace it? Can core ERPNext now support it? Many patches should eventually be retired.

---

### Chapter 42 – Final Architect Recommendations

#### 42.1 Decision Tree

1. Can official hook solve it? → Use `doc_events`
2. Can controller override solve it? → Use `override_doctype_class`
3. Can API override solve it? → Use `override_whitelisted_methods`
4. No official mechanism exists → **Monkey patch** (with this handbook)

#### 42.2 Frontend Recommendations

| Component                        | Mechanism      |
|----------------------------------|----------------|
| `frappe.ui.form.Dashboard`       | `app_include_js` |
| `frappe.views.QueryReport`       | `app_include_js` |
| `erpnext.taxes_and_totals` (JS)  | `app_include_js` |

#### 42.3 Backend Recommendations

| Method                                      | Registration |
|---------------------------------------------|--------------|
| `calculate_item_values()`                   | `before_request` + `before_job` + `__init__.py` |
| `update_outgoing_rate_on_transaction()`     | `before_request` + `before_job` + `__init__.py` |

#### 42.4 Recommended Production Architecture

```
custom_app/
├── __init__.py
├── hooks.py
├── services/
│   ├── patch_manager.py
│   ├── patch_registry.py
│   └── rollback_manager.py
├── overrides/
│   ├── backend/
│   └── frontend/
├── tests/
└── public/js/
    └── runtime_patches.js
```

#### 42.5 Registration Strategy

```python
# hooks.py
before_request = ["custom_app.services.patch_manager.apply_all_patches"]
before_job = ["custom_app.services.patch_manager.apply_all_patches"]
```

```python
# __init__.py
try:
    from custom_app.services.patch_manager import apply_all_patches
    apply_all_patches()
except Exception:
    pass
```

#### 42.6 Why Hybrid Registration Wins

| Context          | `before_request` | `before_job` | `__init__.py` |
|------------------|------------------|--------------|---------------|
| Web              | Yes              | No           | Yes           |
| API              | Yes              | No           | Yes           |
| Worker           | No               | Yes          | Yes           |
| Scheduler        | No               | Yes          | Yes           |
| Console          | No               | No           | Yes           |
| Execute          | No               | No           | Yes           |
| `enqueue(now=True)` | No            | No           | Yes           |

#### 42.7 Final Enterprise Standard (ERPNext v16)

For production systems, the recommended standard is:

- **Patch Registry** + **Patch Manager** + **Class‑Level Sentinels**
- **`before_request`** + **`before_job`** + **`__init__.py`**
- **Automated Testing** + **Upgrade Governance** + **Rollback Framework**

This architecture provides the highest practical level of reliability for runtime patching across:

- Web Requests
- REST APIs
- Background Workers
- Scheduler Jobs
- Repost Item Valuation
- `bench console` / `bench execute`
- `frappe.enqueue(now=True)`
- Docker containers
- Kubernetes pods
- Multi‑worker deployments

---

## Part 9 – Appendices and Reference

### Appendix A – File Structure Reference

#### Complete Production-Ready File Tree

```
your_app/
├── __init__.py
│   └── (safe patching with site guard)
├── hooks.py
│   ├── before_request = ["your_app.core_overrides.apply"]
│   ├── before_job = ["your_app.core_overrides.apply"]
│   └── app_include_js = ["/assets/your_app/js/core_overrides.js"]
├── core_overrides.py
│   └── apply()  # Central dispatcher
├── overrides/
│   ├── __init__.py
│   ├── taxes_and_totals.py    # Scenario 4 patch
│   └── stock_ledger.py        # Scenario 5 patch
├── public/
│   ├── js/
│   │   └── core_overrides.js  # Scenarios 1, 2, 3
│   └── css/
│       └── custom.css         # Optional
├── patches.txt                # Document all patches for maintainers
└── README.md                  # Explain which core methods are overridden
```

---

### Appendix B – Execution Context Matrix

| Execution Context | `before_request` | `before_job` | `app_include_js` |
|-------------------|:----------------:|:------------:|:----------------:|
| Desk / Web HTTP request | ✅ | — | ✅ |
| API call (`/api/method/*`) | ✅ | — | (N/A — frontend not loaded) |
| Background job (`frappe.enqueue` with `now=False`) | — | ✅ | — |
| ERPNext `repost_item_valuation` job | — | ✅ | — |
| Scheduled / cron job | — | ✅ | — |
| `bench console` | ❌ | ❌ | — |
| `bench execute <method>` | ❌ | ❌ | — |
| `bench migrate` / build / tooling | ❌ | ❌ | — |
| `frappe.enqueue(..., now=True)` | — | ❌ | — |

`—` = Not applicable / not loaded in that context

---

### Appendix C – Gotchas, Edge Cases & FAQ

#### Q1: "My frontend patch isn't loading — what's wrong?"

**Checklist:**
1. Run `bench build --app your_app` and `bench clear-cache`
2. Verify `hooks.py` contains `app_include_js = ["/assets/your_app/js/core_overrides.js"]`
3. Ensure the file path matches exactly (case-sensitive)
4. Check browser console for 404 errors on the asset
5. Verify your app is installed on the site (`bench --site yoursite list-apps`)

#### Q2: "The repost job never imports my app — will `__init__.py` still patch it?"

Yes. The worker process imports your app via `get_hooks()` → `import your_app.hooks` → which triggers `__init__.py` first. This implicit chain is reliable but hidden — another reason to prefer explicit hooks for production.

#### Q3: "`before_job` doesn't run for `frappe.enqueue(..., now=True)`"

Correct. `now=True` runs the job inline and bypasses `execute_job()`, so `before_job` will not fire. With the hooks mechanism, patch manually in such code; with `__init__.py` the package is already imported, so it's covered.

#### Q4: "My patch works on my desktop but fails on production server"

Common causes:
- Different app install order affects load timing
- Production uses multiple workers; patch must apply in each worker independently
- Cache differences — run `bench clear-cache` on production after deployment

#### Q5: "Can I patch a method that returns a value from JavaScript?"

Yes — but you MUST return it. See Chapter 10.3 for the correct pattern.

#### Q6: "Will my patch survive an ERPNext upgrade?"

If implemented correctly with graceful failure handling, it will either:
- Continue working if the target method unchanged
- Log a warning and skip if the method was removed/renamed
- Never crash the site

However, you should always test patches against new versions in a staging environment before upgrading production.

#### Q7: "Why can't I just put my patch code directly in `hooks.py`?"

Because `hooks.py` is executed during app discovery and Redis cache rebuilds, leading to:
- `cannot pickle module objects` errors
- Random crashes during `bench clear-cache`
- Bench command failures
- Unstable behaviour in multi-site setups

Always use the centralised loader pattern with `core_overrides.py` as described in Chapter 11.

---

### Appendix D – Safety, Idempotency & Upgrade Proofing

#### D.1 The Sentinel Pattern

Every patch must set a class-level sentinel attribute to make the operation idempotent:

```python
# Python
_PATCH_APPLIED = "_your_app_unique_marker"
if getattr(cls, _PATCH_APPLIED, False):
    return
# ... patch logic ...
setattr(cls, _PATCH_APPLIED, True)
```

```javascript
// JavaScript
if (proto._your_app_unique_marker) return;
// ... patch logic ...
proto._your_app_unique_marker = true;
```

This ensures that if `apply()` is called multiple times (e.g., `before_request` firing on every HTTP request), the actual override happens only once.

#### D.2 Graceful Failure on Missing Targets

Always wrap target imports in `try/except` to prevent the patch from breaking the site during upgrades:

```python
def apply():
    try:
        from erpnext.controllers import taxes_and_totals as module
    except ImportError:
        frappe.logger("your_app").warning(
            "Could not import taxes_and_totals — patch skipped. "
            "This may happen during migration or after an upgrade."
        )
        return
    
    cls = getattr(module, "calculate_taxes_and_totals", None)
    if not cls:
        return
    # ... proceed with patching
```

#### D.3 Upgrade Impact Assessment

| Risk | Mitigation |
|------|------------|
| Target method removed or renamed in new ERPNext version | Patch fails gracefully (guard + sentinel prevents broken assignment) |
| Target function signature changes | Python will raise `TypeError` when calling original; log and skip |
| Target class restructured | Import guard catches AttributeError; patch not applied |

**Before upgrading Frappe/ERPNext:** Run a validation script (see Chapter 35) to confirm all patches still apply.

---

### Appendix E – Documentation Template (patches.txt)

```markdown
# Custom App — Core Overrides Documentation

## Python Overrides
- `erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals.calculate_item_values`
  Purpose: Add custom_amount_per_kg calculation
  File: overrides/taxes_and_totals.py
  ERPNext version tested: v15+

- `erpnext.stock.stock_ledger.update_entries_after.update_outgoing_rate_on_transaction`
  Purpose: Sync custom data after repost rate updates
  File: overrides/stock_ledger.py

## JavaScript Overrides
- `frappe.ui.form.Dashboard.prototype.setup_dashboard_sections`
  Purpose: Inject custom dashboard section
  File: public/js/core_overrides.js

- `frappe.views.QueryReport.prototype.prepare_columns`
  Purpose: Global column formatting (Currency right-alignment)
  File: public/js/core_overrides.js

- `erpnext.taxes_and_totals.prototype.calculate_item_values`
  Purpose: Client-side custom_amount_per_kg calculation
  File: public/js/core_overrides.js
```

---

*This guide is current for Frappe v15+ / ERPNext v15+ and references version-16 branches.*  
*Compiled from production-grade methodologies and enterprise best practices.*