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
    path("", include("apps.contas.urls")),
    path("", include("apps.vendedores.urls")),
    path("", include("apps.pedidos.urls")),
    path("produtos/", include("apps.catalogo.urls")),
    path("minha-conta/orcamentos/", include("apps.orcamentos.urls")),
]

if settings.DEBUG:
    # Somente a mídia PÚBLICA (imagens e logotipos). A mídia privada nunca é servida aqui.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
