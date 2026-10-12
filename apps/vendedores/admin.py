from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count

from apps.core.admin_utils import (
    IsolamentoVendedorAdmin,
    badge_booleano,
    badge_status,
    loja_do_vendedor,
    miniatura,
    perfil_vendedor,
)

from .models import Loja, PerfilVendedor, SolicitacaoVendedor


@admin.register(SolicitacaoVendedor)
class SolicitacaoVendedorAdmin(admin.ModelAdmin):
    """Somente administradores (vendedores não têm permissão neste modelo)."""

    list_display = (
        "id", "usuario", "nome_loja", "tipo_pessoa", "documento_formatado",
        "status_badge", "criado_em", "analisado_por",
    )
    list_display_links = ("id", "usuario")
    list_filter = ("status", "tipo_pessoa", "criado_em", "analisado_em")
    search_fields = ("usuario__username", "usuario__email", "nome_razao_social", "nome_loja", "documento")
    list_select_related = ("usuario", "analisado_por")
    autocomplete_fields = ("usuario",)
    date_hierarchy = "criado_em"
    actions = ("aprovar_solicitacoes", "recusar_solicitacoes")
    fieldsets = (
        ("Solicitante", {"fields": ("usuario",)}),
        ("Dados comerciais", {"fields": ("tipo_pessoa", "documento", "nome_razao_social", "telefone", "nome_loja")}),
        ("Análise", {"fields": ("status", "analisado_por", "analisado_em", "criado_em", "atualizado_em")}),
    )

    def get_readonly_fields(self, request, obj=None):
        analise = ("status", "analisado_por", "analisado_em", "criado_em", "atualizado_em")
        if obj and obj.status != SolicitacaoVendedor.Status.PENDENTE:
            # Solicitação analisada é histórico: nada mais é editável.
            return ("usuario", "tipo_pessoa", "documento", "nome_razao_social", "telefone", "nome_loja") + analise
        if obj:
            return ("usuario",) + analise
        return analise

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="status", ordering="status")
    def status_badge(self, obj):
        return badge_status(obj.status, obj.get_status_display())

    @admin.display(description="CPF/CNPJ", ordering="documento")
    def documento_formatado(self, obj):
        return obj.documento_formatado

    def _analisar(self, request, queryset, metodo, verbo):
        sucesso = 0
        for solicitacao in queryset:
            try:
                getattr(solicitacao, metodo)(request.user)
                sucesso += 1
            except (ValidationError, PermissionDenied) as erro:
                texto = "; ".join(erro.messages) if isinstance(erro, ValidationError) else str(erro)
                self.message_user(request, f"#{solicitacao.pk}: {texto}", messages.ERROR)
        if sucesso:
            self.message_user(request, f"{sucesso} solicitação(ões) {verbo}.", messages.SUCCESS)

    @admin.action(description="Aprovar solicitações selecionadas", permissions=["change"])
    def aprovar_solicitacoes(self, request, queryset):
        self._analisar(request, queryset, "aprovar", "aprovada(s); a conta já pode criar sua loja")

    @admin.action(description="Recusar solicitações selecionadas", permissions=["change"])
    def recusar_solicitacoes(self, request, queryset):
        self._analisar(request, queryset, "recusada(s)")


class LojaPossuiFilter(admin.SimpleListFilter):
    title = "loja"
    parameter_name = "tem_loja"

    def lookups(self, request, model_admin):
        return [("sim", "Com loja"), ("nao", "Ainda sem loja")]

    def queryset(self, request, queryset):
        if self.value() == "sim":
            return queryset.filter(loja__isnull=False)
        if self.value() == "nao":
            return queryset.filter(loja__isnull=True)
        return queryset


