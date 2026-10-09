from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower

from apps.core.validadores import validar_telefone


class Usuario(AbstractUser):
    """Conta única do marketplace.

    A mesma conta atua como comprador e, após aprovação administrativa, como
    vendedor. O perfil funcional é derivado dos relacionamentos (ver
    ``eh_vendedor_aprovado``) e não de campos editáveis pelo próprio usuário.
    """

    first_name = models.CharField("nome", max_length=150)
    last_name = models.CharField("sobrenome", max_length=150, blank=True)
    email = models.EmailField("e-mail")

    REQUIRED_FIELDS = ["email", "first_name"]

    class Meta(AbstractUser.Meta):
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="usuario_email_unico_ci",
                violation_error_message="Já existe uma conta com este e-mail.",
            ),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.email = (self.email or "").strip().lower()

    @property
    def eh_administrador(self):
        return self.is_active and self.is_superuser

    @property
    def eh_vendedor_aprovado(self):
        return hasattr(self, "perfil_vendedor")

    @property
    def perfis(self):
        perfis = ["Comprador"]
        if self.eh_vendedor_aprovado:
            perfis.append("Vendedor")
        if self.eh_administrador:
            perfis.append("Administrador")
        return perfis


class Endereco(models.Model):
    """Endereço de entrega cadastrado pelo comprador (pode haver vários)."""

    class UF(models.TextChoices):
        AC = "AC", "Acre"
        AL = "AL", "Alagoas"
        AP = "AP", "Amapá"
        AM = "AM", "Amazonas"
        BA = "BA", "Bahia"
        CE = "CE", "Ceará"
        DF = "DF", "Distrito Federal"
        ES = "ES", "Espírito Santo"
        GO = "GO", "Goiás"
        MA = "MA", "Maranhão"
        MT = "MT", "Mato Grosso"
        MS = "MS", "Mato Grosso do Sul"
        MG = "MG", "Minas Gerais"
        PA = "PA", "Pará"
        PB = "PB", "Paraíba"
        PR = "PR", "Paraná"
        PE = "PE", "Pernambuco"
        PI = "PI", "Piauí"
        RJ = "RJ", "Rio de Janeiro"
        RN = "RN", "Rio Grande do Norte"
        RS = "RS", "Rio Grande do Sul"
        RO = "RO", "Rondônia"
        RR = "RR", "Roraima"
        SC = "SC", "Santa Catarina"
        SP = "SP", "São Paulo"
        SE = "SE", "Sergipe"
        TO = "TO", "Tocantins"

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="enderecos", verbose_name="comprador"
    )
    apelido = models.CharField("identificação", max_length=50, help_text="Ex.: Casa, Trabalho.")
    destinatario = models.CharField("destinatário", max_length=150)
    telefone = models.CharField("telefone", max_length=20, validators=[validar_telefone])
    cep = models.CharField(
        "CEP", max_length=9, validators=[RegexValidator(r"^\d{5}-?\d{3}$", "Informe um CEP válido.")]
    )
    logradouro = models.CharField(max_length=200)
    numero = models.CharField("número", max_length=20)
    complemento = models.CharField(max_length=100, blank=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    uf = models.CharField("UF", max_length=2, choices=UF.choices)
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "endereço"
        verbose_name_plural = "endereços"
        ordering = ["usuario", "apelido"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "apelido"],
                name="endereco_apelido_unico_por_usuario",
                violation_error_message="Você já possui um endereço com esta identificação.",
            ),
        ]

    def __str__(self):
        return f"{self.apelido} — {self.logradouro}, {self.numero} ({self.cidade}/{self.uf})"

    def como_texto(self):
        complemento = f" — {self.complemento}" if self.complemento else ""
        return (
            f"{self.destinatario} · {self.telefone}\n"
            f"{self.logradouro}, {self.numero}{complemento}\n"
            f"{self.bairro} — {self.cidade}/{self.uf} — CEP {self.cep}"
        )
