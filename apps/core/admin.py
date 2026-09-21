from django.contrib import admin

from .models import Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ["author_name", "location", "short_quote", "active", "order"]
    list_editable = ["active", "order"]
    search_fields = ["author_name", "quote"]

    @admin.display(description="Citat")
    def short_quote(self, obj):
        return obj.quote[:80]
