from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.armazenamento import armazenamento_privado
from apps.core.validadores import validar_arquivo_3d
from apps.vendedores.models import PerfilVendedor


def _caminho_arquivo_orcamento(instancia, nome):
    return f"orcamentos/{instancia.comprador_id}/{nome}"


class Orcamento(models.Model):
    """Solicitação de impressão personalizada enviada por um comprador a um vendedor.

    Fluxo: Pendente → Respondido (vendedor propõe preço) → Aceito/Recusado (comprador).
    Pendente ou Respondido podem ser Cancelados pelo comprador. O aceite gera um
    pedido; a ligação 1:1 ``ItemPedido.orcamento`` impede pedidos duplicados.
    """

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        RESPONDIDO = "respondido", "Respondido"
        ACEITO = "aceito", "Aceito"
        RECUSADO = "recusado", "Recusado"
        CANCELADO = "cancelado", "Cancelado"

    comprador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orcamentos_solicitados",
    )
    vendedor = models.ForeignKey(
        PerfilVendedor,
        on_delete=models.PROTECT,
        related_name="orcamentos_recebidos",
        verbose_name="vendedor destinatário",
    )
    arquivo_3d = models.FileField(
        "arquivo 3D",
        upload_to=_caminho_arquivo_orcamento,
        storage=armazenamento_privado,
        validators=[validar_arquivo_3d],
        max_length=255,
    )
    quantidade = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    material = models.CharField("material desejado", max_length=60)
    cor = models.CharField("cor desejada", max_length=40)
    dimensoes = models.CharField("dimensões", max_length=60)
    observacoes = models.TextField("observações", blank=True)

    # Proposta comercial do vendedor
    preco_unitario_proposto = models.DecimalField(
        "preço unitário proposto",
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    detalhes_proposta = models.TextField(
        "detalhes da proposta", blank=True, help_text="Prazo, condições e observações do vendedor."
    )
    respondido_em = models.DateTimeField("respondido em", null=True, blank=True)

    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    finalizado_em = models.DateTimeField(
        "finalizado em", null=True, blank=True, help_text="Data do aceite, recusa ou cancelamento."
    )
    criado_em = models.DateTimeField("solicitado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "solicitação de orçamento"
        verbose_name_plural = "solicitações de orçamento"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["vendedor", "status"]), models.Index(fields=["status"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pendente", "respondido", "aceito", "recusado", "cancelado"]),
                name="orcamento_status_valido",
            ),
            models.CheckConstraint(condition=Q(quantidade__gte=1), name="orcamento_quantidade_positiva"),
            models.CheckConstraint(
                condition=Q(preco_unitario_proposto__isnull=True) | Q(preco_unitario_proposto__gt=0),
                name="orcamento_preco_positivo",
            ),
            # Pendente: ainda sem proposta. Respondido/Aceito/Recusado: proposta obrigatória.
            models.CheckConstraint(
                condition=~Q(status="pendente")
                | Q(preco_unitario_proposto__isnull=True, respondido_em__isnull=True),
                name="orcamento_pendente_sem_proposta",
            ),
            models.CheckConstraint(
                condition=~Q(status__in=["respondido", "aceito", "recusado"])
                | Q(preco_unitario_proposto__isnull=False, respondido_em__isnull=False),
                name="orcamento_respondido_com_proposta",
            ),
        ]

    def __str__(self):
        return f"Orçamento #{self.pk} — {self.material}/{self.cor} × {self.quantidade}"

    @property
    def valor_total_proposto(self):
        if self.preco_unitario_proposto is None:
            return None
        return self.preco_unitario_proposto * self.quantidade

    @property
    def nome_arquivo(self):
        return Path(self.arquivo_3d.name).name if self.arquivo_3d else ""

    @property
    def pedido_gerado(self):
        item = getattr(self, "item_pedido", None)
        return item.subpedido.pedido if item else None

    # ------------------------------------------------------------------
    # Transições de estado
    # ------------------------------------------------------------------
    def _bloquear(self):
        return Orcamento.objects.select_for_update().get(pk=self.pk)

    @transaction.atomic
    def responder(self, usuario_vendedor, preco_unitario, detalhes=""):
        orc = self._bloquear()
        if orc.vendedor.usuario_id != usuario_vendedor.pk:
            raise PermissionDenied("Somente o vendedor destinatário pode responder.")
        if orc.status != self.Status.PENDENTE:
            raise ValidationError("Somente orçamentos pendentes podem ser respondidos.")
        orc.preco_unitario_proposto = preco_unitario
        orc.detalhes_proposta = detalhes
        orc.respondido_em = timezone.now()
        orc.status = self.Status.RESPONDIDO
        orc.full_clean()
        orc.save()
        self.refresh_from_db()

    def _decidir(self, comprador, novo_status, permitidos):
        orc = self._bloquear()
        if orc.comprador_id != comprador.pk:
            raise PermissionDenied("Somente o comprador pode decidir sobre este orçamento.")
        if orc.status not in permitidos:
            raise ValidationError(
                f"Não é possível passar de '{orc.get_status_display()}' para '{novo_status.label}'."
            )
        orc.status = novo_status
        orc.finalizado_em = timezone.now()
        orc.save(update_fields=["status", "finalizado_em", "atualizado_em"])
        return orc

    @transaction.atomic
    def aceitar(self, comprador, endereco):
        """Aceita a proposta e gera o pedido correspondente na mesma transação."""
        from apps.pedidos.servicos import gerar_pedido_de_orcamento

        orc = self._decidir(comprador, self.Status.ACEITO, [self.Status.RESPONDIDO])
        pedido = gerar_pedido_de_orcamento(orc, endereco)
        self.refresh_from_db()
        return pedido

    @transaction.atomic
    def recusar(self, comprador):
        self._decidir(comprador, self.Status.RECUSADO, [self.Status.RESPONDIDO])
        self.refresh_from_db()

    @transaction.atomic
    def cancelar(self, comprador):
        self._decidir(comprador, self.Status.CANCELADO, [self.Status.PENDENTE, self.Status.RESPONDIDO])
        self.refresh_from_db()
