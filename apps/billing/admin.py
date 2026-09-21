from django.contrib import admin

from .models import Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "price_monthly",
        "daily_exercise_limit",
        "natural_level",
        "fast_level",
        "personalized_training",
        "order",
    ]
    list_editable = ["order"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "provider", "current_period_end", "updated_at"]
    list_filter = ["plan", "status", "provider"]
    search_fields = ["user__email", "provider_customer_id", "provider_subscription_id"]
    autocomplete_fields = ["user"]
    list_select_related = ["user", "plan"]
