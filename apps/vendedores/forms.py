from django import forms

from apps.core.forms import FormularioBootstrap
from apps.core.validadores import somente_digitos

from .models import SolicitacaoVendedor


class FormularioSolicitacao(FormularioBootstrap, forms.ModelForm):
    """Pedido de habilitação como vendedor; o status é sempre definido pelo servidor."""

    documento = forms.CharField(label="CPF/CNPJ", max_length=18, help_text="CPF para pessoa física ou CNPJ para jurídica.")

    class Meta:
        model = SolicitacaoVendedor
        fields = ("tipo_pessoa", "documento", "nome_razao_social", "telefone", "nome_loja")
        widgets = {"telefone": forms.TextInput(attrs={"placeholder": "(35) 99999-0000"})}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.usuario = usuario

    def clean_documento(self):
        return somente_digitos(self.cleaned_data["documento"])
