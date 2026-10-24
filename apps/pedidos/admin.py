from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, Exists, OuterRef
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.core.admin_utils import IsolamentoVendedorAdmin, badge_status

from .models import Carrinho, ItemCarrinho, ItemPedido, PagamentoSimulado, Pedido, StatusPedido, SubPedido

AVISO_SIMULADO = (
    "Pagamento FICTÍCIO: nenhuma cobrança real, cartão, Pix ou boleto é processado. "
    "A confirmação é manual e serve apenas para registrar o andamento do pedido."
)


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
class MultiplosVendedoresFilter(admin.SimpleListFilter):
    title = "lojas no pedido"
    parameter_name = "lojas"

    def lookups(self, request, model_admin):
        return [("uma", "Uma loja"), ("varias", "Várias lojas")]

    def queryset(self, request, queryset):
        if self.value() == "uma":
            return queryset.filter(_qtd_sub=1)
        if self.value() == "varias":
            return queryset.filter(_qtd_sub__gt=1)
        return queryset


class OrigemPedidoFilter(admin.SimpleListFilter):
    title = "origem"
    parameter_name = "origem"

    def lookups(self, request, model_admin):
        return [("orcamento", "Orçamento aceito"), ("catalogo", "Catálogo")]

    def queryset(self, request, queryset):
        de_orcamento = Exists(ItemPedido.objects.filter(subpedido__pedido=OuterRef("pk"), orcamento__isnull=False))
        if self.value() == "orcamento":
            return queryset.filter(de_orcamento)
        if self.value() == "catalogo":
            return queryset.exclude(de_orcamento)
        return queryset


class TipoEntregaFilter(admin.SimpleListFilter):
    title = "entrega"
    parameter_name = "entrega"

    def lookups(self, request, model_admin):
        return [("fisica", "Com entrega física"), ("digital", "Somente digital")]

    def queryset(self, request, queryset):
        if self.value() == "fisica":
            return queryset.exclude(entrega_logradouro="")
        if self.value() == "digital":
            return queryset.filter(entrega_logradouro="")
        return queryset


class CarrinhoVazioFilter(admin.SimpleListFilter):
    title = "conteúdo"
    parameter_name = "conteudo"

    def lookups(self, request, model_admin):
        return [("vazio", "Vazio"), ("com_itens", "Com itens")]

    def queryset(self, request, queryset):
        if self.value() == "vazio":
            return queryset.filter(_qtd_itens=0)
        if self.value() == "com_itens":
            return queryset.filter(_qtd_itens__gt=0)
        return queryset


# ---------------------------------------------------------------------------
# Inlines somente leitura (histórico comercial não é editável)
# ---------------------------------------------------------------------------
class SomenteLeituraInline:
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ItemPedidoInline(SomenteLeituraInline, admin.TabularInline):
    model = ItemPedido
    fields = ("descricao", "detalhes_variacao", "tipo_produto", "preco_unitario", "quantidade", "subtotal_exibicao", "origem")
    readonly_fields = fields

    @admin.display(description="subtotal")
    def subtotal_exibicao(self, obj):
        return obj.subtotal

    @admin.display(description="origem")
    def origem(self, obj):
        return f"Orçamento #{obj.orcamento_id}" if obj.orcamento_id else "Catálogo"


class PagamentoInline(SomenteLeituraInline, admin.StackedInline):
    model = PagamentoSimulado
    fields = ("valor", "status", "confirmado_por", "confirmado_em", "observacao")
    readonly_fields = fields
    verbose_name_plural = "pagamento simulado (fictício)"


class SubPedidoInline(SomenteLeituraInline, admin.TabularInline):
    model = SubPedido
    fields = ("link", "loja", "status", "subtotal", "pagamento_status")
    readonly_fields = fields
    show_change_link = True

    @admin.display(description="subpedido")
    def link(self, obj):
        return format_html('<a href="{}">#{}</a>', reverse("admin:pedidos_subpedido_change", args=[obj.pk]), obj.pk)

    @admin.display(description="pagamento")
    def pagamento_status(self, obj):
        pagamento = getattr(obj, "pagamento", None)
        return badge_status(pagamento.status, pagamento.get_status_display()) if pagamento else "—"


