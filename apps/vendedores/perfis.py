"""Grupos e permissões dos perfis funcionais.

* Administrador: ``is_superuser`` (controle integral).
* Vendedor: membro do grupo ``Vendedores`` + ``PerfilVendedor`` (criado na aprovação).
* Comprador: qualquer conta ativa; não acessa o Django Admin (``is_staff=False``).

As permissões do grupo apenas dizem QUAIS modelos o vendedor pode tocar. QUAIS
registros ele enxerga é decidido pelo isolamento implementado nos ModelAdmins.
"""

from django.contrib.auth.models import Group, Permission

GRUPO_VENDEDORES = "Vendedores"

PERMISSOES_VENDEDOR = {
    "vendedores": {"loja": ["view", "add", "change"], "perfilvendedor": ["view"]},
    "catalogo": {
        "categoria": ["view"],
        "produto": ["view", "add", "change", "delete"],
        "variacaoproduto": ["view", "add", "change", "delete"],
        "imagemproduto": ["view", "add", "change", "delete"],
        "arquivodigital": ["view", "add", "change", "delete"],
    },
    "orcamentos": {"orcamento": ["view", "change"]},
    "pedidos": {
        "subpedido": ["view", "change"],
        "itempedido": ["view"],
        "pagamentosimulado": ["view", "change"],
    },
}


def obter_grupo_vendedores():
    grupo, _ = Group.objects.get_or_create(name=GRUPO_VENDEDORES)
    return grupo


def sincronizar_grupos(sender=None, **kwargs):
    """Cria/atualiza o grupo de vendedores de forma idempotente (post_migrate)."""
    codenames = [
        (app, f"{acao}_{modelo}")
        for app, modelos in PERMISSOES_VENDEDOR.items()
        for modelo, acoes in modelos.items()
        for acao in acoes
    ]
    permissoes = [
        p
        for p in Permission.objects.select_related("content_type").filter(
            content_type__app_label__in=PERMISSOES_VENDEDOR.keys()
        )
        if (p.content_type.app_label, p.codename) in codenames
    ]
    if len(permissoes) < len(codenames):
        # Alguma app ainda não foi migrada; o próximo post_migrate completa o grupo.
        return
    obter_grupo_vendedores().permissions.set(permissoes)
