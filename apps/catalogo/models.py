from decimal import Decimal
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import F, Min, Q, Sum
from django.db.models.functions import Lower

from apps.core.armazenamento import armazenamento_privado
from apps.core.validadores import validar_arquivo_3d
from apps.vendedores.models import Loja


class Categoria(models.Model):
    """Categoria hierárquica (ex.: Decoração → Vasos). Gerida só por administradores."""

    nome = models.CharField(max_length=80)
    slug = models.SlugField(max_length=100, unique=True)
    pai = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="subcategorias",
        verbose_name="categoria pai",
    )
    ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "categoria"
        verbose_name_plural = "categorias"
        ordering = ["nome"]
        constraints = [
            models.CheckConstraint(condition=~Q(pai=F("id")), name="categoria_nao_e_pai_de_si"),
            models.UniqueConstraint(
                Lower("nome"),
                "pai",
                name="categoria_nome_unico_no_nivel",
                violation_error_message="Já existe uma categoria com este nome neste nível.",
            ),
            # Em SQLite, NULLs são distintos: a constraint acima não cobre as raízes.
            models.UniqueConstraint(
                Lower("nome"),
                condition=Q(pai__isnull=True),
                name="categoria_raiz_nome_unico",
                violation_error_message="Já existe uma categoria raiz com este nome.",
            ),
        ]

    def __str__(self):
        return self.caminho

    def ancestrais(self):
        """Lista da raiz até o pai imediato (protegida contra ciclos já gravados)."""
        cadeia, visitados, atual = [], {self.pk}, self.pai
        while atual is not None and atual.pk not in visitados:
            cadeia.append(atual)
            visitados.add(atual.pk)
            atual = atual.pai
        return list(reversed(cadeia))

    @property
    def caminho(self):
        return " → ".join([c.nome for c in self.ancestrais()] + [self.nome])

    @property
    def nivel(self):
        return len(self.ancestrais())

    def clean(self):
        super().clean()
        if self.pai_id is None:
            return
        if self.pk and self.pai_id == self.pk:
            raise ValidationError({"pai": "Uma categoria não pode ser pai de si mesma."})
        atual = self.pai
        while atual is not None:
            if self.pk and atual.pk == self.pk:
                raise ValidationError(
                    {"pai": "Relação circular: a categoria escolhida é descendente desta."}
                )
            atual = atual.pai


class ProdutoQuerySet(models.QuerySet):
    def disponiveis(self):
        """Produtos que podem ser oferecidos para novas compras."""
        return self.filter(ativo=True, loja__ativa=True)


