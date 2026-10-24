"""Operações que criam vários registros comerciais de uma vez (sempre atômicas).

O checkout público (carrinho → pedido) será construído no Checkpoint 2 sobre
``registrar_pedido``; no Checkpoint 1 a função é usada pelos dados de demonstração
e garante as mesmas regras que o checkout precisará respeitar.
"""

from collections import defaultdict

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.catalogo.models import Produto, VariacaoProduto
from apps.orcamentos.models import Orcamento

from .models import ItemPedido, PagamentoSimulado, Pedido, SubPedido, validar_combinacao


def _validar_endereco(comprador, endereco, exige_entrega):
    if endereco is None:
        if exige_entrega:
            raise ValidationError("Selecione um endereço de entrega para os produtos físicos.")
        return
    if endereco.usuario_id != comprador.pk:
        raise ValidationError("O endereço selecionado não pertence ao comprador.")


def _fechar_subpedidos(pedido, subpedidos):
    for subpedido in subpedidos:
        subpedido.recalcular_subtotal()
        PagamentoSimulado.objects.create(subpedido=subpedido, valor=subpedido.subtotal)
    pedido.recalcular_total()


@transaction.atomic
def registrar_pedido(comprador, linhas, endereco=None):
    """Cria pedido, subpedidos por loja, itens com snapshot e pagamentos simulados.

    ``linhas``: iterável de ``(produto, variacao_ou_None, quantidade)``.
    Baixa o estoque das variações com bloqueio de linha.
    """
    linhas = list(linhas)
    if not linhas:
        raise ValidationError("O pedido precisa de ao menos um item.")

    exige_entrega = any(produto.tipo == Produto.Tipo.FISICO for produto, _, _ in linhas)
    _validar_endereco(comprador, endereco, exige_entrega)

    por_loja = defaultdict(list)
    for produto, variacao, quantidade in linhas:
        produto = Produto.objects.select_related("loja").get(pk=produto.pk)
        if not produto.esta_disponivel:
            raise ValidationError(f"O produto '{produto}' não está disponível para compra.")
        if variacao is not None:
            variacao = VariacaoProduto.objects.select_for_update().get(pk=variacao.pk)
        validar_combinacao(produto, variacao, quantidade)
        por_loja[produto.loja].append((produto, variacao, quantidade))

    pedido = Pedido(comprador=comprador)
    if endereco is not None and exige_entrega:
        pedido.copiar_endereco(endereco)
    pedido.save()

    subpedidos = []
    for loja, itens in por_loja.items():
        subpedido = SubPedido.objects.create(pedido=pedido, loja=loja)
        subpedidos.append(subpedido)
        for produto, variacao, quantidade in itens:
            ItemPedido.objects.create(
                subpedido=subpedido,
                produto=produto,
                variacao=variacao,
                tipo_produto=produto.tipo,
                descricao=produto.nome,
                detalhes_variacao=str(variacao) if variacao else "",
                preco_unitario=variacao.preco_final if variacao else produto.preco_base,
                quantidade=quantidade,
            )
            if variacao is not None:
                variacao.estoque -= quantidade
                variacao.save(update_fields=["estoque", "atualizado_em"])

    _fechar_subpedidos(pedido, subpedidos)
    return pedido


@transaction.atomic
def gerar_pedido_de_orcamento(orcamento, endereco):
    """Gera o pedido de um orçamento aceito (sem passar pelo carrinho)."""
    orcamento = Orcamento.objects.select_for_update().select_related("vendedor").get(pk=orcamento.pk)
    if orcamento.status != Orcamento.Status.ACEITO:
        raise ValidationError("Somente orçamentos aceitos geram pedidos.")
    if ItemPedido.objects.filter(orcamento=orcamento).exists():
        raise ValidationError("Este orçamento já gerou um pedido.")
    loja = getattr(orcamento.vendedor, "loja", None)
    if loja is None:
        raise ValidationError("O vendedor ainda não possui loja para receber o pedido.")
    _validar_endereco(orcamento.comprador, endereco, exige_entrega=True)

    pedido = Pedido(comprador=orcamento.comprador)
    pedido.copiar_endereco(endereco)
    pedido.save()
    subpedido = SubPedido.objects.create(pedido=pedido, loja=loja)
    ItemPedido.objects.create(
        subpedido=subpedido,
        orcamento=orcamento,
        tipo_produto=Produto.Tipo.FISICO,
        descricao=f"Impressão personalizada (orçamento #{orcamento.pk})",
        detalhes_variacao=f"{orcamento.material} / {orcamento.cor} / {orcamento.dimensoes}",
        preco_unitario=orcamento.preco_unitario_proposto,
        quantidade=orcamento.quantidade,
    )
    _fechar_subpedidos(pedido, [subpedido])
    return pedido
