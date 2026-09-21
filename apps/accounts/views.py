from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.encoding import force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode
from django.views.decorators.http import require_POST

from apps.billing.services.entitlements import get_entitlements
from apps.core.ratelimit import rate_limit

from .forms import (
    EmailAuthenticationForm,
    ProfileForm,
    SignupForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .services import send_verification_email
from .tokens import email_verification_token


def _safe_next(request, fallback: str = "practice:hub"):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return fallback


@rate_limit("signup", limit=10, window=3600)
def signup(request):
    if request.user.is_authenticated:
        return redirect("practice:hub")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        send_verification_email(user)
        messages.success(
            request, "Contul a fost creat. Ți-am trimis un email pentru confirmarea adresei."
        )
        return redirect(_safe_next(request))
    return render(
        request, "pages/accounts/signup.html", {"form": form, "next": _safe_next(request, "")}
    )


@method_decorator(rate_limit("login", limit=10, window=300), name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "pages/accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class LogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("core:home")


@method_decorator(rate_limit("password_reset", limit=5, window=3600), name="dispatch")
class PasswordResetView(auth_views.PasswordResetView):
    template_name = "pages/accounts/password_reset.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy("accounts:password_reset_done")


class PasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = "pages/accounts/password_reset_done.html"


class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "pages/accounts/password_reset_confirm.html"
    form_class = StyledSetPasswordForm
    success_url = reverse_lazy("accounts:password_reset_complete")


class PasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = "pages/accounts/password_reset_complete.html"


@method_decorator(login_required, name="dispatch")
class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "pages/accounts/password_change.html"
    success_url = reverse_lazy("accounts:account")

    def form_valid(self, form):
        messages.success(self.request, "Parola a fost schimbată.")
        return super().form_valid(form)


def verify_email(request, uidb64: str, token: str):
    User = get_user_model()
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    ok = user is not None and email_verification_token.check_token(user, token)
    if ok:
        user.email_verified = True
        user.save(update_fields=["email_verified"])
    return render(request, "pages/accounts/verify_email.html", {"ok": ok})


@login_required
@require_POST
@rate_limit("verify_resend", limit=3, window=3600)
def resend_verification(request):
    if not request.user.email_verified:
        send_verification_email(request.user)
        messages.success(request, "Ți-am retrimis emailul de confirmare.")
    return redirect("accounts:account")


@login_required
def account(request):
    profile = request.user.profile
    form = ProfileForm(request.POST or None, instance=profile, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profilul a fost salvat.")
        return redirect("accounts:account")
    return render(
        request,
        "pages/accounts/account.html",
        {"form": form, "entitlements": get_entitlements(request.user)},
    )
