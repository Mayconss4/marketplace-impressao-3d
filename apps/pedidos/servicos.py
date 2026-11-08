"""Operações que criam ou alteram vários registros comerciais de uma vez (sempre atômicas).

``registrar_pedido`` é usado pelo checkout do site (carrinho → pedido) e pelos dados
de demonstração; ``finalizar_carrinho`` e ``cancelar_pedido`` atendem a área do comprador.
"""

from collections import defaultdict

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F

from apps.catalogo.models import Produto, VariacaoProduto
from apps.orcamentos.models import Orcamento

from .models import (
    Carrinho,
    ItemPedido,
    PagamentoSimulado,
    Pedido,
    StatusPedido,
    SubPedido,
    validar_combinacao,
)


def validar_autocompra(comprador, produto):
    """Vendedores não compram da própria loja."""
    if produto.loja.vendedor.usuario_id == comprador.pk:
        raise ValidationError(f"Você não pode comprar '{produto}', pois ele é da sua própria loja.")


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
        produto = Produto.objects.select_related("loja__vendedor").get(pk=produto.pk)
        if not produto.esta_disponivel:
            raise ValidationError(f"O produto '{produto}' não está disponível para compra.")
        validar_autocompra(comprador, produto)
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


@transaction.atomic
def finalizar_carrinho(comprador, endereco=None):
    """Checkout: transforma o carrinho em pedido e o esvazia na mesma transação."""
    carrinho = Carrinho.objects.select_for_update().filter(comprador=comprador).first()
    itens = list(carrinho.itens.select_related("produto", "variacao")) if carrinho else []
    if not itens:
        raise ValidationError("Seu carrinho está vazio.")
    pedido = registrar_pedido(
        comprador, [(item.produto, item.variacao, item.quantidade) for item in itens], endereco
    )
    carrinho.itens.all().delete()
    return pedido


@transaction.atomic
def cancelar_pedido(comprador, pedido):
    """Cancelamento pelo comprador: cancela todos os subpedidos e devolve o estoque.

    Só é permitido enquanto o pedido e todos os subpedidos estão Pendentes e
    nenhum pagamento simulado foi confirmado.
    """
    pedido = Pedido.objects.select_for_update().get(pk=pedido.pk)
    if pedido.comprador_id != comprador.pk:
        raise PermissionDenied("Somente o comprador pode cancelar este pedido.")
    subpedidos = list(pedido.subpedidos.select_related("pagamento"))
    if pedido.status != StatusPedido.PENDENTE or any(s.status != StatusPedido.PENDENTE for s in subpedidos):
        raise ValidationError("Somente pedidos pendentes podem ser cancelados.")
    if any(s.pagamento.status != PagamentoSimulado.Status.PENDENTE for s in subpedidos):
        raise ValidationError("Este pedido já tem pagamento confirmado e não pode ser cancelado.")

    for item in ItemPedido.objects.filter(subpedido__pedido=pedido, variacao__isnull=False):
        VariacaoProduto.objects.filter(pk=item.variacao_id).update(estoque=F("estoque") + item.quantidade)
    pedido.subpedidos.update(status=StatusPedido.CANCELADO)
    pedido.status = StatusPedido.CANCELADO
    pedido.save(update_fields=["status", "atualizado_em"])
    return pedido