@admin.register(PerfilVendedor)
class PerfilVendedorAdmin(IsolamentoVendedorAdmin):
    """Somente leitura: o perfil nasce exclusivamente da aprovação da solicitação."""

    caminho_vendedor = "pk"
    list_display = ("usuario", "nome_razao_social", "tipo_pessoa", "documento", "telefone", "loja", "aprovado_em")
    list_filter = ("solicitacao__tipo_pessoa", LojaPossuiFilter, "aprovado_em")
    search_fields = ("usuario__username", "usuario__email", "solicitacao__nome_razao_social", "solicitacao__documento")
    list_select_related = ("usuario", "solicitacao", "loja")
    fields = ("usuario", "solicitacao", "nome_razao_social", "tipo_pessoa", "documento", "telefone", "aprovado_em")
    readonly_fields = fields

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = admin.ModelAdmin.get_queryset(self, request)
        if request.user.is_superuser:
            return qs
        perfil = perfil_vendedor(request)
        return qs.filter(pk=perfil.pk) if perfil else qs.none()


@admin.register(Loja)
class LojaAdmin(IsolamentoVendedorAdmin):
    caminho_vendedor = "vendedor"
    list_display = ("logo", "nome", "vendedor", "status_badge", "qtd_produtos", "criado_em", "atualizado_em")
    list_display_links = ("logo", "nome")
    list_filter = ("ativa", "vendedor__solicitacao__tipo_pessoa", "criado_em", "atualizado_em")
    search_fields = ("nome", "descricao", "vendedor__usuario__username", "vendedor__solicitacao__nome_razao_social")
    list_select_related = ("vendedor__usuario", "vendedor__solicitacao")
    readonly_fields = ("logo_grande", "criado_em", "atualizado_em")
    actions = ("ativar", "desativar")

    def get_fieldsets(self, request, obj=None):
        identificacao = ("vendedor", "nome", "descricao") if request.user.is_superuser else ("nome", "descricao")
        return (
            ("Identificação", {"fields": identificacao}),
            ("Visual", {"fields": ("logotipo", "logo_grande")}),
            ("Situação", {"fields": ("ativa", "criado_em", "atualizado_em")}),
        )

    def get_readonly_fields(self, request, obj=None):
        if obj and request.user.is_superuser:
            return self.readonly_fields + ("vendedor",)
        return self.readonly_fields

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_qtd_produtos=Count("produtos"))

    def has_add_permission(self, request):
        if not super().has_add_permission(request):
            return False
        if request.user.is_superuser:
            return True
        # Um vendedor aprovado pode ter exatamente uma loja.
        return perfil_vendedor(request) is not None and loja_do_vendedor(request) is None

    def has_delete_permission(self, request, obj=None):
        # Excluir loja apagaria histórico; desative-a. O banco ainda protege (PROTECT).
        return request.user.is_superuser and super().has_delete_permission(request, obj)

    def get_changeform_initial_data(self, request):
        inicial = super().get_changeform_initial_data(request)
        perfil = perfil_vendedor(request)
        if perfil and not request.user.is_superuser:
            inicial.setdefault("nome", perfil.solicitacao.nome_loja)
        return inicial

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "vendedor":
            kwargs["queryset"] = PerfilVendedor.objects.filter(loja__isnull=True).select_related("solicitacao", "usuario")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not change and not request.user.is_superuser:
            obj.vendedor = perfil_vendedor(request)
        super().save_model(request, obj, form, change)

    @admin.display(description="")
    def logo(self, obj):
        return miniatura(obj.logotipo, 36)

    @admin.display(description="pré-visualização")
    def logo_grande(self, obj):
        return miniatura(obj.logotipo, 120)

    @admin.display(description="status", ordering="ativa")
    def status_badge(self, obj):
        return badge_booleano(obj.ativa, "Ativa", "Inativa")

    @admin.display(description="produtos", ordering="_qtd_produtos")
    def qtd_produtos(self, obj):
        return obj._qtd_produtos

    @admin.action(description="Ativar lojas selecionadas", permissions=["change"])
    def ativar(self, request, queryset):
        self.message_user(request, f"{queryset.update(ativa=True)} loja(s) ativada(s).")

    @admin.action(description="Desativar lojas selecionadas (nada é excluído)", permissions=["change"])
    def desativar(self, request, queryset):
        self.message_user(request, f"{queryset.update(ativa=False)} loja(s) desativada(s).")
