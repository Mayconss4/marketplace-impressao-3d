from django.contrib.auth.forms import AuthenticationForm


class FormularioLogin(AuthenticationForm):
    """Formulário de login padrão do Django com classes do Bootstrap."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Nome de usuário"
        self.fields["password"].label = "Senha"
        for campo in self.fields.values():
            campo.widget.attrs["class"] = "form-control"
        self.fields["username"].widget.attrs["autofocus"] = True
