from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from apps.core.validadores import (
    cnpj_valido,
    cpf_valido,
    formatar_cnpj,
    formatar_cpf,
    somente_digitos,
    validar_telefone,
)


class SolicitacaoVendedor(models.Model):
    """Pedido de habilitação como vendedor, sujeito à aprovação administrativa.

    O estado só muda pelos métodos ``aprovar``/``recusar`` (acionados no admin por
    um administrador); nenhum campo enviado pelo navegador concede o perfil.
    """

    class TipoPessoa(models.TextChoices):
        FISICA = "PF", "Pessoa física"
        JURIDICA = "PJ", "Pessoa jurídica"

    class Status(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        APROVADA = "aprovada", "Aprovada"
        RECUSADA = "recusada", "Recusada"

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="solicitacoes_vendedor",
        verbose_name="solicitante",
    )
    tipo_pessoa = models.CharField("tipo de pessoa", max_length=2, choices=TipoPessoa.choices)
    documento = models.CharField(
        "CPF/CNPJ", max_length=14, help_text="Somente números; CPF para PF ou CNPJ para PJ."
    )
    nome_razao_social = models.CharField("nome / razão social", max_length=200)
    telefone = models.CharField(max_length=20, validators=[validar_telefone])
    nome_loja = models.CharField("nome da loja", max_length=120)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDENTE)
    analisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitacoes_analisadas",
        verbose_name="analisada por",
    )
    analisado_em = models.DateTimeField("analisada em", null=True, blank=True)
    criado_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "solicitação de vendedor"
        verbose_name_plural = "solicitações de vendedor"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["status", "criado_em"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pendente", "aprovada", "recusada"]),
                name="solicitacao_status_valido",
            ),
            models.CheckConstraint(
                condition=Q(tipo_pessoa__in=["PF", "PJ"]), name="solicitacao_tipo_pessoa_valido"
            ),
            models.CheckConstraint(
                condition=(Q(tipo_pessoa="PF", documento__regex=r"^[0-9]{11}$"))
                | Q(tipo_pessoa="PJ", documento__regex=r"^[0-9]{14}$"),
                name="solicitacao_documento_compativel_tipo",
                violation_error_message="O documento deve ter 11 dígitos (CPF) ou 14 dígitos (CNPJ).",
            ),
            # Uma solicitação analisada sempre registra quem analisou e quando.
            models.CheckConstraint(
                condition=Q(status="pendente", analisado_por__isnull=True, analisado_em__isnull=True)
                | (
                    ~Q(status="pendente")
                    & Q(analisado_por__isnull=False, analisado_em__isnull=False)
                ),
                name="solicitacao_analise_consistente",
            ),
            # No máximo uma solicitação em aberto ou aprovada por conta...
            models.UniqueConstraint(
                fields=["usuario"],
                condition=Q(status__in=["pendente", "aprovada"]),
                name="solicitacao_unica_ativa_por_usuario",
                violation_error_message="Esta conta já possui uma solicitação pendente ou aprovada.",
            ),
            # ...e o mesmo CPF/CNPJ não pode estar em duas solicitações ativas.
            models.UniqueConstraint(
                fields=["documento"],
                condition=Q(status__in=["pendente", "aprovada"]),
                name="solicitacao_documento_unico_ativo",
                violation_error_message="Este CPF/CNPJ já está em uma solicitação pendente ou aprovada.",
            ),
        ]

    def __str__(self):
        return f"{self.nome_loja} — {self.usuario} ({self.get_status_display()})"

    @property
    def documento_formatado(self):
        if self.tipo_pessoa == self.TipoPessoa.FISICA:
            return formatar_cpf(self.documento)
        return formatar_cnpj(self.documento)

    def clean(self):
        super().clean()
        self.documento = somente_digitos(self.documento)
        if self.tipo_pessoa == self.TipoPessoa.FISICA and not cpf_valido(self.documento):
            raise ValidationError({"documento": "CPF inválido para pessoa física."})
        if self.tipo_pessoa == self.TipoPessoa.JURIDICA and not cnpj_valido(self.documento):
            raise ValidationError({"documento": "CNPJ inválido para pessoa jurídica."})
        # Espelha as UniqueConstraints condicionais: formulários sem o campo
        # "status" fariam o Django pular essa validação e só o banco a barraria.
        if self.status in (self.Status.PENDENTE, self.Status.APROVADA):
            ativas = SolicitacaoVendedor.objects.filter(
                status__in=[self.Status.PENDENTE, self.Status.APROVADA]
            ).exclude(pk=self.pk)
            if self.usuario_id and ativas.filter(usuario_id=self.usuario_id).exists():
                raise ValidationError("Esta conta já possui uma solicitação pendente ou aprovada.")
            if ativas.filter(documento=self.documento).exists():
                raise ValidationError(
                    {"documento": "Este CPF/CNPJ já está em uma solicitação pendente ou aprovada."}
                )

    def _validar_analise(self, administrador):
        if not (administrador and administrador.is_active and administrador.is_superuser):
            raise PermissionDenied("Somente administradores podem analisar solicitações.")
        if administrador.pk == self.usuario_id:
            raise ValidationError("Um administrador não pode analisar a própria solicitação.")
        if self.status != self.Status.PENDENTE:
            raise ValidationError("Somente solicitações pendentes podem ser analisadas.")

    @transaction.atomic
    def aprovar(self, administrador):
        """Aprova a solicitação e habilita a conta como vendedor."""
        from .perfis import obter_grupo_vendedores

        solicitacao = SolicitacaoVendedor.objects.select_for_update().get(pk=self.pk)
        solicitacao._validar_analise(administrador)
        solicitacao.status = self.Status.APROVADA
        solicitacao.analisado_por = administrador
        solicitacao.analisado_em = timezone.now()
        solicitacao.save(update_fields=["status", "analisado_por", "analisado_em", "atualizado_em"])

        PerfilVendedor.objects.create(usuario=solicitacao.usuario, solicitacao=solicitacao)
        usuario = solicitacao.usuario
        # is_staff apenas libera o login no painel; o que o vendedor vê e altera é
        # limitado pelas permissões do grupo e pelo isolamento dos ModelAdmins.
        usuario.is_staff = True
        usuario.save(update_fields=["is_staff"])
        usuario.groups.add(obter_grupo_vendedores())
        self.refresh_from_db()
        return solicitacao

    @transaction.atomic
    def recusar(self, administrador):
        """Recusa a solicitação; a conta continua apenas como compradora."""
        solicitacao = SolicitacaoVendedor.objects.select_for_update().get(pk=self.pk)
        solicitacao._validar_analise(administrador)
        solicitacao.status = self.Status.RECUSADA
        solicitacao.analisado_por = administrador
        solicitacao.analisado_em = timezone.now()
        solicitacao.save(update_fields=["status", "analisado_por", "analisado_em", "atualizado_em"])
        self.refresh_from_db()
        return solicitacao


