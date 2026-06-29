from django.shortcuts import redirect

from flights.utils.commander import user_is_commander, user_is_commander_only


class CommanderAccessMiddleware:
    """Командиры работают в /commander/, полная админка им недоступна."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated:
            path = request.path
            if user_is_commander_only(user) and path.startswith('/admin/'):
                return redirect('/commander/')
            if (
                path.startswith('/commander/')
                and not path.startswith('/commander/login')
                and not user_is_commander(user)
            ):
                if user.is_staff or user.is_superuser:
                    return redirect('/admin/')
                return redirect('/login/?next=/commander/')
        return self.get_response(request)
