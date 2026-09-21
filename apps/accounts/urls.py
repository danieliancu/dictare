from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.signup, name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("account/", views.account, name="account"),
    path("account/password/", views.PasswordChangeView.as_view(), name="password_change"),
    path("account/verify/resend/", views.resend_verification, name="verify_resend"),
    path("verify-email/<uidb64>/<token>/", views.verify_email, name="verify_email"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/sent/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path(
        "password-reset/<uidb64>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
