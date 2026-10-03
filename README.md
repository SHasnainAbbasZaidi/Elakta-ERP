# Elakta ERP

This Django application was restored from `full_code.txt`, which is retained locally as the original source snapshot and excluded from this repository. Modules cover CRM, complaints, tasks, maintenance, invoices, quotations, inventory, delivery challans, finance, reports, users, roles, and employees.

## Run

From this directory in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\start.ps1
```

Open http://127.0.0.1:8000. If the environment and database already exist, only run `start.ps1`.

The local SQLite database starts empty because the source export contains no database or uploaded media. Company profiles and reference data can be added through `/admin/`. Frontend libraries are loaded from public CDNs and require internet access.

`erp/settings.py` is configured for local development. Business logic is in `operations/views/`, database models in `operations/models.py`, and page templates in `operations/templates/operations/`.

## Verification and recent fixes

Run `.\.venv\Scripts\python.exe manage.py test` for isolated regression tests, and `.\.venv\Scripts\python.exe smoke_check.py` for page checks against the local database.

The UI now has shared styling in `operations/static/operations/app.css`, quick actions, mobile layouts, accessible card links, and empty chart states. Fixed document numbering, CRM notes, password hashing and role assignment, validation errors, dashboard balances and counts, finance detail rendering, and delivery stock rollback. Invoice and quotation totals are calculated on the server using decimal arithmetic; revisions preserve the original quotation.

Role enforcement is enabled: administrators retain full access, while other users need an assigned role with the corresponding module and action permissions. Old boolean permissions grant read access only. Review existing roles using the administrator account. Delete and approval actions require a CSRF-protected POST.

Validation covers the listed regression cases and page rendering; it is not an exhaustive audit of every legacy workflow. In particular, finance allocation edits, concurrent document numbering, and all populated print layouts need further coverage before production use.


### Reporting, ledgers and document costs
- Quotation cards use the same date/search filters as their rows. Approved quotations stay approved after validity expires; other quotations become expired after their expiry date.
- All time ignores stale start/end dates. Custom ranges support either or both bounds. Preset selection applies automatically.
- Quotation/invoice lines save a unit-cost snapshot. Profit = subtotal - discount - sum(quantity × unit cost); margin = profit / net sales × 100, excluding tax. Unknown historic costs remain incomplete until entered; no historical prices are invented. Zero net sales has no percentage margin.
- Inventory forms expose Vendor and Local (the existing database value Direct remains compatible). Vendor purchases require a vendor; Local can record a shop name. Edit item is available on the inventory list.
- Finance → Client & vendor ledgers provides every account, transaction references, payment details, date ranges, opening/running/closing balances and CSV exports. Positive client balances are receivable; positive vendor balances are payable. Only Paid payments settle balances. Other entries remain visible without assumed postings. Linked invoices determine the owning client. Opening balances derive from recorded history; imported opening balances, credit notes and purchase-to-payment allocation are not provided.
- Reports include sales/profit, quotation pipeline, invoice aging, vendor balances, current inventory valuation, cash movements, complaints and user activity. Sales and operations support client/user filters, and all reports export CSV. Aging uses invoice age rather than contractual due dates. Vendor purchase-level aging is not inferred without explicit allocations; inventory valuation is a current snapshot. Cash reports count only Paid receipts and disbursements in known categories.
- Migration 0003 adds nullable document unit costs. A SQLite backup was taken before applying it locally.
