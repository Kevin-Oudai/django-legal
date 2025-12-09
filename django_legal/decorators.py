from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect

from .conf import get_legal_acceptance_url
from .models import check_user_legal_compliance


def legal_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        user = getattr(request, "user", None)

        # Authentication is assumed to be handled elsewhere; if the user
        # is not authenticated, fall back to the original view.
        if user is None or not user.is_authenticated:
            return view_func(request, *args, **kwargs)

        is_compliant, _missing_versions = check_user_legal_compliance(user)
        if is_compliant:
            return view_func(request, *args, **kwargs)

        acceptance_url = get_legal_acceptance_url()
        next_param = urlencode({"next": request.get_full_path()})
        separator = "&" if "?" in acceptance_url else "?"

        return redirect(f"{acceptance_url}{separator}{next_param}")

    return _wrapped
