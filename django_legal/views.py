from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import LegalDocument, LegalDocumentAcceptance, check_user_legal_compliance


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
    - On GET, shows all required legal documents for which the current
      user has not yet accepted the current version.
    - On POST, records acceptance for all missing current versions and
      redirects to the "next" URL (if provided) or "/" as a default.
    """
    user = request.user
    next_url = request.GET.get("next") or request.POST.get("next") or "/"

    is_compliant, missing_versions = check_user_legal_compliance(user)

    if is_compliant or request.method == "POST":
        if not is_compliant:
            ip = request.META.get("REMOTE_ADDR")
            user_agent = request.META.get("HTTP_USER_AGENT", "")
            for version in missing_versions:
                LegalDocumentAcceptance.objects.record_acceptance(
                    user=user,
                    version=version,
                    ip_address=ip,
                    user_agent=user_agent,
                )
        return redirect(next_url)

    context = {
        "missing_versions": missing_versions,
        "next": next_url,
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
    - Renders the stored snapshot text (content_snapshot) as the
      authoritative version at publish time.
    """
    document = get_object_or_404(LegalDocument, slug=slug)
    current_version = document.versions.order_by("-created_at").first()

    if current_version is None:
        return render(
            request,
            "django_legal/current_version.html",
            {
                "document": document,
                "version": None,
            },
        )

    return render(
        request,
        "django_legal/current_version.html",
        {
            "document": document,
            "version": current_version,
        },
    )
