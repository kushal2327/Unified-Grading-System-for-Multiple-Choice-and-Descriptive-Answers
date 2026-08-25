from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.authentication.urls")),
    path("api/", include("apps.descriptive_grading.urls")),
    path("api/", include("apps.manual_review.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Serve frontend SPA for all non-API routes
urlpatterns += [
    re_path(r"^(?!api/|admin/|media/|static/).*$", TemplateView.as_view(template_name="index.html"), name="frontend"),
]
