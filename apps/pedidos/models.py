from decimal import Decimal

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.catalogo.models import Produto, VariacaoProduto
from apps.contas.models import Endereco
from apps.orcamentos.models import Orcamento
from apps.vendedores.models import Loja

ZERO = Decimal("0.00")


class StatusPedido(models.TextChoices):
    """Estados compartilhados (mas independentes) por Pedido e SubPedido."""

    PENDENTE = "pendente", "Pendente"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    CONCLUIDO = "concluido", "Concluído"
    CANCELADO = "cancelado", "Cancelado"


_STATUS_VALIDOS = Q(status__in=[s.value for s in StatusPedido])


# ---------------------------------------------------------------------------
# Carrinho (persistido no banco)
# ---------------------------------------------------------------------------
class Carrinho(models.Model):
    comprador = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="carrinho"
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "carrinho"
        verbose_name_plural = "carrinhos"
        ordering = ["-atualizado_em"]

    def __str__(self):
        return f"Carrinho de {self.comprador}"

    def total(self):
        return sum((item.subtotal for item in self.itens.select_related("produto", "variacao")), ZERO)


class ItemCarrinho(models.Model):
    carrinho = models.ForeignKey(Carrinho, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="+")
    variacao = models.ForeignKey(
        VariacaoProduto,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="variação",
    )
    quantidade = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    adicionado_em = models.DateTimeField("adicionado em", auto_now_add=True)

    class Meta:
        verbose_name = "item do carrinho"
        verbose_name_plural = "itens do carrinho"
        ordering = ["adicionado_em"]
        constraints = [
            models.CheckConstraint(condition=Q(quantidade__gte=1), name="item_carrinho_qtd_positiva"),
            models.UniqueConstraint(
                fields=["carrinho", "variacao"],
                condition=Q(variacao__isnull=False),
                name="item_carrinho_variacao_unica",
                violation_error_message="Esta variação já está no carrinho.",
            ),
            models.UniqueConstraint(
                fields=["carrinho", "produto"],
                condition=Q(variacao__isnull=True),
                name="item_carrinho_produto_unico",
                violation_error_message="Este produto já está no carrinho.",
            ),
        ]

    def __str__(self):
        return f"{self.quantidade} × {self.produto}" + (f" ({self.variacao})" if self.variacao_id else "")

    @property
    def preco_unitario(self):
        return self.variacao.preco_final if self.variacao_id else self.produto.preco_base

    @property
    def subtotal(self):
        return self.preco_unitario * self.quantidade

    def clean(self):
        super().clean()
        if not self.produto_id:
            return
        validar_combinacao(self.produto, self.variacao, self.quantidade)
        # Espelha as UniqueConstraints condicionais (não validadas por formulários inline).
        if self.carrinho_id:
            repetidos = ItemCarrinho.objects.filter(carrinho_id=self.carrinho_id).exclude(pk=self.pk)
            if self.variacao_id:
                repetidos = repetidos.filter(variacao_id=self.variacao_id)
            else:
                repetidos = repetidos.filter(produto_id=self.produto_id, variacao__isnull=True)
            if repetidos.exists():
                raise ValidationError("Este item já está no carrinho; altere a quantidade.")


