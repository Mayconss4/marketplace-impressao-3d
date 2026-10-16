from django.contrib import admin
from django.db.models import Q

from .models import Categoria, Produto

LIMITE_ESTOQUE_BAIXO = 5


def ids_descendentes(categoria_id):
    """IDs da categoria e de todas as suas subcategorias (qualquer profundidade)."""
    ids, fronteira = {categoria_id}, {categoria_id}
    while fronteira:
        fronteira = set(Categoria.objects.filter(pai_id__in=fronteira).values_list("id", flat=True)) - ids
        ids |= fronteira
    return ids


class CategoriaArvoreFilter(admin.SimpleListFilter):
    """Filtra pela categoria escolhida incluindo suas subcategorias."""

    title = "categoria (com subcategorias)"
    parameter_name = "categoria_arvore"

    def lookups(self, request, model_admin):
        categorias = list(Categoria.objects.select_related("pai"))
        return sorted(((c.pk, c.caminho) for c in categorias), key=lambda par: par[1])

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(categoria_id__in=ids_descendentes(int(self.value())))
        return queryset


class NivelCategoriaFilter(admin.SimpleListFilter):
    title = "nível"
    parameter_name = "nivel"

    def lookups(self, request, model_admin):
        return [("raiz", "Categorias principais"), ("sub", "Subcategorias")]

    def queryset(self, request, queryset):
        if self.value() == "raiz":
            return queryset.filter(pai__isnull=True)
        if self.value() == "sub":
            return queryset.filter(pai__isnull=False)
        return queryset


class EstoqueProdutoFilter(admin.SimpleListFilter):
    """Condição de estoque; depende da anotação ``_estoque`` do ProdutoAdmin."""

    title = "estoque"
    parameter_name = "estoque"

    def lookups(self, request, model_admin):
        return [
            ("ilimitado", "Ilimitado (digital)"),
            ("sem_variacao", "Físico sem variações"),
            ("esgotado", "Esgotado"),
            ("baixo", f"Baixo (1 a {LIMITE_ESTOQUE_BAIXO})"),
            ("disponivel", f"Disponível (> {LIMITE_ESTOQUE_BAIXO})"),
        ]

    def queryset(self, request, queryset):
        fisico = queryset.filter(tipo=Produto.Tipo.FISICO)
        match self.value():
            case "ilimitado":
                return queryset.filter(tipo=Produto.Tipo.DIGITAL)
            case "sem_variacao":
                return fisico.filter(_estoque__isnull=True)
            case "esgotado":
                return fisico.filter(_estoque=0)
            case "baixo":
                return fisico.filter(_estoque__gte=1, _estoque__lte=LIMITE_ESTOQUE_BAIXO)
            case "disponivel":
                return fisico.filter(_estoque__gt=LIMITE_ESTOQUE_BAIXO)
        return queryset


class EstoqueVariacaoFilter(admin.SimpleListFilter):
    title = "estoque"
    parameter_name = "estoque"

    def lookups(self, request, model_admin):
        return [
            ("0", "Esgotado"),
            ("baixo", f"Baixo (1 a {LIMITE_ESTOQUE_BAIXO})"),
            ("ok", f"Disponível (> {LIMITE_ESTOQUE_BAIXO})"),
        ]

    def queryset(self, request, queryset):
        match self.value():
            case "0":
                return queryset.filter(estoque=0)
            case "baixo":
                return queryset.filter(estoque__gte=1, estoque__lte=LIMITE_ESTOQUE_BAIXO)
            case "ok":
                return queryset.filter(estoque__gt=LIMITE_ESTOQUE_BAIXO)
        return queryset


class FaixaPrecoFilter(admin.SimpleListFilter):
    title = "faixa de preço base"
    parameter_name = "preco"
    FAIXAS = {
        "ate50": ("Até R$ 50", Q(preco_base__lte=50)),
        "50a150": ("R$ 50 a R$ 150", Q(preco_base__gt=50, preco_base__lte=150)),
        "acima150": ("Acima de R$ 150", Q(preco_base__gt=150)),
    }

    def lookups(self, request, model_admin):
        return [(chave, rotulo) for chave, (rotulo, _) in self.FAIXAS.items()]

    def queryset(self, request, queryset):
        if self.value() in self.FAIXAS:
            return queryset.filter(self.FAIXAS[self.value()][1])
        return queryset


class DisponibilidadeFilter(admin.SimpleListFilter):
    """Disponível = anúncio ativo em loja ativa."""

    title = "disponibilidade para venda"
    parameter_name = "disponivel"

    def lookups(self, request, model_admin):
        return [("sim", "Disponível"), ("loja_inativa", "Bloqueado: loja inativa"), ("anuncio_inativo", "Anúncio inativo")]

    def queryset(self, request, queryset):
        if self.value() == "sim":
            return queryset.filter(ativo=True, loja__ativa=True)
        if self.value() == "loja_inativa":
            return queryset.filter(loja__ativa=False)
        if self.value() == "anuncio_inativo":
            return queryset.filter(ativo=False)
        return queryset
