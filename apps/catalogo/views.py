from django.core.paginator import Paginator
from django.db.models import Case, DecimalField, F, Min, Prefetch, Q, Sum, When
from django.shortcuts import get_object_or_404, render

from apps.vendedores.models import Loja

from .models import Categoria, ImagemProduto, Produto

ORDENACOES = {
    "recentes": ("Mais recentes", "-criado_em"),
    "menor_preco": ("Menor preço", "preco_exibido"),
    "maior_preco": ("Maior preço", "-preco_exibido"),
    "nome": ("Nome (A–Z)", "nome"),
}


def produtos_vitrine():
    """Produtos ofertáveis: ativos, de lojas ativas e (se físicos) com ao menos uma variação."""
    return (
        Produto.objects.disponiveis()
        .select_related("loja", "categoria", "categoria__pai")
        .annotate(menor_ajuste=Min("variacoes__ajuste_preco"), estoque=Sum("variacoes__estoque"))
        .filter(Q(tipo=Produto.Tipo.DIGITAL) | Q(menor_ajuste__isnull=False))
        .annotate(
            preco_exibido=Case(
                When(tipo=Produto.Tipo.DIGITAL, then=F("preco_base")),
                default=F("preco_base") + F("menor_ajuste"),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .prefetch_related(
            Prefetch(
                "imagens",
                queryset=ImagemProduto.objects.order_by("-principal", "ordem", "id"),
                to_attr="imagens_ordenadas",
            )
        )
    )


def com_capa(produtos):
    for produto in produtos:
        produto.capa = produto.imagens_ordenadas[0] if produto.imagens_ordenadas else None
    return produtos


def _ids_com_descendentes(categoria):
    ids, nivel = {categoria.pk}, [categoria.pk]
    while nivel:
        nivel = list(Categoria.objects.filter(pai_id__in=nivel).values_list("pk", flat=True))
        ids.update(nivel)
    return ids


def lista(request):
    produtos = produtos_vitrine()
    filtros = {
        "q": request.GET.get("q", "").strip(),
        "categoria": request.GET.get("categoria", ""),
        "tipo": request.GET.get("tipo", ""),
        "loja": request.GET.get("loja", ""),
        "ordem": request.GET.get("ordem", "recentes"),
    }
    if filtros["q"]:
        produtos = produtos.filter(
            Q(nome__icontains=filtros["q"]) | Q(descricao__icontains=filtros["q"]) | Q(loja__nome__icontains=filtros["q"])
        )
    categoria = Categoria.objects.filter(slug=filtros["categoria"], ativa=True).first()
    if categoria:
        produtos = produtos.filter(categoria_id__in=_ids_com_descendentes(categoria))
    if filtros["tipo"] in Produto.Tipo.values:
        produtos = produtos.filter(tipo=filtros["tipo"])
    loja = Loja.objects.filter(pk=filtros["loja"], ativa=True).first() if filtros["loja"].isdigit() else None
    if loja:
        produtos = produtos.filter(loja=loja)
    _, ordenacao = ORDENACOES.get(filtros["ordem"], ORDENACOES["recentes"])

    pagina = Paginator(produtos.order_by(ordenacao, "pk"), 12).get_page(request.GET.get("pagina"))
    com_capa(pagina.object_list)
    parametros = request.GET.copy()
    parametros.pop("pagina", None)

    contexto = {
        "pagina": pagina,
        "filtros": filtros,
        "categoria": categoria,
        "loja": loja,
        "categorias": Categoria.objects.filter(ativa=True).select_related("pai__pai"),
        "lojas": Loja.objects.filter(ativa=True),
        "tipos": Produto.Tipo.choices,
        "ordenacoes": [(chave, rotulo) for chave, (rotulo, _) in ORDENACOES.items()],
        "parametros": parametros.urlencode(),
    }
    return render(request, "catalogo/lista.html", contexto)


def detalhe(request, pk):
    produto = get_object_or_404(produtos_vitrine(), pk=pk)
    com_capa([produto])
    eh_dono = request.user.is_authenticated and produto.loja.vendedor.usuario_id == request.user.pk
    contexto = {
        "produto": produto,
        "variacoes": produto.variacoes.all(),
        "arquivos": produto.arquivos.all(),
        "eh_dono": eh_dono,
        "relacionados": com_capa(
            produtos_vitrine().filter(categoria=produto.categoria).exclude(pk=produto.pk)[:4]
        ),
    }
    return render(request, "catalogo/detalhe.html", contexto)