# ---------------------------------------------------------------------------
# Pedido principal — somente administradores
# ---------------------------------------------------------------------------
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ("id", "comprador", "status_badge", "lojas", "valor_total", "entrega", "criado_em")
    list_display_links = ("id", "comprador")
    list_filter = ("status", MultiplosVendedoresFilter, OrigemPedidoFilter, TipoEntregaFilter, "entrega_uf", "criado_em", "atualizado_em")
    search_fields = ("id", "comprador__username", "comprador__email", "entrega_cidade", "subpedidos__loja__nome")
    list_select_related = ("comprador",)
    date_hierarchy = "criado_em"
    inlines = [SubPedidoInline]
    actions = ("marcar_em_andamento", "marcar_concluido", "marcar_cancelado")
    fieldsets = (
        ("Pedido", {"fields": ("comprador", "status", "valor_total", "criado_em", "atualizado_em")}),
        ("Entrega (cópia do endereço no momento da compra)", {"fields": ("endereco", "endereco_texto")}),
    )
    readonly_fields = ("comprador", "valor_total", "criado_em", "atualizado_em", "endereco", "endereco_texto")

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_qtd_sub=Count("subpedidos", distinct=True))

    def has_add_permission(self, request):
        return False  # pedidos nascem do checkout (Checkpoint 2) ou de orçamento aceito

    def has_delete_permission(self, request, obj=None):
        return False  # histórico comercial é preservado; use o status "Cancelado"

    @admin.display(description="status", ordering="status")
    def status_badge(self, obj):
        return badge_status(obj.status, obj.get_status_display())

    @admin.display(description="lojas", ordering="_qtd_sub")
    def lojas(self, obj):
        return obj._qtd_sub

    @admin.display(description="entrega", boolean=True)
    def entrega(self, obj):
        return obj.possui_entrega

    @admin.display(description="endereço de entrega")
    def endereco_texto(self, obj):
        return format_html_join("", "{}<br>", ((linha,) for linha in obj.endereco_entrega_texto.splitlines()))

    def _marcar(self, request, queryset, status):
        total = queryset.update(status=status)
        self.message_user(request, f"{total} pedido(s) marcado(s) como {status.label}.")

    @admin.action(description="Marcar como Em andamento", permissions=["change"])
    def marcar_em_andamento(self, request, queryset):
        self._marcar(request, queryset, StatusPedido.EM_ANDAMENTO)

    @admin.action(description="Marcar como Concluído", permissions=["change"])
    def marcar_concluido(self, request, queryset):
        self._marcar(request, queryset, StatusPedido.CONCLUIDO)

    @admin.action(description="Marcar como Cancelado", permissions=["change"])
    def marcar_cancelado(self, request, queryset):
        self._marcar(request, queryset, StatusPedido.CANCELADO)


