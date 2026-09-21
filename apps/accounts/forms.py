from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm, SetPasswordForm

from apps.listening.models import Accent

from .models import Profile, User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True})
    )
    error_messages = {
        "invalid_login": "Email sau parolă incorectă.",
        "inactive": "Acest cont este dezactivat.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class SignupForm(forms.ModelForm):
    first_name = forms.CharField(
        label="Prenume",
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    email = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )
    password = forms.CharField(
        label="Parolă",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text="Minimum 8 caractere, nu doar cifre.",
    )

    class Meta:
        model = User
        fields = ["first_name", "email"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Există deja un cont cu acest email.")
        return email

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            user = User(email=cleaned.get("email", ""), first_name=cleaned.get("first_name", ""))
            try:
                password_validation.validate_password(password, user)
            except forms.ValidationError as exc:
                self.add_error("password", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Prenume", max_length=60, required=False)

    class Meta:
        model = Profile
        fields = ["preferred_voice", "timezone", "daily_goal", "preferred_accent"]
        widgets = {"daily_goal": forms.NumberInput(attrs={"min": 3, "max": 50})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if user is not None:
            self.fields["first_name"].initial = user.first_name
        self.fields["preferred_accent"].queryset = Accent.objects.filter(active=True)
        self.fields["preferred_accent"].empty_label = "Implicit (Standard Southern British)"
        self.order_fields(
            ["first_name", "preferred_voice", "timezone", "daily_goal", "preferred_accent"]
        )

    def clean_daily_goal(self):
        goal = self.cleaned_data["daily_goal"]
        if not 3 <= goal <= 50:
            raise forms.ValidationError("Alege între 3 și 50 de exerciții pe zi.")
        return goal

    def save(self, commit=True):
        profile = super().save(commit=commit)
        if self.user is not None:
            self.user.first_name = self.cleaned_data.get("first_name", "")
            self.user.save(update_fields=["first_name"])
        return profile


class StyledPasswordResetForm(PasswordResetForm):
    email = forms.EmailField(
        label="Email", max_length=254, widget=forms.EmailInput(attrs={"autocomplete": "email"})
    )


class StyledSetPasswordForm(SetPasswordForm):
    pass
