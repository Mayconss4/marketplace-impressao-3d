from django import forms
from django.contrib.auth.forms import UserCreationForm

from apps.core.forms import FormularioBootstrap

from .models import Endereco, Usuario


class ValidacaoEmailUnico:
    """O e-mail é único sem diferenciar maiúsculas (espelha a constraint do banco)."""

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if Usuario.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email


class FormularioCadastro(ValidacaoEmailUnico, FormularioBootstrap, UserCreationForm):
    """Cadastro público: toda conta nova começa apenas como compradora."""

    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("username", "first_name", "last_name", "email")
        labels = {"username": "Nome de usuário"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True
        self.fields["username"].widget.attrs["autofocus"] = True


class FormularioDadosConta(ValidacaoEmailUnico, FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ("first_name", "last_name", "email")


class FormularioEndereco(FormularioBootstrap, forms.ModelForm):
    class Meta:
        model = Endereco
        fields = (
            "apelido",
            "destinatario",
            "telefone",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "uf",
        )
        widgets = {
            "telefone": forms.TextInput(attrs={"placeholder": "(35) 99999-0000"}),
            "cep": forms.TextInput(attrs={"placeholder": "37200-000"}),
        }

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        if usuario is not None:
            self.instance.usuario = usuario

    def clean_apelido(self):
        # "usuario" não está no formulário, então o Django não valida a constraint (usuário, apelido).
        apelido = self.cleaned_data["apelido"].strip()
        repetido = Endereco.objects.filter(usuario=self.instance.usuario, apelido__iexact=apelido)
        if repetido.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Você já possui um endereço com esta identificação.")
        return apelido
