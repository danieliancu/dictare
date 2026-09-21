from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticSitemap(Sitemap):
    changefreq = "weekly"

    def items(self):
        return [
            "core:home",
            "billing:pricing",
            "practice:hub",
            "core:about",
            "core:contact",
            "core:privacy",
            "core:terms",
        ]

    def priority(self, item):
        return 1.0 if item == "core:home" else 0.6

    def location(self, item):
        return reverse(item)