def validar_combinacao(produto, variacao, quantidade):
    """Regras comuns a itens de carrinho e de pedido."""
    if produto.tipo == Produto.Tipo.DIGITAL:
        if variacao is not None:
            raise ValidationError({"variacao": "Produtos digitais não possuem variações."})
        if quantidade != 1:
            raise ValidationError({"quantidade": "Produtos digitais são vendidos em quantidade 1."})
        return
    if variacao is None:
        raise ValidationError({"variacao": "Escolha uma variação para produtos físicos."})
    if variacao.produto_id != produto.pk:
        raise ValidationError({"variacao": "A variação escolhida não pertence a este produto."})
    if quantidade is not None and quantidade > variacao.estoque:
        raise ValidationError({"quantidade": f"Estoque insuficiente (disponível: {variacao.estoque})."})


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------
class Pedido(models.Model):
    """Pedido principal do comprador; agrupa um subpedido por loja.

    O endereço escolhido é referenciado e também copiado (snapshot) para que o
    histórico não mude se o comprador editar ou excluir o cadastro.
    """

    comprador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pedidos"
    )
    status = models.CharField(max_length=12, choices=StatusPedido.choices, default=StatusPedido.PENDENTE)
    endereco = models.ForeignKey(
        Endereco,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pedidos",
        verbose_name="endereço cadastrado",
        help_text="Vazio em pedidos só com produtos digitais ou se o endereço foi excluído.",
    )
    entrega_destinatario = models.CharField("destinatário", max_length=150, blank=True)
    entrega_telefone = models.CharField("telefone", max_length=20, blank=True)
    entrega_cep = models.CharField("CEP", max_length=9, blank=True)
    entrega_logradouro = models.CharField("logradouro", max_length=200, blank=True)
    entrega_numero = models.CharField("número", max_length=20, blank=True)
    entrega_complemento = models.CharField("complemento", max_length=100, blank=True)
    entrega_bairro = models.CharField("bairro", max_length=100, blank=True)
    entrega_cidade = models.CharField("cidade", max_length=100, blank=True)
    entrega_uf = models.CharField("UF", max_length=2, blank=True)
    valor_total = models.DecimalField("valor total", max_digits=12, decimal_places=2, default=ZERO)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pedido"
        verbose_name_plural = "pedidos"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["status", "criado_em"])]
        constraints = [
            models.CheckConstraint(condition=_STATUS_VALIDOS, name="pedido_status_valido"),
            models.CheckConstraint(condition=Q(valor_total__gte=0), name="pedido_total_nao_negativo"),
        ]

    def __str__(self):
        return f"Pedido #{self.pk}"

    @property
    def possui_entrega(self):
        return bool(self.entrega_logradouro)

    @property
    def endereco_entrega_texto(self):
        if not self.possui_entrega:
            return "Sem entrega física (somente produtos digitais)."
        complemento = f" — {self.entrega_complemento}" if self.entrega_complemento else ""
        return (
            f"{self.entrega_destinatario} · {self.entrega_telefone}\n"
            f"{self.entrega_logradouro}, {self.entrega_numero}{complemento}\n"
            f"{self.entrega_bairro} — {self.entrega_cidade}/{self.entrega_uf} — CEP {self.entrega_cep}"
        )

    @property
    def pode_ser_cancelado_pelo_comprador(self):
        return self.status == StatusPedido.PENDENTE

    def copiar_endereco(self, endereco):
        self.endereco = endereco
        self.entrega_destinatario = endereco.destinatario
        self.entrega_telefone = endereco.telefone
        self.entrega_cep = endereco.cep
        self.entrega_logradouro = endereco.logradouro
        self.entrega_numero = endereco.numero
        self.entrega_complemento = endereco.complemento
        self.entrega_bairro = endereco.bairro
        self.entrega_cidade = endereco.cidade
        self.entrega_uf = endereco.uf

    def recalcular_total(self):
        self.valor_total = self.subpedidos.aggregate(t=Sum("subtotal"))["t"] or ZERO
        self.save(update_fields=["valor_total", "atualizado_em"])


class SubPedido(models.Model):
    """Parte do pedido sob responsabilidade de uma loja/vendedor."""

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name="subpedidos")
    loja = models.ForeignKey(Loja, on_delete=models.PROTECT, related_name="subpedidos")
    status = models.CharField(max_length=12, choices=StatusPedido.choices, default=StatusPedido.PENDENTE)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=ZERO)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "subpedido"
        verbose_name_plural = "subpedidos"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["loja", "status"])]
        constraints = [
            models.CheckConstraint(condition=_STATUS_VALIDOS, name="subpedido_status_valido"),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="subpedido_subtotal_nao_negativo"),
            models.UniqueConstraint(
                fields=["pedido", "loja"],
                name="subpedido_unico_por_loja",
                violation_error_message="O pedido já possui um subpedido desta loja.",
            ),
        ]

    def __str__(self):
        return f"Pedido #{self.pedido_id} / {self.loja}"

    def recalcular_subtotal(self):
        self.subtotal = sum((item.subtotal for item in self.itens.all()), ZERO)
        self.save(update_fields=["subtotal", "atualizado_em"])