# ---------------------------------------------------------------------------
# Subpedidos — administrador e vendedor responsável
# ---------------------------------------------------------------------------
@admin.register(SubPedido)
class SubPedidoAdmin(IsolamentoVendedorAdmin):
    caminho_vendedor = "loja__vendedor"
    list_display = ("id", "pedido_ref", "loja", "comprador", "status_badge", "subtotal", "pagamento_badge", "criado_em")
    list_display_links = ("id", "pedido_ref")
    list_filter = ("status", "pagamento__status", "criado_em", "atualizado_em")
    filtros_somente_admin = (("loja", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("pedido__id", "loja__nome", "pedido__comprador__username", "pedido__comprador__email")
    list_select_related = ("pedido__comprador", "loja", "pagamento")
    date_hierarchy = "criado_em"
    inlines = [ItemPedidoInline, PagamentoInline]
    actions = ("marcar_em_andamento", "marcar_concluido", "marcar_cancelado")
    fieldsets = (
        ("Subpedido", {"fields": ("pedido_ref", "loja", "status", "subtotal", "criado_em", "atualizado_em")}),
        (
            "Comprador (dados necessários à entrega)",
            {"fields": ("comprador_nome", "comprador_email", "endereco_texto")},
        ),
    )
    readonly_fields = (
        "pedido_ref", "loja", "subtotal", "criado_em", "atualizado_em", "comprador_nome", "comprador_email", "endereco_texto",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="pedido", ordering="pedido_id")
    def pedido_ref(self, obj):
        return f"Pedido #{obj.pedido_id}"

    @admin.display(description="comprador", ordering="pedido__comprador__username")
    def comprador(self, obj):
        return obj.pedido.comprador

    @admin.display(description="nome do comprador")
    def comprador_nome(self, obj):
        return obj.pedido.comprador.get_full_name()

    @admin.display(description="e-mail do comprador")
    def comprador_email(self, obj):
        return obj.pedido.comprador.email

    @admin.display(description="endereço de entrega")
    def endereco_texto(self, obj):
        return format_html_join("", "{}<br>", ((linha,) for linha in obj.pedido.endereco_entrega_texto.splitlines()))

    @admin.display(description="status", ordering="status")
    def status_badge(self, obj):
        return badge_status(obj.status, obj.get_status_display())

    @admin.display(description="pagamento", ordering="pagamento__status")
    def pagamento_badge(self, obj):
        pagamento = getattr(obj, "pagamento", None)
        return badge_status(pagamento.status, pagamento.get_status_display()) if pagamento else "—"

    def _marcar(self, request, queryset, status):
        total = queryset.update(status=status)
        self.message_user(request, f"{total} subpedido(s) marcado(s) como {status.label}.")

    @admin.action(description="Marcar como Em andamento", permissions=["change"])
    def marcar_em_andamento(self, request, queryset):
        self._marcar(request, queryset, StatusPedido.EM_ANDAMENTO)

    @admin.action(description="Marcar como Concluído", permissions=["change"])
    def marcar_concluido(self, request, queryset):
        self._marcar(request, queryset, StatusPedido.CONCLUIDO)

    @admin.action(description="Marcar como Cancelado", permissions=["change"])
    def marcar_cancelado(self, request, queryset):
        self._marcar(request, queryset, StatusPedido.CANCELADO)


# ---------------------------------------------------------------------------
# Pagamentos simulados
# ---------------------------------------------------------------------------
@admin.register(PagamentoSimulado)
class PagamentoSimuladoAdmin(IsolamentoVendedorAdmin):
    caminho_vendedor = "subpedido__loja__vendedor"
    list_display = ("id", "subpedido", "valor", "status_badge", "confirmado_por", "confirmado_em", "criado_em")
    list_filter = ("status", "confirmado_em", "criado_em")
    filtros_somente_admin = (("subpedido__loja", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("subpedido__pedido__id", "subpedido__loja__nome", "subpedido__pedido__comprador__username")
    list_select_related = ("subpedido__loja", "confirmado_por")
    actions = ("confirmar_pagamentos",)
    fieldsets = (
        ("Registro fictício", {"description": AVISO_SIMULADO, "fields": ("subpedido", "valor", "status", "observacao")}),
        ("Confirmação manual", {"fields": ("confirmado_por", "confirmado_em", "criado_em", "atualizado_em")}),
    )
    readonly_fields = ("subpedido", "valor", "status", "confirmado_por", "confirmado_em", "criado_em", "atualizado_em")

    def has_add_permission(self, request):
        return False  # criado junto com o subpedido

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="status", ordering="status")
    def status_badge(self, obj):
        return badge_status(obj.status, obj.get_status_display())

    @admin.action(description="Confirmar pagamento simulado (manual)", permissions=["change"])
    def confirmar_pagamentos(self, request, queryset):
        confirmados = 0
        for pagamento in queryset:
            try:
                pagamento.confirmar(request.user)
                confirmados += 1
            except (ValidationError, PermissionDenied) as erro:
                texto = "; ".join(erro.messages) if isinstance(erro, ValidationError) else str(erro)
                self.message_user(request, f"Pagamento #{pagamento.pk}: {texto}", messages.WARNING)
        if confirmados:
            self.message_user(request, f"{confirmados} pagamento(s) simulado(s) confirmado(s).", messages.SUCCESS)


# ---------------------------------------------------------------------------
# Carrinhos — somente administradores (o comprador usará a interface no CP2)
# ---------------------------------------------------------------------------
class ItemCarrinhoInline(admin.TabularInline):
    model = ItemCarrinho
    extra = 0
    fields = ("produto", "variacao", "quantidade", "preco_unitario_exibicao", "subtotal_exibicao")
    readonly_fields = ("preco_unitario_exibicao", "subtotal_exibicao")
    autocomplete_fields = ("produto",)

    @admin.display(description="preço unitário")
    def preco_unitario_exibicao(self, obj):
        return obj.preco_unitario if obj.pk else "—"

    @admin.display(description="subtotal")
    def subtotal_exibicao(self, obj):
        return obj.subtotal if obj.pk else "—"


@admin.register(Carrinho)
class CarrinhoAdmin(admin.ModelAdmin):
    list_display = ("comprador", "qtd_itens", "total_exibicao", "atualizado_em")
    list_filter = (CarrinhoVazioFilter, "atualizado_em", "criado_em")
    search_fields = ("comprador__username", "comprador__email")
    list_select_related = ("comprador",)
    autocomplete_fields = ("comprador",)
    readonly_fields = ("criado_em", "atualizado_em")
    inlines = [ItemCarrinhoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_qtd_itens=Count("itens"))

    @admin.display(description="itens", ordering="_qtd_itens")
    def qtd_itens(self, obj):
        return obj._qtd_itens

    @admin.display(description="total")
    def total_exibicao(self, obj):
        return obj.total()
