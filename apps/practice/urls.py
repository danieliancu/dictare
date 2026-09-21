from django.urls import path

from . import views

app_name = "practice"

urlpatterns = [
    path("practice/", views.hub, name="hub"),
    path("practice/daily/", views.daily, name="daily"),
    path("practice/personalized/", views.start_personalized, name="personalized"),
    path("practice/topic/<slug:slug>/", views.start_topic, name="topic"),
    path("practice/pattern/<slug:slug>/", views.start_pattern, name="pattern"),
    path("practice/session/<uuid:session_id>/", views.session_view, name="session"),
    path("practice/attempt/<uuid:attempt_id>/check/", views.check, name="check"),
    path("practice/attempt/<uuid:attempt_id>/reveal/", views.reveal, name="reveal"),
    path("practice/attempt/<uuid:attempt_id>/level/", views.change_level, name="level"),
    path("practice/attempt/<uuid:attempt_id>/listen/", views.listen, name="listen"),
    path("practice/attempt/<uuid:attempt_id>/speech/", views.speech_text, name="speech"),
]
