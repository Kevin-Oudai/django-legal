from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from django_legal.decorators import legal_required
from django_legal.models import check_user_legal_compliance


@login_required
@legal_required
def home(request):
    """
    Basic homepage used to exercise the login and legal acceptance flow.
    """
    return render(request, "home.html")


@login_required
@legal_required
def legal_ok(request):
    """
    Example view that is only reachable when the user has accepted
    all required current legal documents.
    """
    return render(request, "legal_ok.html")


@login_required
def legal_status(request):
    """
    Example view that shows whether the current user is compliant, and
    lists any missing legal versions. This does not enforce compliance.
    """
    is_compliant, missing_versions = check_user_legal_compliance(request.user)
    return render(
        request,
        "legal_status.html",
        {"is_compliant": is_compliant, "missing_versions": missing_versions},
    )


def logout_view(request):
    """
    Log the user out and redirect to the homepage.
    """
    logout(request)
    return redirect("home")
