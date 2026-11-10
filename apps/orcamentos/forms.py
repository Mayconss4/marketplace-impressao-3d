from django import forms

from apps.core.forms import FormularioBootstrap
from apps.vendedores.models import PerfilVendedor

from .models import Orcamento


class EscolhaVendedor(forms.ModelChoiceField):
    def label_from_instance(self, perfil):
        return perfil.loja.nome


class FormularioOrcamento(FormularioBootstrap, forms.ModelForm):
    """Solicitação de impressão personalizada enviada pelo comprador."""

    vendedor = EscolhaVendedor(queryset=PerfilVendedor.objects.none(), label="Loja destinatária")

    class Meta:
        model = Orcamento
        fields = ("vendedor", "arquivo_3d", "quantidade", "material", "cor", "dimensoes", "observacoes")
        widgets = {
            "arquivo_3d": forms.ClearableFileInput(attrs={"accept": ".stl,.3mf,.obj,.step,.stp"}),
            "quantidade": forms.NumberInput(attrs={"min": 1}),
            "material": forms.TextInput(attrs={"placeholder": "Ex.: PLA, PETG, Resina"}),
            "dimensoes": forms.TextInput(attrs={"placeholder": "Ex.: 10 x 10 x 15 cm"}),
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {"arquivo_3d": "Formatos aceitos: STL, 3MF, OBJ ou STEP. O arquivo fica privado."}

    def __init__(self, *args, comprador, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.comprador = comprador
        # Somente lojas ativas, e nunca o próprio comprador (sem autocompra).
        self.fields["vendedor"].queryset = (
            PerfilVendedor.objects.filter(loja__ativa=True)
            .exclude(usuario=comprador)
            .select_related("loja")
            .order_by("loja__nome")
        )


class FormularioAceite(FormularioBootstrap, forms.Form):
    endereco = forms.ModelChoiceField(queryset=None, label="Endereço de entrega", empty_label=None)

    def __init__(self, *args, comprador, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["endereco"].queryset = comprador.enderecos.all()
