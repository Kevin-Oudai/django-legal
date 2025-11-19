from django.urls import path

from . import views

app_name = "django_legal"

urlpatterns = [
    path("accept/", views.acceptance_gate, name="accept"),
    path("<slug:slug>/current/", views.current_version_view, name="current_version"),
]
