from django.conf import settings
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from apps.core.sitemaps import StaticSitemap
from apps.core.views import serve_media

admin.site.site_header = "dictare.ro · administrare"
admin.site.site_title = "dictare.ro admin"
admin.site.index_title = "Conținut și utilizatori"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("sitemap.xml", sitemap, {"sitemaps": {"static": StaticSitemap}}, name="sitemap"),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.practice.urls")),
    path("", include("apps.progress.urls")),
    path("", include("apps.billing.urls")),
]

if settings.DEBUG or settings.SERVE_MEDIA:
    urlpatterns += [path("media/<path:path>", serve_media, name="media")]

handler404 = "apps.core.views.error_404"
handler500 = "apps.core.views.error_500"
