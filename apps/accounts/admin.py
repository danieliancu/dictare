from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    fields = ["timezone", "daily_goal", "preferred_accent"]


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = [
        "email",
        "first_name",
        "email_verified",
        "is_staff",
        "is_active",
        "date_joined",
        "last_login",
    ]
    list_filter = ["is_staff", "is_superuser", "is_active", "email_verified"]
    search_fields = ["email", "first_name", "last_name"]
    inlines = [ProfileInline]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Date personale", {"fields": ["first_name", "last_name", "email_verified"]}),
        (
            "Permisiuni",
            {"fields": ["is_active", "is_staff", "is_superuser", "groups", "user_permissions"]},
        ),
        ("Date importante", {"fields": ["last_login", "date_joined"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "password1", "password2"]}),
    ]
