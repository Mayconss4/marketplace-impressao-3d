from django import forms
from django.contrib import admin
from django.utils.html import format_html

from apps.core.admin_utils import IsolamentoVendedorAdmin, badge_status, link_arquivo_privado

from .models import Orcamento

CAMPOS_SOLICITACAO = ("comprador", "vendedor", "arquivo_3d", "quantidade", "material", "cor", "dimensoes", "observacoes")
CAMPOS_PROPOSTA = ("preco_unitario_proposto", "detalhes_proposta")
CAMPOS_SISTEMA = (
    "arquivo_protegido", "valor_total", "respondido_em", "status_badge", "finalizado_em",
    "pedido_link", "criado_em", "atualizado_em",
)


class FormularioRespostaOrcamento(forms.ModelForm):
    class Meta:
        model = Orcamento
        fields = CAMPOS_PROPOSTA

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["preco_unitario_proposto"].required = True
        self.fields["preco_unitario_proposto"].help_text = (
            "Valor por unidade; o total da proposta é este valor × a quantidade solicitada."
        )


class PossuiPedidoFilter(admin.SimpleListFilter):
    title = "pedido gerado"
    parameter_name = "pedido"

    def lookups(self, request, model_admin):
        return [("sim", "Já gerou pedido"), ("nao", "Sem pedido")]

    def queryset(self, request, queryset):
        if self.value() == "sim":
            return queryset.filter(item_pedido__isnull=False)
        if self.value() == "nao":
            return queryset.filter(item_pedido__isnull=True)
        return queryset


@admin.register(Orcamento)
class OrcamentoAdmin(IsolamentoVendedorAdmin):
    """Administrador consulta; o vendedor destinatário responde os pendentes.

    Aceite, recusa e cancelamento são decisões do comprador (área do comprador,
    Checkpoint 2) e passam pelos métodos do modelo, nunca por edição direta.
    """

    caminho_vendedor = "vendedor"
    list_display = (
        "id", "comprador", "loja", "quantidade", "material", "cor", "status_badge",
        "preco_unitario_proposto", "valor_total", "criado_em", "pedido_link",
    )
    list_display_links = ("id", "comprador")
    list_filter = ("status", PossuiPedidoFilter, "criado_em", "respondido_em", "finalizado_em")
    filtros_somente_admin = (("vendedor", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("comprador__username", "comprador__email", "material", "cor", "vendedor__loja__nome", "observacoes")
    list_select_related = ("comprador", "vendedor__loja", "item_pedido__subpedido")
    date_hierarchy = "criado_em"
    autocomplete_fields = ("comprador",)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            return (("Solicitação", {"fields": CAMPOS_SOLICITACAO}),)
        return (
            ("Solicitação do comprador", {"fields": CAMPOS_SOLICITACAO[:2] + ("arquivo_protegido",) + CAMPOS_SOLICITACAO[3:]}),
            ("Proposta comercial", {"fields": CAMPOS_PROPOSTA + ("valor_total", "respondido_em")}),
            ("Situação", {"fields": ("status_badge", "finalizado_em", "pedido_link", "criado_em", "atualizado_em")}),
        )

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ()
        if self._pode_responder(request, obj):
            return CAMPOS_SOLICITACAO + CAMPOS_SISTEMA
        return CAMPOS_SOLICITACAO + CAMPOS_PROPOSTA + CAMPOS_SISTEMA

    def get_form(self, request, obj=None, **kwargs):
        if obj is not None and self._pode_responder(request, obj):
            kwargs["form"] = FormularioRespostaOrcamento
        return super().get_form(request, obj, **kwargs)

    def _pode_responder(self, request, obj):
        perfil = getattr(request.user, "perfil_vendedor", None)
        return (
            perfil is not None
            and obj.vendedor_id == perfil.pk
            and obj.status == Orcamento.Status.PENDENTE
        )

    def has_add_permission(self, request):
        # Orçamentos nascem do comprador; no painel, só o administrador registra (demonstração).
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if obj is None:
            return True
        return self._pode_responder(request, obj)

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if change and self._pode_responder(request, obj):
            obj.responder(request.user, obj.preco_unitario_proposto, obj.detalhes_proposta)
            return
        super().save_model(request, obj, form, change)

    @admin.display(description="loja", ordering="vendedor__loja__nome")
    def loja(self, obj):
        return getattr(obj.vendedor, "loja", obj.vendedor)

    @admin.display(description="status", ordering="status")
    def status_badge(self, obj):
        return badge_status(obj.status, obj.get_status_display())

    @admin.display(description="valor total")
    def valor_total(self, obj):
        return obj.valor_total_proposto or "—"

    @admin.display(description="arquivo 3D")
    def arquivo_protegido(self, obj):
        return link_arquivo_privado(obj.arquivo_3d, obj.nome_arquivo)

    @admin.display(description="pedido")
    def pedido_link(self, obj):
        item = getattr(obj, "item_pedido", None)
        if item is None:
            return "—"
        return format_html("Pedido #{}", item.subpedido.pedido_id)
