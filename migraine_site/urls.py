"""
URL configuration for migraine_site project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.i18n import i18n_patterns
from django.shortcuts import redirect
from django.conf import settings as django_settings


def root_redirect(request):
    lang_cookie = request.COOKIES.get(django_settings.LANGUAGE_COOKIE_NAME, "")
    supported = {code for code, _ in django_settings.LANGUAGES}
    lang = lang_cookie if lang_cookie in supported else django_settings.LANGUAGE_CODE
    return redirect(f"/{lang}/")

def legacy_redirect(request):
    lang_cookie = request.COOKIES.get(django_settings.LANGUAGE_COOKIE_NAME, "")
    supported = {code for code, _ in django_settings.LANGUAGES}
    lang = lang_cookie if lang_cookie in supported else django_settings.LANGUAGE_CODE
    return redirect(f"/{lang}/")

urlpatterns = [
    path("", root_redirect, name="root_redirect"),
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("log/", legacy_redirect, name="legacy_log_redirect"),
    path("profile/", legacy_redirect, name="legacy_profile_redirect"),
]

urlpatterns += i18n_patterns(
    path("", include("tracker.urls")),
)
