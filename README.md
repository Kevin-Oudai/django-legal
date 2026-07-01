# django-legal

**django-legal** is a lightweight Django app for managing legal documents (Terms of Use, Privacy Policy, etc.) and tracking which versions each user has agreed to.
This repository includes both the reusable app (`django_legal/`) and a small demo project (`test_project/`) you can run locally to see the flow end-to-end.

---

## What the app does

Many sites need users to agree to one or more legal documents, and to re-accept when those documents change.

**django-legal** provides:

- **Document & version management**
  - Create legal documents in the Django admin.
  - Split documents into ordered sections.
  - Publish immutable versions with an automatic `X.Y.Z` version label.
  - Store a hash for each published version.
- **User acceptance tracking**
  - Record which versions each user has accepted.
  - Keep a snapshot of the version hash at acceptance time.
  - Require re-acceptance for new versions.
- **View protection**
  - A `@legal_required` decorator that checks whether the user has accepted the latest versions of all required documents.
  - If not compliant, redirect the user to a central "acceptance gate" page or any custom page designated by the user.
- **Minimal templates**
  - Ships with simple example templates for the acceptance flow and current-version display.
  - You are encouraged to override these in your own project.
  - Individual legal document pages can also be replaced with document-specific templates.
- **Demo project included**
  - A minimal Django project with sample views and templates to exercise login + acceptance flows.

At a high level, the app answers one question:

> "Does the current authenticated user accept the conditions of all required legal documents?"

---

## Installation

Install from PyPI or from your chosen source:

```bash
pip install mroudai-django-legal
```

Install directly from GitHub:

```bash
pip install "mroudai-django-legal @ git+https://github.com/Kevin-Oudai/django-legal.git@v0.1.3"
```

Ensure all the listed apps are in the INSTALLED_APPS list:

```python
# settings.py
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    ...,
    "django_legal",
]
```

Make sure you have authentication middleware enabled:

```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # ...
]
```

Include the app's URLs (for the acceptance gate and the current version view):

```python
# urls.py
from django.urls import include, path

urlpatterns = [
    # ...
    path("legal/", include("django_legal.urls")),
]
```

Run migrations:

```bash
python manage.py migrate
```

---

## Configuration

Most projects can use the defaults. The main optional setting is:

```python
# settings.py
LEGAL_ACCEPTANCE_URL = "/legal/accept/"
```

If `LEGAL_ACCEPTANCE_URL` is set, `django-legal` will redirect non-compliant users to that path (or URL). If it is not set, the app will try to reverse the built-in gate view
named `"django_legal:accept"`, and finally fall back to `"/legal/accept/"` if URL reversing fails.

The app uses your configured `AUTH_USER_MODEL` internally, via `settings.AUTH_USER_MODEL`. It works with the default `django.contrib.auth.models.User` and with custom user models.

---

## Basic usage

### 1. Create documents in the admin

1. Log into Django admin.
2. Create one or more **LegalDocument** entries (e.g. "Terms of Use", "Privacy Policy").
   - Set `is_required=True` for documents that users must accept so they can access and use the site.
3. Add **sections** for each document using `LegalDocumentSection` to build up the full text in order.
4. Save the document. If sections exist, the admin will automatically publish an initial `1.0.0` version.
5. When you update sections later, either save again (auto-publish on changes) or use the admin action
   **"Publish new legal version from current sections"**. Each publish takes a snapshot of the current sections,
   computes a hash, and assigns an `X.Y.Z` version label.

Once a document has at least one published version, the app can start enforcing acceptance.
Required documents with *no* published version are ignored until you publish one.

### 2. Protect views with `@legal_required`

Use the `legal_required` decorator to enforce that the current user has accepted the latest versions of all required documents.

You will usually combine it with `@login_required` so only authenticated users reach the legal checks:

```python
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from django_legal.decorators import legal_required

@login_required
@legal_required
def dashboard(request):
    return render(request, "dashboard.html")
```

Behaviour:

- If the user is **not authenticated**, `legal_required` simply lets the view run; authentication is left to your own logic.
- If the user **is authenticated** and compliant, the view runs normally.
- If the user **is authenticated but missing required acceptances**, they are redirected to the acceptance gate URL (see below), with a `next` query parameter pointing back to the original path.

### 3. Use the acceptance gate

`django-legal` ships with a central gate view at `django_legal.views.acceptance_gate`, exposed by the URL pattern:

