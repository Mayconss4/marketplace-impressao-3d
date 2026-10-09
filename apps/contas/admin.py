from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.db.models import Count
from django.utils.html import format_html_join

from .models import Endereco, Usuario


class FormularioCriacaoUsuario(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email")


class FormularioEdicaoUsuario(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario


class PerfilFuncionalFilter(admin.SimpleListFilter):
    title = "perfil funcional"
    parameter_name = "perfil"

    def lookups(self, request, model_admin):
        return [
            ("comprador", "Somente comprador"),
            ("vendedor", "Vendedor aprovado"),
            ("solicitante", "Solicitação de vendedor pendente"),
            ("administrador", "Administrador"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "comprador":
            return queryset.filter(perfil_vendedor__isnull=True, is_superuser=False)
        if self.value() == "vendedor":
            return queryset.filter(perfil_vendedor__isnull=False)
        if self.value() == "solicitante":
            return queryset.filter(solicitacoes_vendedor__status="pendente")
        if self.value() == "administrador":
            return queryset.filter(is_superuser=True)
        return queryset


class EnderecoInline(admin.StackedInline):
    model = Endereco
    extra = 0
    fields = (("apelido", "destinatario", "telefone"), ("cep", "logradouro", "numero"),
              ("complemento", "bairro"), ("cidade", "uf"))


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = FormularioEdicaoUsuario
    add_form = FormularioCriacaoUsuario
    list_display = ("username", "get_full_name", "email", "perfis_exibicao", "is_staff", "is_active", "date_joined")
    list_filter = (PerfilFuncionalFilter, "is_active", "is_staff", "is_superuser", "groups", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email")
    ordering = ("username",)
    readonly_fields = ("last_login", "date_joined", "perfis_exibicao")
    inlines = [EnderecoInline]
    fieldsets = (
        ("Acesso", {"fields": ("username", "password")}),
        ("Dados pessoais", {"fields": ("first_name", "last_name", "email", "perfis_exibicao")}),
        (
            "Permissões técnicas",
            {
                "classes": ("collapse",),
                "description": "is_staff libera o login no painel; o perfil de vendedor é concedido "
                "apenas pela aprovação de uma solicitação.",
                "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
            },
        ),
        ("Datas", {"classes": ("collapse",), "fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "first_name", "last_name", "email", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="perfis")
    def perfis_exibicao(self, obj):
        return format_html_join(" ", '<span class="badge badge-info">{}</span>', ((p,) for p in obj.perfis))

    @admin.display(description="nome completo", ordering="first_name")
    def get_full_name(self, obj):
        return obj.get_full_name()

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("perfil_vendedor")


@admin.register(Endereco)
class EnderecoAdmin(admin.ModelAdmin):
    list_display = ("apelido", "usuario", "destinatario", "cidade", "uf", "cep", "qtd_pedidos")
    list_filter = ("uf", "criado_em", "atualizado_em")
    search_fields = ("apelido", "usuario__username", "usuario__email", "destinatario", "cidade", "cep", "logradouro")
    list_select_related = ("usuario",)
    autocomplete_fields = ("usuario",)
    fieldsets = (
        (None, {"fields": ("usuario", "apelido")}),
        ("Contato", {"fields": ("destinatario", "telefone")}),
        ("Endereço", {"fields": ("cep", "logradouro", "numero", "complemento", "bairro", "cidade", "uf")}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_qtd_pedidos=Count("pedidos"))

    @admin.display(description="pedidos", ordering="_qtd_pedidos")
    def qtd_pedidos(self, obj):
        return obj._qtd_pedidos
