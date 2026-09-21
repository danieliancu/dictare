from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("despre/", views.static_page, {"page": "about"}, name="about"),
    path("contact/", views.static_page, {"page": "contact"}, name="contact"),
    path("confidentialitate/", views.static_page, {"page": "privacy"}, name="privacy"),
    path("termeni/", views.static_page, {"page": "terms"}, name="terms"),
    path("health/", views.health, name="health"),
    path("robots.txt", views.robots_txt, name="robots"),
]
