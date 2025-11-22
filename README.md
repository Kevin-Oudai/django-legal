 # django-legal

**django-legal** is a lightweight Django app for managing legal documents (Terms of Use, Privacy Policy, etc.) and tracking which versions each user has agreed to.

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
  - If not compliant, redirect the user to a central “acceptance gate” page or any custom page designated by the user.
- **Minimal templates**
  - Ships with simple example templates for the acceptance flow and current-version display.
  - You are encouraged to override these in your own project.

At a high level, the app answers one question:

> “Does the current authenticated user accept the conditions of all required legal documents?”

---

## Installation

Install from PyPI or from your chosen source:

```bash
pip install django-legal
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

Include the app's URLs (for the acceptance gate and the “current version” view):

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
2. Create one or more **LegalDocument** entries (e.g. “Terms of Use”, “Privacy Policy”).
   - Set `is_required=True` for documents that users must accept so they can access and use the site.
3. Add **sections** for each document using `LegalDocumentSection` to build up the full text in order.
4. Publish a new version for each document. This takes a snapshot of the current sections, computes a hash, and assigns an `X.Y.Z` version label.

Once a document has at least one published version, the app can start enforcing acceptance.

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

- `path("accept/", acceptance_gate, name="accept")` (included via `include("django_legal.urls")`).

Behaviour:

- **GET**: shows all required legal documents for which the current user has not accepted the latest version. It uses the template `django_legal/acceptance_gate.html` by default.
- **POST**: records acceptance for all missing current versions for `request.user`, then redirects to:
  - The `next` parameter from the request (if present), or
  - `"/"` as a fallback.

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

