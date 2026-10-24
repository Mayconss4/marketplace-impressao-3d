"""Infraestrutura compartilhada pelos ModelAdmins.

``IsolamentoVendedorAdmin`` aplica o isolamento entre vendedores no servidor:
filtra o queryset (listagens, buscas, autocomplete e acesso direto por ID) e
revalida a posse em cada verificação de permissão. Ocultar menus não basta.
"""

from django.contrib import admin
from django.utils.html import format_html


def perfil_vendedor(request):
    return getattr(request.user, "perfil_vendedor", None)


def loja_do_vendedor(request):
    perfil = perfil_vendedor(request)
    return getattr(perfil, "loja", None) if perfil else None


class IsolamentoVendedorAdmin(admin.ModelAdmin):
    #: Caminho ORM do modelo até o ``PerfilVendedor`` dono do registro.
    caminho_vendedor = None

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        perfil = perfil_vendedor(request)
        if perfil is None:
            return qs.none()
        return qs.filter(**{self.caminho_vendedor: perfil})

    def _pertence(self, request, obj):
        if obj is None or request.user.is_superuser:
            return True
        return self.get_queryset(request).filter(pk=obj.pk).exists()

    def has_view_permission(self, request, obj=None):
        return super().has_view_permission(request, obj) and self._pertence(request, obj)

    def has_change_permission(self, request, obj=None):
        return super().has_change_permission(request, obj) and self._pertence(request, obj)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and self._pertence(request, obj)

    #: Filtros exibidos apenas ao administrador (ex.: por loja/vendedor).
    filtros_somente_admin = ()

    def get_list_filter(self, request):
        filtros = list(super().get_list_filter(request))
        if request.user.is_superuser:
            return filtros + list(self.filtros_somente_admin)
        return filtros


CORES_STATUS = {
    "pendente": "warning",
    "aprovada": "success",
    "recusada": "danger",
    "respondido": "info",
    "aceito": "success",
    "recusado": "danger",
    "cancelado": "secondary",
    "em_andamento": "info",
    "concluido": "success",
    "confirmado": "success",
}


def badge_status(valor, rotulo):
    cor = CORES_STATUS.get(valor, "secondary")
    return format_html('<span class="badge badge-{}">{}</span>', cor, rotulo)


def badge_booleano(valor, sim="Ativo", nao="Inativo"):
    return format_html(
        '<span class="badge badge-{}">{}</span>', "success" if valor else "secondary", sim if valor else nao
    )


def miniatura(arquivo, tamanho=48):
    if not arquivo:
        return format_html('<span class="text-muted">—</span>')
    return format_html(
        '<img src="{}" alt="" style="width:{}px;height:{}px;object-fit:cover;border-radius:6px;">',
        arquivo.url,
        tamanho,
        tamanho,
    )


def link_arquivo_privado(arquivo, nome):
    if not arquivo:
        return "—"
    return format_html(
        '<a href="{}"><i class="fas fa-lock"></i> {}</a> <small class="text-muted">(acesso protegido)</small>',
        arquivo.url,
        nome,
    )