class Produto(models.Model):
    class Tipo(models.TextChoices):
        FISICO = "fisico", "Físico (impresso em 3D)"
        DIGITAL = "digital", "Digital (arquivo para impressão)"

    loja = models.ForeignKey(Loja, on_delete=models.PROTECT, related_name="produtos")
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="produtos")
    nome = models.CharField(max_length=150)
    descricao = models.TextField("descrição")
    tipo = models.CharField(max_length=10, choices=Tipo.choices)
    preco_base = models.DecimalField(
        "preço base",
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    ativo = models.BooleanField(
        "anúncio ativo",
        default=True,
        help_text="Desative para retirar o anúncio de novas compras sem perder o histórico.",
    )
    criado_em = models.DateTimeField("criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizado em", auto_now=True)

    objects = ProdutoQuerySet.as_manager()

    class Meta:
        verbose_name = "produto"
        verbose_name_plural = "produtos"
        ordering = ["-criado_em"]
        indexes = [
            models.Index(fields=["ativo", "tipo"]),
            models.Index(fields=["loja", "ativo"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(preco_base__gte=0), name="produto_preco_base_nao_negativo"
            ),
            models.CheckConstraint(
                condition=Q(tipo__in=["fisico", "digital"]), name="produto_tipo_valido"
            ),
        ]

    def __str__(self):
        return self.nome

    @property
    def eh_digital(self):
        return self.tipo == self.Tipo.DIGITAL

    @property
    def esta_disponivel(self):
        return self.ativo and self.loja.ativa

    def estoque_total(self):
        """Soma do estoque das variações; ``None`` significa ilimitado (digital)."""
        if self.eh_digital:
            return None
        return self.variacoes.aggregate(total=Sum("estoque"))["total"] or 0

    def preco_minimo(self):
        """Menor preço final ofertado (físico: preço base + menor ajuste)."""
        if self.eh_digital:
            return self.preco_base
        menor_ajuste = self.variacoes.aggregate(m=Min("ajuste_preco"))["m"]
        return None if menor_ajuste is None else self.preco_base + menor_ajuste

    def imagem_principal(self):
        return self.imagens.filter(principal=True).first() or self.imagens.first()

    def clean(self):
        super().clean()
        if not self.pk:
            return
        if self.tipo == self.Tipo.DIGITAL and self.variacoes.exists():
            raise ValidationError(
                {"tipo": "Remova as variações antes de transformar o produto em digital."}
            )
        if self.tipo == self.Tipo.FISICO and self.arquivos.exists():
            raise ValidationError(
                {"tipo": "Remova os arquivos digitais antes de transformar o produto em físico."}
            )
        if self.preco_base is not None:
            menor_ajuste = self.variacoes.aggregate(m=Min("ajuste_preco"))["m"]
            if menor_ajuste is not None and self.preco_base + menor_ajuste < 0:
                raise ValidationError(
                    {"preco_base": "Este preço base tornaria negativo o preço de uma variação."}
                )


class VariacaoProduto(models.Model):
    """Combinação material/cor/dimensão de um produto físico, com estoque próprio."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="variacoes")
    material = models.CharField(max_length=60, help_text="Ex.: PLA, PETG, Resina.")
    cor = models.CharField(max_length=40)
    dimensoes = models.CharField(
        "tamanho/dimensões", max_length=60, help_text="Ex.: 10 x 10 x 15 cm, Médio."
    )
    ajuste_preco = models.DecimalField(
        "ajuste de preço",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Somado ao preço base; pode ser negativo.",
    )
    estoque = models.PositiveIntegerField(default=0)
    criado_em = models.DateTimeField("criada em", auto_now_add=True)
    atualizado_em = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        verbose_name = "variação de produto"
        verbose_name_plural = "variações de produto"
        ordering = ["produto", "material", "cor", "dimensoes"]
        constraints = [
            models.CheckConstraint(condition=Q(estoque__gte=0), name="variacao_estoque_nao_negativo"),
            models.UniqueConstraint(
                "produto",
                Lower("material"),
                Lower("cor"),
                Lower("dimensoes"),
                name="variacao_combinacao_unica",
                violation_error_message="Já existe uma variação com este material, cor e dimensão.",
            ),
        ]

    def __str__(self):
        return f"{self.material} / {self.cor} / {self.dimensoes}"

    @property
    def preco_final(self):
        if self.produto_id is None or self.ajuste_preco is None:
            return None
        return self.produto.preco_base + self.ajuste_preco

    def clean(self):
        super().clean()
        for campo in ("material", "cor", "dimensoes"):
            setattr(self, campo, (getattr(self, campo) or "").strip())
        if self.produto_id is None:
            return
        if self.produto.tipo != Produto.Tipo.FISICO:
            raise ValidationError("Produtos digitais não possuem variações.")
        # Espelha a UniqueConstraint funcional, que formulários inline podem não validar.
        duplicada = (
            VariacaoProduto.objects.filter(
                produto_id=self.produto_id,
                material__iexact=self.material,
                cor__iexact=self.cor,
                dimensoes__iexact=self.dimensoes,
            )
            .exclude(pk=self.pk)
            .exists()
        )
        if duplicada:
            raise ValidationError("Já existe uma variação com este material, cor e dimensão.")
        if (
            self.produto.preco_base is not None
            and self.ajuste_preco is not None
            and self.preco_final < 0
        ):
            raise ValidationError(
                {"ajuste_preco": f"O preço final ficaria negativo ({self.preco_final})."}
            )


def _caminho_imagem(instancia, nome):
    return f"produtos/{instancia.produto_id or 'novo'}/{nome}"


class ImagemProduto(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="imagens")
    imagem = models.ImageField(upload_to=_caminho_imagem)
    texto_alternativo = models.CharField("texto alternativo", max_length=150, blank=True)
    principal = models.BooleanField("imagem principal", default=False)
    ordem = models.PositiveSmallIntegerField(default=0)
    criado_em = models.DateTimeField("enviada em", auto_now_add=True)

    class Meta:
        verbose_name = "imagem de produto"
        verbose_name_plural = "imagens de produto"
        ordering = ["produto", "-principal", "ordem", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["produto"],
                condition=Q(principal=True),
                name="imagem_principal_unica_por_produto",
                violation_error_message="O produto já possui uma imagem principal.",
            ),
        ]

    def __str__(self):
        return f"Imagem de {self.produto} ({'principal' if self.principal else self.ordem})"

    def validate_constraints(self, exclude=None):
        # A unicidade da imagem principal é garantida em save() (que rebaixa a
        # anterior na mesma transação) e, em última instância, pelo banco.
        exclude = set(exclude or ()) | {"principal"}
        super().validate_constraints(exclude=exclude)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.principal:
                ImagemProduto.objects.filter(produto_id=self.produto_id, principal=True).exclude(
                    pk=self.pk
                ).update(principal=False)
            super().save(*args, **kwargs)


def _caminho_arquivo_digital(instancia, nome):
    return f"produtos_digitais/{instancia.produto_id or 'novo'}/{nome}"


class ArquivoDigital(models.Model):
    """Arquivo comercializado por um produto digital. Armazenado de forma privada."""

    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name="arquivos")
    arquivo = models.FileField(
        upload_to=_caminho_arquivo_digital,
        storage=armazenamento_privado,
        validators=[validar_arquivo_3d],
        max_length=255,
    )
    descricao = models.CharField("descrição", max_length=150, blank=True)
    criado_em = models.DateTimeField("enviado em", auto_now_add=True)

    class Meta:
        verbose_name = "arquivo digital"
        verbose_name_plural = "arquivos digitais"
        ordering = ["produto", "id"]

    def __str__(self):
        return self.nome_arquivo

    @property
    def nome_arquivo(self):
        return Path(self.arquivo.name).name if self.arquivo else ""

    @property
    def formato(self):
        sufixo = Path(self.arquivo.name).suffix.lower().lstrip(".") if self.arquivo else ""
        return "STEP" if sufixo in ("step", "stp") else sufixo.upper()

    def clean(self):
        super().clean()
        if self.produto_id and self.produto.tipo != Produto.Tipo.DIGITAL:
            raise ValidationError("Arquivos digitais só podem ser vinculados a produtos digitais.")
