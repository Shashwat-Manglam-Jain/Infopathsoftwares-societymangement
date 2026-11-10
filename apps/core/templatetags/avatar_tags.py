from django import template
from django.utils.html import format_html

register = template.Library()


def _fallback_url(name, size):
    return f'/avatar/{name}/{size}/'


@register.simple_tag
def avatar(user, size=40, css_class=''):
    px = int(size)
    name = ''
    src = ''

    if hasattr(user, 'get_full_name'):
        name = user.get_full_name() or getattr(user, 'username', '')
    elif hasattr(user, 'name'):
        name = user.name
    else:
        name = str(user)

    fallback = _fallback_url(name or 'U', px)
    has_photo = False

    if hasattr(user, 'profile_photo') and user.profile_photo:
        src = user.profile_photo.url
        has_photo = True
    elif hasattr(user, 'photo') and user.photo:
        src = user.photo.url
        has_photo = True

    if not has_photo:
        src = fallback

    return format_html(
        '<img src="{}" alt="{}" width="{}" height="{}" '
        'class="rounded-full object-cover {}" '
        'onerror="this.onerror=null;this.src=\'{}\';" loading="lazy">',
        src,
        name,
        px,
        px,
        css_class,
        fallback,
    )


@register.simple_tag
def avatar_url(user, size=40):
    name = ''
    if hasattr(user, 'profile_photo') and user.profile_photo:
        return user.profile_photo.url
    if hasattr(user, 'photo') and user.photo:
        return user.photo.url

    if hasattr(user, 'get_full_name'):
        name = user.get_full_name() or getattr(user, 'username', '')
    elif hasattr(user, 'name'):
        name = user.name
    else:
        name = str(user)

    return _fallback_url(name or 'U', int(size))
