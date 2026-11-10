from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control

from .avatar import generate_avatar


@cache_control(max_age=86400, public=True)
def avatar_view(request, name, size=80):
    size = min(max(int(size), 16), 256)
    png = generate_avatar(name, size)
    return HttpResponse(png, content_type='image/png')


def error_403(request, exception=None):
    return render(request, '403.html', status=403)


def error_404(request, exception=None):
    return render(request, '404.html', status=404)


def error_500(request):
    return render(request, '500.html', status=500)
