from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    allowed_roles = set(roles)

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(request, *args, **kwargs):
            profile = getattr(request.user, "procurement_profile", None)
            if (
                profile is None
                or not profile.is_active
                or profile.role not in allowed_roles
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


def has_role(user, *roles):
    profile = getattr(user, "procurement_profile", None)
    return (
        user.is_authenticated
        and profile is not None
        and profile.is_active
        and profile.role in set(roles)
    )