class ItemPedido(models.Model):
    """Item vendido. Guarda cópia de nome, variação e preço do momento da compra.

    Origina-se de um produto do catálogo OU de um orçamento aceito (nunca ambos).
    O vínculo 1:1 com o orçamento impede gerar dois pedidos para a mesma proposta.
    """

    subpedido = models.ForeignKey(SubPedido, on_delete=models.CASCADE, related_name="itens")
    produto = models.ForeignKey(
        Produto, on_delete=models.PROTECT, null=True, blank=True, related_name="itens_vendidos"
    )
    variacao = models.ForeignKey(
        VariacaoProduto,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="itens_vendidos",
        verbose_name="variação",
    )
    orcamento = models.OneToOneField(
        Orcamento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="item_pedido",
        verbose_name="orçamento de origem",
    )
    tipo_produto = models.CharField("tipo", max_length=10, choices=Produto.Tipo.choices)
    descricao = models.CharField("descrição", max_length=200)
    detalhes_variacao = models.CharField("variação/especificação", max_length=200, blank=True)
    preco_unitario = models.DecimalField("preço unitário", max_digits=10, decimal_places=2)
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        verbose_name = "item do pedido"
        verbose_name_plural = "itens do pedido"
        ordering = ["subpedido", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(produto__isnull=False, orcamento__isnull=True)
                | Q(produto__isnull=True, orcamento__isnull=False),
                name="item_pedido_origem_unica",
                violation_error_message="O item deve vir de um produto ou de um orçamento, não de ambos.",
            ),
            models.CheckConstraint(
                condition=Q(variacao__isnull=True) | Q(produto__isnull=False),
                name="item_pedido_variacao_exige_produto",
            ),
            models.CheckConstraint(
                condition=~Q(tipo_produto="digital") | Q(quantidade=1, variacao__isnull=True),
                name="item_pedido_digital_sem_variacao_qtd_1",
            ),
            models.CheckConstraint(condition=Q(quantidade__gte=1), name="item_pedido_qtd_positiva"),
            models.CheckConstraint(
                condition=Q(preco_unitario__gte=0), name="item_pedido_preco_nao_negativo"
            ),
            models.CheckConstraint(
                condition=Q(tipo_produto__in=["fisico", "digital"]), name="item_pedido_tipo_valido"
            ),
        ]

    def __str__(self):
        return f"{self.quantidade} × {self.descricao}"

    @property
    def subtotal(self):
        if self.preco_unitario is None or self.quantidade is None:
            return ZERO
        return self.preco_unitario * self.quantidade


class PagamentoSimulado(models.Model):
    """Registro FICTÍCIO de pagamento de um subpedido.

    Não há integração com instituições financeiras: nenhuma cobrança é feita. A
    confirmação é manual, por um administrador ou pelo vendedor do subpedido.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        CONFIRMADO = "confirmado", "Confirmado (simulado)"

    subpedido = models.OneToOneField(SubPedido, on_delete=models.PROTECT, related_name="pagamento")
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagamentos_confirmados",
    )
    confirmado_em = models.DateTimeField("confirmado em", null=True, blank=True)
    observacao = models.CharField("observação", max_length=255, blank=True)
    criado_em = models.DateTimeField("registrado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "pagamento simulado"
        verbose_name_plural = "pagamentos simulados"
        ordering = ["-criado_em"]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pendente", "confirmado"]), name="pagamento_status_valido"
            ),
            models.CheckConstraint(condition=Q(valor__gte=0), name="pagamento_valor_nao_negativo"),
            models.CheckConstraint(
                condition=Q(status="pendente", confirmado_por__isnull=True, confirmado_em__isnull=True)
                | Q(status="confirmado", confirmado_por__isnull=False, confirmado_em__isnull=False),
                name="pagamento_confirmacao_consistente",
            ),
        ]

    def __str__(self):
        return f"Pagamento simulado — {self.subpedido} ({self.get_status_display()})"

    @staticmethod
    def pode_confirmar(usuario, subpedido):
        if not (usuario and usuario.is_active):
            return False
        if usuario.is_superuser:
            return True
        perfil = getattr(usuario, "perfil_vendedor", None)
        return perfil is not None and subpedido.loja.vendedor_id == perfil.pk

    @transaction.atomic
    def confirmar(self, usuario, observacao=""):
        pagamento = PagamentoSimulado.objects.select_for_update().select_related("subpedido__loja").get(
            pk=self.pk
        )
        if not self.pode_confirmar(usuario, pagamento.subpedido):
            raise PermissionDenied("Você não pode confirmar este pagamento.")
        if pagamento.status != self.Status.PENDENTE:
            raise ValidationError("Este pagamento já foi confirmado.")
        pagamento.status = self.Status.CONFIRMADO
        pagamento.confirmado_por = usuario
        pagamento.confirmado_em = timezone.now()
        if observacao:
            pagamento.observacao = observacao
        pagamento.save()
        self.refresh_from_db()
