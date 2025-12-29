from django.urls import path
from . import views

app_name = "tracker"

urlpatterns = [
    path("", views.home, name="home"),
    path("log/", views.log_day, name="log"),
    path("log/<int:pk>/edit/", views.edit_log, name="edit_log"),
    path("log/<int:pk>/delete/", views.delete_log, name="delete_log"),
    path("profile/", views.profile, name="profile"),
]
