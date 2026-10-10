from django.apps import AppConfig
from django.db.models.signals import post_migrate


class VendedoresConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.vendedores"
    verbose_name = "Vendedores e lojas"

    def ready(self):
        from .perfis import sincronizar_grupos

        # Executa após TODAS as migrações, quando as permissões já existem.
        post_migrate.connect(sincronizar_grupos, dispatch_uid="vendedores_sincronizar_grupos")
