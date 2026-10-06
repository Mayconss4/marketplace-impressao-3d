from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Marketplace 3D"
admin.site.site_title = "Marketplace 3D | Administração"
admin.site.index_title = "Painel administrativo"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
]

if settings.DEBUG:
    # Somente a mídia PÚBLICA (imagens e logotipos). A mídia privada nunca é servida aqui.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
