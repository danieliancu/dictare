from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    path("progress/", views.progress, name="progress"),
    path("mistakes/", views.mistakes, name="mistakes"),
    path("progress/streak/", views.streak_badge, name="streak"),
]
