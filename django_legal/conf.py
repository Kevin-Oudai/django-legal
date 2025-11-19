from django.conf import settings
from django.urls import NoReverseMatch, reverse


def get_legal_acceptance_url() -> str:
    """
    Resolve the URL used as the legal acceptance gate.

    Behaviour:
    - If settings.LEGAL_ACCEPTANCE_URL is defined, its value is used directly.
      This can be a path (e.g. "/legal/accept/") or a fully-qualified URL.
    - Otherwise, django_legal will try to reverse the built-in gate view
      named "django_legal:accept".
    - If URL reversing fails (for example, the URLs are not included),
      the hard-coded fallback "/legal/accept/" is used.
    """
    configured = getattr(settings, "LEGAL_ACCEPTANCE_URL", None)
    if configured:
        return configured

    try:
        return reverse("django_legal:accept")
    except NoReverseMatch:
        return "/legal/accept/"

