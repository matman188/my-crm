from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme


def return_url(request, default=""):
    candidate = request.POST.get("next") or request.GET.get("next", "")
    if candidate and url_has_allowed_host_and_scheme(
        candidate, {request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return default


def return_to_list(request, name):
    return redirect(return_url(request, reverse(name)))


def record_url(request, name, **kwargs):
    url = reverse(name, kwargs=kwargs)
    destination = return_url(request)
    return url + ("?" + urlencode({"next": destination}) if destination else "")


def list_page(request, queryset, key):
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return {
        key: page.object_list,
        "page_obj": page,
        "pagination_query": params.urlencode(),
    }


def has_permission(user, permission):
    return user.is_superuser or user.has_perm(permission)
