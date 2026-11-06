from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm


class FormularioBootstrap:
    """Aplica as classes do Bootstrap aos widgets de qualquer formulário."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect)):
                classe = "form-check-input"
            elif isinstance(widget, forms.Select):
                classe = "form-select"
            else:
                classe = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {classe}".strip()


class FormularioLogin(FormularioBootstrap, AuthenticationForm):
    """Formulário de login padrão do Django com classes do Bootstrap."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nome de usuário"
        self.fields["password"].label = "Senha"
        self.fields["username"].widget.attrs["autofocus"] = True


class FormularioTrocaSenha(FormularioBootstrap, PasswordChangeForm):
    pass