- `path("accept/", acceptance_gate, name="accept")` (included via `include("django_legal.urls"))`.

Behaviour:

- **GET**: shows required legal documents for which the current user has not accepted the latest version. It uses the template `django_legal/acceptance_gate.html` by default.
- **POST**: redirects to the first missing legal document page. The gate does not bulk-accept documents.
- Acceptance happens from the individual legal document page. Users accept or decline one document at a time.
- After accepting one document, the user is moved to the next missing required document. When no required documents remain, the user is redirected to `"/"`.
- Declining a document redirects to `"/"` without recording acceptance for that version.
- The gate view itself is protected with `@login_required`, so unauthenticated users are redirected to your login URL.

You can override the gate template by creating your own file at:

```text
templates/
  django_legal/
    acceptance_gate.html
```

### 4. Display the current version of a document

The app provides a simple view to display the latest published version of a document by slug:

- URL pattern: `path("<slug:slug>/current/", current_version_view, name="current_version")`
- Default template: `django_legal/current_version.html`

You can link to this from your own templates, for example:

```django
<a href="{% url 'django_legal:current_version' slug='terms-of-use' %}">
  View current Terms of Use
</a>
```

As with the gate template, you can override `current_version.html` under `templates/django_legal/` in your project.
For a per-document replacement, create a template at:

```text
templates/
  django_legal/
    documents/
      terms-of-use.html
```

The app looks for `django_legal/documents/<slug>.html` first, then falls back to `django_legal/current_version.html`.
Replacement templates receive the same context:

- `document`
- `version`
- `version_update_diff`
- `requires_acceptance`
- `remaining_legal_document_count`

If `requires_acceptance` is true, include a POST form with CSRF protection and buttons named `legal_action`:

```django
<form method="post">
  {% csrf_token %}
  <button type="submit" name="legal_action" value="accept">I accept these changes</button>
  <button type="submit" name="legal_action" value="decline">Decline</button>
</form>
```

---

## Highlighting document updates

Each `LegalDocumentVersion` can compare itself with the previous published version of the same document.
This is useful when users must review what changed before accepting a new Terms or Privacy version.

```python
version = document.versions.order_by("-created_at").first()
update_diff = version.get_update_diff()
```

`get_update_diff()` returns a dictionary:

- `current_version`: the version being displayed.
- `previous_version`: the previous published version, or `None` for the first version.
- `has_previous`: whether a previous version exists.
- `has_changes`: whether the generated blocks include added or removed content.
- `blocks`: ordered diff blocks with `kind`, `label`, `lines`, and `is_changed`.

Block kinds are:

- `added`: lines added in the current version.
- `removed`: lines present in the previous version but removed from the current version.
- `unchanged`: current-version lines that did not change.

The built-in `current_version_view` adds `version_update_diff` to the template context.
The default template renders the diff blocks, and projects can style or replace that display by overriding:

```text
templates/
  django_legal/
    current_version.html
```

For example:

```django
{% if version_update_diff.has_previous %}
  <p>Changes since v{{ version_update_diff.previous_version.version_label }}</p>
{% endif %}

{% for block in version_update_diff.blocks %}
  <div class="legal-diff-block legal-diff-block--{{ block.kind }}">
    {% if block.is_changed %}<strong>{{ block.label }}</strong>{% endif %}
    {% for line in block.lines %}
      <p>{{ line }}</p>
    {% endfor %}
  </div>
{% endfor %}
```

No migration is required for update highlighting because it is calculated from existing immutable version snapshots.

---

## Version publishing

- Calling `LegalDocument.publish_new_version()` returns `(version, created)`. When the current snapshot matches the latest version, it returns the existing version with `created=False`.
- Publishing is idempotent and uses a stable hash (slug + version + snapshot) to avoid churn; admin actions already handle this return shape.
- The next semantic version is chosen by diff size: up to 5% change bumps the patch, up to 15% bumps the minor, otherwise the major.

---

## Checking compliance in code

If you need to check a user's compliance manually (outside of the decorator), you can call `check_user_legal_compliance`:

```python
from django_legal.models import check_user_legal_compliance

is_compliant, missing_versions = check_user_legal_compliance(request.user)

if not is_compliant:
    # missing_versions is a list of LegalDocumentVersion objects
    ...
```

You generally don't need to record acceptances manually, but if you do, you can use the manager on `LegalDocumentAcceptance`:

```python
from django_legal.models import LegalDocumentAcceptance

LegalDocumentAcceptance.objects.record_acceptance(
    user=request.user,
    version=version,
    ip_address=request.META.get("REMOTE_ADDR"),
    user_agent=request.META.get("HTTP_USER_AGENT", ""),
)
```

---

## Demo project (local)

This repo ships with a minimal Django project under `test_project/` and a `manage.py` at the repo root. It is useful for quickly seeing the login + legal flow end-to-end.

```bash
# from the repository root (the folder containing manage.py)
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate
pip install -e .
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then:

1. Visit `http://127.0.0.1:8000/admin/` and create one or more `LegalDocument` entries with sections.
2. Navigate to `http://127.0.0.1:8000/` (protected by login + legal compliance).
3. Accept the current versions at `http://127.0.0.1:8000/legal/accept/`.
4. Try `http://127.0.0.1:8000/legal/status/` and `http://127.0.0.1:8000/legal/ok/` for example flows.

---

## Authentication and django-allauth

**django-legal** builds on Django's standard authentication system:

- It always references the user model via `settings.AUTH_USER_MODEL`.
- It expects `AuthenticationMiddleware` and session middleware to be enabled.
- It works with the default `User` model and with custom user models.

When you use **django-allauth**, no special integration is required:

- allauth signs users in to the same `request.user` object that `django-legal` uses.
- The `@login_required` and `@legal_required` decorators behave the same way regardless of how the user logged in (username/password, social login, etc.).

In an allauth project you typically have URLs like:

```python
path("accounts/", include("allauth.urls")),
path("legal/", include("django_legal.urls")),
```

and then decorate any protected views with `@login_required` and `@legal_required` as shown above.

---

## Project status

This is an early version of **django-legal**. The core behaviour is in place, but the API and templates may still evolve. Feedback and contributions are welcome.
