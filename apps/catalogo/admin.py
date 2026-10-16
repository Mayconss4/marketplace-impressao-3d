from django import forms
from django.contrib import admin
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.db.models import Case, Count, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from apps.core.admin_utils import (
    IsolamentoVendedorAdmin,
    badge_booleano,
    link_arquivo_privado,
    loja_do_vendedor,
    miniatura,
)

from .filtros import (
    CategoriaArvoreFilter,
    DisponibilidadeFilter,
    EstoqueProdutoFilter,
    EstoqueVariacaoFilter,
    FaixaPrecoFilter,
    NivelCategoriaFilter,
)
from .models import ArquivoDigital, Categoria, ImagemProduto, Produto, VariacaoProduto


# ---------------------------------------------------------------------------
# Categorias (somente administradores alteram; vendedores apenas consultam)
# ---------------------------------------------------------------------------
class ArvoreCategoriaChangeList(ChangeList):
    """Ordena a listagem pelas chaves de árvore anotadas em CategoriaAdmin.get_queryset."""

    def _get_default_ordering(self):
        return ["_k1", "_k2", "_k3"]


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("arvore", "slug", "status_badge", "qtd_subcategorias", "qtd_produtos", "atualizado_em")
    list_filter = (NivelCategoriaFilter, "ativa", ("pai", admin.RelatedOnlyFieldListFilter), "criado_em", "atualizado_em")
    search_fields = ("nome", "slug", "pai__nome")
    prepopulated_fields = {"slug": ("nome",)}
    list_select_related = ("pai__pai",)
    autocomplete_fields = ("pai",)
    fields = ("nome", "slug", "pai", "ativa")

    def get_queryset(self, request):
        # Chaves de ordenação que exibem a árvore (raiz → filha → neta) em sequência.
        tem_avo = Q(pai__pai__isnull=False)
        tem_pai = Q(pai__isnull=False)
        qs = (
            super()
            .get_queryset(request)
            .annotate(
                _qtd_sub=Count("subcategorias", distinct=True),
                _qtd_prod=Count("produtos", distinct=True),
                _k1=Coalesce("pai__pai__nome", "pai__nome", "nome"),
                _k2=Case(When(tem_avo, then=F("pai__nome")), When(tem_pai, then=F("nome")), default=Value("")),
                _k3=Case(When(tem_avo, then=F("nome")), default=Value("")),
            )
        )
        # Vendedores só enxergam (e escolhem) categorias ativas.
        return qs if request.user.is_superuser else qs.filter(ativa=True)

    def get_changelist(self, request, **kwargs):
        return ArvoreCategoriaChangeList

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    @admin.display(description="categoria")
    def arvore(self, obj):
        nivel = obj.nivel
        prefixo = "↳ " if nivel else ""
        return format_html('<span style="padding-left:{}rem">{}{}</span> <small class="text-muted">{}</small>',
                           nivel * 1.5, prefixo, obj.nome, obj.caminho if nivel else "")

    @admin.display(description="status", ordering="ativa")
    def status_badge(self, obj):
        return badge_booleano(obj.ativa, "Ativa", "Inativa")

    @admin.display(description="subcategorias", ordering="_qtd_sub")
    def qtd_subcategorias(self, obj):
        return obj._qtd_sub

    @admin.display(description="produtos", ordering="_qtd_prod")
    def qtd_produtos(self, obj):
        return obj._qtd_prod


# ---------------------------------------------------------------------------
# Inlines de produto
# ---------------------------------------------------------------------------
class ImagemFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        principais = sum(
            1
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE") and form.cleaned_data.get("principal")
        )
        if principais > 1:
            raise ValidationError("Marque apenas uma imagem como principal.")


class ImagemProdutoInline(admin.TabularInline):
    model = ImagemProduto
    formset = ImagemFormSet
    extra = 0
    fields = ("previa", "imagem", "texto_alternativo", "principal", "ordem")
    readonly_fields = ("previa",)
    classes = ("inline-imagens",)

    @admin.display(description="prévia")
    def previa(self, obj):
        return miniatura(obj.imagem, 64) if obj.pk else "—"


class VariacaoFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        vistas = set()
        for form in self.forms:
            dados = form.cleaned_data
            if not dados or dados.get("DELETE"):
                continue
            chave = tuple((dados.get(c) or "").strip().lower() for c in ("material", "cor", "dimensoes"))
            if chave in vistas:
                raise ValidationError("Há variações repetidas (mesmo material, cor e dimensão) neste envio.")
            vistas.add(chave)


class VariacaoProdutoInline(admin.TabularInline):
    model = VariacaoProduto
    formset = VariacaoFormSet
    extra = 0
    fields = ("material", "cor", "dimensoes", "ajuste_preco", "preco_final_exibicao", "estoque")
    readonly_fields = ("preco_final_exibicao",)
    classes = ("inline-variacoes",)

    @admin.display(description="preço final")
    def preco_final_exibicao(self, obj):
        return f"R$ {obj.preco_final}" if obj.pk else "—"


class ArquivoDigitalInline(admin.TabularInline):
    model = ArquivoDigital
    extra = 0
    fields = ("arquivo", "descricao", "formato", "link_protegido")
    readonly_fields = ("formato", "link_protegido")
    classes = ("inline-arquivos",)
    verbose_name_plural = "arquivos digitais (privados — STL, 3MF, OBJ, STEP)"

    @admin.display(description="download")
    def link_protegido(self, obj):
        return link_arquivo_privado(obj.arquivo, obj.nome_arquivo) if obj.pk else "—"


