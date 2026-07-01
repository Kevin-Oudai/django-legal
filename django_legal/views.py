from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .models import LegalDocument, LegalDocumentAcceptance, check_user_legal_compliance


def _home_redirect():
    return redirect("/")


def _missing_versions_for_user(user):
    if user is None or not user.is_authenticated:
        return []

    _is_compliant, missing_versions = check_user_legal_compliance(user)
    return sorted(
        missing_versions,
        key=lambda version: (version.document_id, version.id),
    )


def _first_missing_version_url(user):
    missing_versions = _missing_versions_for_user(user)
    if not missing_versions:
        return ""
    return reverse(
        "django_legal:current_version",
        kwargs={"slug": missing_versions[0].document.slug},
    )


def _record_acceptance(request: HttpRequest, version):
    LegalDocumentAcceptance.objects.record_acceptance(
        user=request.user,
        version=version,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )


def _current_version_template_names(document):
    return [
        f"django_legal/documents/{document.slug}.html",
        "django_legal/current_version.html",
    ]


@login_required
def acceptance_gate(request: HttpRequest) -> HttpResponse:
    """
    Legal acceptance gate.

    Templates:
    - Uses "django_legal/acceptance_gate.html" by default.
    - Projects can override this by creating a template with the same
      path in their own templates directory, for example:

        templates/
          django_legal/
            acceptance_gate.html

    Behaviour:
    - On GET, shows required legal documents for which the current
      user has not yet accepted the current version.
    - On POST, redirects to the first missing document page. Acceptance
      is recorded from the document page one version at a time.
    """
    user = request.user
    missing_versions = _missing_versions_for_user(user)
    first_missing_url = _first_missing_version_url(user)

    if request.method == "POST" and first_missing_url:
        return redirect(first_missing_url)
    if not missing_versions:
        return _home_redirect()

    context = {
        "missing_versions": missing_versions,
    }
    return render(request, "django_legal/acceptance_gate.html", context)


def current_version_view(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Display the current (latest) published version of a LegalDocument.

    Templates:
    - Uses "django_legal/current_version.html" by default.
    - Projects can override this by creating a template with the same
      path in their own templates directory, for example:

        templates/
          django_legal/
            current_version.html

    Behaviour:
    - Resolves the LegalDocument by slug.
    - Finds the latest LegalDocumentVersion for that document.
    - Renders the stored snapshot text (content_snapshot).
    - If the authenticated user still needs this required version,
      POST with legal_action=accept records this version and redirects
      to the next missing document, or "/" when no required documents remain.
    - POST with legal_action=decline returns to "/".
    """
    document = get_object_or_404(LegalDocument, slug=slug)
    current_version = document.versions.order_by("-created_at").first()
    missing_versions = _missing_versions_for_user(request.user)
    requires_acceptance = bool(
        current_version
        and request.user.is_authenticated
        and any(version.pk == current_version.pk for version in missing_versions)
    )

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        action = (request.POST.get("legal_action") or "").strip()
        if action == "decline":
            return _home_redirect()

        if current_version is not None and requires_acceptance:
            _record_acceptance(request, current_version)

        next_document_url = _first_missing_version_url(request.user)
        if next_document_url:
            return redirect(next_document_url)
        return _home_redirect()

    if current_version is None:
        return render(
            request,
            _current_version_template_names(document),
            {
                "document": document,
                "version": None,
                "version_update_diff": None,
                "requires_acceptance": False,
                "remaining_legal_document_count": len(missing_versions),
            },
        )

    return render(
        request,
        _current_version_template_names(document),
        {
            "document": document,
            "version": current_version,
            "version_update_diff": current_version.get_update_diff(),
            "requires_acceptance": requires_acceptance,
            "remaining_legal_document_count": len(missing_versions),
        },
    )
