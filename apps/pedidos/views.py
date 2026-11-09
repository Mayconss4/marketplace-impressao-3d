from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.catalogo.models import VariacaoProduto
from apps.catalogo.views import produtos_vitrine
from apps.contas.models import Endereco

from .models import Carrinho, ItemCarrinho, Pedido, StatusPedido
from .servicos import cancelar_pedido, finalizar_carrinho, validar_autocompra


def _mensagens_erro(request, erro):
    for mensagem in erro.messages:
        messages.error(request, mensagem)


def _quantidade(request, padrao=1):
    try:
        return max(int(request.POST.get("quantidade", padrao)), 1)
    except (TypeError, ValueError):
        return padrao


# ---------------------------------------------------------------------------
# Carrinho
# ---------------------------------------------------------------------------
@login_required
def carrinho(request):
    carrinho = Carrinho.objects.filter(comprador=request.user).first()
    itens = list(
        carrinho.itens.select_related("produto__loja", "variacao__produto").order_by("produto__loja__nome", "adicionado_em")
    ) if carrinho else []
    contexto = {
        "itens": itens,
        "total": sum((item.subtotal for item in itens), 0),
        "exige_entrega": any(not item.produto.eh_digital for item in itens),
    }
    return render(request, "pedidos/carrinho.html", contexto)


@login_required
@require_POST
def adicionar(request, produto_pk):
    produto = get_object_or_404(produtos_vitrine().select_related("loja__vendedor"), pk=produto_pk)
    variacao = None
    if not produto.eh_digital:
        variacao = VariacaoProduto.objects.filter(produto=produto, pk=request.POST.get("variacao") or 0).first()
    quantidade = 1 if produto.eh_digital else _quantidade(request)
    carrinho, _ = Carrinho.objects.get_or_create(comprador=request.user)

    item = ItemCarrinho.objects.filter(carrinho=carrinho, produto=produto, variacao=variacao).first()
    if item is not None:
        if produto.eh_digital:
            messages.info(request, f"“{produto}” já está no carrinho.")
            return redirect("pedidos:carrinho")
        item.quantidade += quantidade
    else:
        item = ItemCarrinho(carrinho=carrinho, produto=produto, variacao=variacao, quantidade=quantidade)
    try:
        validar_autocompra(request.user, produto)
        item.full_clean()
    except ValidationError as erro:
        _mensagens_erro(request, erro)
        return redirect("catalogo:detalhe", produto.pk)
    item.save()
    messages.success(request, f"“{produto}” adicionado ao carrinho.")
    return redirect("pedidos:carrinho")


@login_required
@require_POST
def atualizar_item(request, pk):
    item = get_object_or_404(ItemCarrinho, pk=pk, carrinho__comprador=request.user)
    if request.POST.get("acao") == "remover":
        item.delete()
        messages.success(request, "Item removido do carrinho.")
        return redirect("pedidos:carrinho")
    item.quantidade = _quantidade(request, item.quantidade)
    try:
        item.full_clean()
    except ValidationError as erro:
        _mensagens_erro(request, erro)
    else:
        item.save()
        messages.success(request, "Quantidade atualizada.")
    return redirect("pedidos:carrinho")


@login_required
def checkout(request):
    carrinho = Carrinho.objects.filter(comprador=request.user).first()
    itens = list(carrinho.itens.select_related("produto__loja", "variacao__produto")) if carrinho else []
    if not itens:
        messages.info(request, "Seu carrinho está vazio.")
        return redirect("pedidos:carrinho")
    exige_entrega = any(not item.produto.eh_digital for item in itens)
    enderecos = request.user.enderecos.all()

    if request.method == "POST":
        endereco = None
        if exige_entrega:
            endereco = Endereco.objects.filter(usuario=request.user, pk=request.POST.get("endereco") or 0).first()
        try:
            pedido = finalizar_carrinho(request.user, endereco)
        except ValidationError as erro:
            _mensagens_erro(request, erro)
        else:
            messages.success(
                request,
                f"Pedido #{pedido.pk} registrado! O pagamento é simulado: cada loja confirma o seu subpedido.",
            )
            return redirect("pedidos:detalhe", pedido.pk)

    lojas = {}
    for item in itens:
        lojas.setdefault(item.produto.loja, []).append(item)
    contexto = {
        "lojas": [(loja, grupo, sum(i.subtotal for i in grupo)) for loja, grupo in lojas.items()],
        "total": sum(item.subtotal for item in itens),
        "exige_entrega": exige_entrega,
        "enderecos": enderecos,
    }
    return render(request, "pedidos/checkout.html", contexto)


# ---------------------------------------------------------------------------
# Pedidos do comprador
# ---------------------------------------------------------------------------
@login_required
def lista(request):
    pedidos = Pedido.objects.filter(comprador=request.user).prefetch_related("subpedidos__loja")
    status = request.GET.get("status", "")
    if status in StatusPedido.values:
        pedidos = pedidos.filter(status=status)
    contexto = {"pedidos": pedidos, "status": status, "opcoes_status": StatusPedido.choices}
    return render(request, "pedidos/lista.html", contexto)


@login_required
def detalhe(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, comprador=request.user)
    subpedidos = pedido.subpedidos.select_related("loja", "pagamento").prefetch_related(
        "itens__produto__arquivos", "itens__orcamento"
    )
    return render(request, "pedidos/detalhe.html", {"pedido": pedido, "subpedidos": subpedidos})


@login_required
@require_POST
def cancelar(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, comprador=request.user)
    try:
        cancelar_pedido(request.user, pedido)
    except ValidationError as erro:
        _mensagens_erro(request, erro)
    else:
        messages.success(request, f"Pedido #{pedido.pk} cancelado. O estoque foi devolvido às lojas.")
    return redirect("pedidos:detalhe", pedido.pk)