class PerfilVendedor(models.Model):
    """Habilitação comercial de uma conta, criada exclusivamente pela aprovação.

    Os dados cadastrais (documento, razão social, telefone) permanecem na
    solicitação aprovada, evitando duplicação.
    """

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="perfil_vendedor",
        verbose_name="usuário",
    )
    solicitacao = models.OneToOneField(
        SolicitacaoVendedor,
        on_delete=models.PROTECT,
        related_name="perfil",
        verbose_name="solicitação aprovada",
        limit_choices_to={"status": SolicitacaoVendedor.Status.APROVADA},
    )
    aprovado_em = models.DateTimeField("habilitado em", auto_now_add=True)

    class Meta:
        verbose_name = "vendedor"
        verbose_name_plural = "vendedores"
        ordering = ["usuario__username"]

    def __str__(self):
        return f"{self.solicitacao.nome_razao_social} ({self.usuario.username})"

    def clean(self):
        super().clean()
        if self.solicitacao_id:
            if self.solicitacao.status != SolicitacaoVendedor.Status.APROVADA:
                raise ValidationError("O perfil exige uma solicitação aprovada.")
            if self.usuario_id and self.solicitacao.usuario_id != self.usuario_id:
                raise ValidationError("A solicitação aprovada pertence a outra conta.")

    @property
    def tipo_pessoa(self):
        return self.solicitacao.get_tipo_pessoa_display()

    @property
    def documento(self):
        return self.solicitacao.documento_formatado

    @property
    def nome_razao_social(self):
        return self.solicitacao.nome_razao_social

    @property
    def telefone(self):
        return self.solicitacao.telefone


class Loja(models.Model):
    """Loja única de um vendedor aprovado."""

    vendedor = models.OneToOneField(
        PerfilVendedor, on_delete=models.PROTECT, related_name="loja", verbose_name="vendedor"
    )
    nome = models.CharField(max_length=120)
    descricao = models.TextField("descrição")
    logotipo = models.ImageField(upload_to="lojas/logotipos/")
    ativa = models.BooleanField(
        default=True,
        help_text="Lojas inativas não oferecem produtos à venda; nada é excluído ao desativar.",
    )
    criado_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "loja"
        verbose_name_plural = "lojas"
        ordering = ["nome"]
        indexes = [models.Index(fields=["ativa", "nome"])]

    def __str__(self):
        return self.nome
