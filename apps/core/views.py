from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import render

from apps.catalogo.models import ArquivoDigital, Categoria, Produto
from apps.catalogo.views import com_capa, produtos_vitrine
from apps.orcamentos.models import Orcamento
from apps.pedidos.models import Pedido, StatusPedido, comprou_com_pagamento_confirmado
from apps.vendedores.models import Loja

from .armazenamento import armazenamento_privado


def home(request):
    """Vitrine com produtos disponíveis (ativos, de lojas ativas e compráveis)."""
    contexto = {
        "produtos": com_capa(produtos_vitrine().order_by("-criado_em")[:8]),
        "total_lojas": Loja.objects.filter(ativa=True).count(),
        "total_produtos": Produto.objects.disponiveis().count(),
        "categorias_raiz": Categoria.objects.filter(ativa=True, pai__isnull=True).order_by("nome"),
    }
    return render(request, "core/home.html", contexto)


@login_required
def painel(request):
    """Visão geral da área do usuário final (comprador e, se aprovado, vendedor)."""
    usuario = request.user
    pedidos = Pedido.objects.filter(comprador=usuario)
    orcamentos = Orcamento.objects.filter(comprador=usuario)
    contexto = {
        "pedidos_recentes": pedidos.prefetch_related("subpedidos__loja")[:5],
        "qtd_pedidos_abertos": pedidos.filter(
            status__in=[StatusPedido.PENDENTE, StatusPedido.EM_ANDAMENTO]
        ).count(),
        "qtd_orcamentos_respondidos": orcamentos.filter(status=Orcamento.Status.RESPONDIDO).count(),
        "qtd_orcamentos_abertos": orcamentos.filter(
            status__in=[Orcamento.Status.PENDENTE, Orcamento.Status.RESPONDIDO]
        ).count(),
        "qtd_enderecos": usuario.enderecos.count(),
        "solicitacao": usuario.solicitacoes_vendedor.order_by("-criado_em").first(),
    }
    return render(request, "core/painel.html", contexto)


def _pode_acessar_arquivo(usuario, nome):
    """Decide o acesso a um arquivo privado pelo registro que o referencia."""
    perfil = getattr(usuario, "perfil_vendedor", None)

    arquivo = ArquivoDigital.objects.select_related("produto__loja").filter(arquivo=nome).first()
    if arquivo is not None:
        if usuario.is_superuser:
            return True
        if perfil is not None and arquivo.produto.loja.vendedor_id == perfil.pk:
            return True
        # Comprador: liberado após a confirmação do pagamento simulado do subpedido.
        return comprou_com_pagamento_confirmado(usuario, arquivo.produto_id)

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
