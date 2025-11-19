"""
URL configuration for test_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.contrib import admin
from django.urls import include, path

from .views import home, legal_ok, legal_status, logout_view

urlpatterns = [
    path("", home, name="home"),
    path("logout/", logout_view, name="logout"),
    path("accounts/logout/", logout_view, name="logout"),
    path("legal/ok/", legal_ok, name="legal_ok"),
    path("legal/status/", legal_status, name="legal_status"),
    path("accounts/", include("django.contrib.auth.urls")),
    path("legal/", include("django_legal.urls")),
    path("admin/", admin.site.urls),
]
