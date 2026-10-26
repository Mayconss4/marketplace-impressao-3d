from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Min, Prefetch, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import render

from apps.catalogo.models import Categoria, ImagemProduto, Produto
from apps.vendedores.models import Loja

from .armazenamento import armazenamento_privado


def home(request):
    """Vitrine com produtos disponíveis (ativos, de lojas ativas e compráveis)."""
    produtos = (
        Produto.objects.disponiveis()
        .select_related("loja", "categoria", "categoria__pai")
        .annotate(menor_ajuste=Min("variacoes__ajuste_preco"), estoque=Sum("variacoes__estoque"))
        # Produto físico só é ofertado quando possui ao menos uma variação.
        .filter(Q(tipo=Produto.Tipo.DIGITAL) | Q(menor_ajuste__isnull=False))
        .prefetch_related(
            Prefetch(
                "imagens",
                queryset=ImagemProduto.objects.order_by("-principal", "ordem", "id"),
                to_attr="imagens_ordenadas",
            )
        )
        .order_by("-criado_em")[:12]
    )
    for produto in produtos:
        produto.preco_exibido = (
            produto.preco_base
            if produto.eh_digital
            else produto.preco_base + produto.menor_ajuste
        )
        produto.capa = produto.imagens_ordenadas[0] if produto.imagens_ordenadas else None

    contexto = {
        "produtos": produtos,
        "total_lojas": Loja.objects.filter(ativa=True).count(),
        "total_produtos": Produto.objects.disponiveis().count(),
        "categorias_raiz": Categoria.objects.filter(ativa=True, pai__isnull=True).order_by("nome"),
    }
    return render(request, "core/home.html", contexto)


def _pode_acessar_arquivo(usuario, nome):
    """Decide o acesso a um arquivo privado pelo registro que o referencia."""
    from apps.catalogo.models import ArquivoDigital
    from apps.orcamentos.models import Orcamento

    perfil = getattr(usuario, "perfil_vendedor", None)

    arquivo = ArquivoDigital.objects.select_related("produto__loja").filter(arquivo=nome).first()
    if arquivo is not None:
        if usuario.is_superuser:
            return True
        # Liberação ao comprador após a conclusão da compra: Checkpoint 2.
        return perfil is not None and arquivo.produto.loja.vendedor_id == perfil.pk

    orcamento = Orcamento.objects.filter(arquivo_3d=nome).first()
    if orcamento is not None:
        return (
            usuario.is_superuser
            or orcamento.comprador_id == usuario.pk
            or (perfil is not None and orcamento.vendedor_id == perfil.pk)
        )

    raise Http404("Arquivo não encontrado.")


@login_required
def arquivo_privado(request, nome):
    if not _pode_acessar_arquivo(request.user, nome):
        raise PermissionDenied("Você não tem permissão para acessar este arquivo.")
    if not armazenamento_privado.exists(nome):
        raise Http404("Arquivo não encontrado.")
    return FileResponse(
        armazenamento_privado.open(nome, "rb"), as_attachment=True, filename=Path(nome).name
    )
