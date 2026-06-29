# middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required

class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and request.path not in [
            reverse('login'),
            reverse('logout'),
        ]:
            return redirect('login')
        return self.get_response(request)