# ---------------------------------------------------------------------------
# Produtos
# ---------------------------------------------------------------------------
@admin.register(Produto)
class ProdutoAdmin(IsolamentoVendedorAdmin):
    caminho_vendedor = "loja__vendedor"
    list_display = (
        "capa", "nome", "loja", "categoria", "tipo", "preco_base", "estoque_exibicao", "status_badge", "atualizado_em",
    )
    list_display_links = ("capa", "nome")
    list_filter = (
        "tipo", "ativo", DisponibilidadeFilter, EstoqueProdutoFilter, CategoriaArvoreFilter, FaixaPrecoFilter,
        "criado_em", "atualizado_em",
    )
    filtros_somente_admin = (("loja", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("nome", "descricao", "loja__nome", "categoria__nome")
    list_select_related = ("loja", "categoria__pai")
    autocomplete_fields = ("categoria",)
    readonly_fields = ("criado_em", "atualizado_em")
    actions = ("ativar_anuncios", "desativar_anuncios")
    list_per_page = 25

    class Media:
        js = ("js/produto_tipo.js",)

    def get_fieldsets(self, request, obj=None):
        identificacao = ("loja", "nome", "categoria") if request.user.is_superuser else ("nome", "categoria")
        return (
            ("Identificação", {"fields": identificacao + ("descricao",)}),
            (
                "Comercial",
                {
                    "fields": ("tipo", "preco_base", "ativo"),
                    "description": "Físico: preço final = preço base + ajuste da variação; estoque por variação. "
                    "Digital: sem variações, estoque ilimitado, arquivos privados.",
                },
            ),
            ("Registro", {"classes": ("collapse",), "fields": ("criado_em", "atualizado_em")}),
        )

    def get_inlines(self, request, obj):
        if obj is None:
            # Na criação, o script produto_tipo.js mostra apenas o inline compatível com o tipo.
            return [ImagemProdutoInline, VariacaoProdutoInline, ArquivoDigitalInline]
        if obj.eh_digital:
            return [ImagemProdutoInline, ArquivoDigitalInline]
        return [ImagemProdutoInline, VariacaoProdutoInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_estoque=Sum("variacoes__estoque"))

    def has_add_permission(self, request):
        if not super().has_add_permission(request):
            return False
        return request.user.is_superuser or loja_do_vendedor(request) is not None

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "categoria" and not request.user.is_superuser:
            kwargs["queryset"] = Categoria.objects.filter(ativa=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            # O vendedor nunca escolhe a loja: ela é sempre a sua.
            obj.loja = loja_do_vendedor(request)
        super().save_model(request, obj, form, change)

    @admin.display(description="")
    def capa(self, obj):
        imagem = obj.imagem_principal()
        return miniatura(imagem.imagem if imagem else None, 40)

    @admin.display(description="estoque", ordering="_estoque")
    def estoque_exibicao(self, obj):
        if obj.eh_digital:
            return format_html('<span class="badge badge-info">∞ ilimitado</span>')
        if obj._estoque is None:
            return format_html('<span class="badge badge-warning">sem variações</span>')
        cor = "danger" if obj._estoque == 0 else "warning" if obj._estoque <= 5 else "success"
        return format_html('<span class="badge badge-{}">{}</span>', cor, obj._estoque)

    @admin.display(description="anúncio", ordering="ativo")
    def status_badge(self, obj):
        return badge_booleano(obj.ativo)

    @admin.action(description="Ativar anúncios selecionados", permissions=["change"])
    def ativar_anuncios(self, request, queryset):
        self.message_user(request, f"{queryset.update(ativo=True)} anúncio(s) ativado(s).")

    @admin.action(description="Desativar anúncios selecionados", permissions=["change"])
    def desativar_anuncios(self, request, queryset):
        self.message_user(request, f"{queryset.update(ativo=False)} anúncio(s) desativado(s).")


@admin.register(VariacaoProduto)
class VariacaoProdutoAdmin(IsolamentoVendedorAdmin):
    """Visão consolidada de estoque das variações (também editáveis no produto)."""

    caminho_vendedor = "produto__loja__vendedor"
    list_display = ("produto", "material", "cor", "dimensoes", "ajuste_preco", "preco_final_exibicao", "estoque")
    list_editable = ("estoque",)
    list_filter = (EstoqueVariacaoFilter, "material", "cor", "atualizado_em")
    filtros_somente_admin = (("produto__loja", admin.RelatedOnlyFieldListFilter),)
    search_fields = ("produto__nome", "material", "cor", "dimensoes")
    list_select_related = ("produto__loja",)
    fields = ("produto", "material", "cor", "dimensoes", "ajuste_preco", "estoque")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "produto":
            produtos = Produto.objects.filter(tipo=Produto.Tipo.FISICO).select_related("loja")
            if not request.user.is_superuser:
                loja = loja_do_vendedor(request)
                produtos = produtos.filter(loja=loja) if loja else produtos.none()
            kwargs["queryset"] = produtos
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        if not super().has_add_permission(request):
            return False
        return request.user.is_superuser or loja_do_vendedor(request) is not None

    @admin.display(description="preço final")
    def preco_final_exibicao(self, obj):
        return obj.preco_final
