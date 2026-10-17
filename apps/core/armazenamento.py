from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.urls import reverse
from django.utils.deconstruct import deconstructible
from django.utils.functional import cached_property


@deconstructible
class ArmazenamentoPrivado(FileSystemStorage):
    """Armazena arquivos em PRIVATE_MEDIA_ROOT, fora de MEDIA_ROOT.

    A URL gerada nunca aponta para o arquivo físico: aponta para a view
    protegida ``core:arquivo_privado``, que verifica quem está pedindo o arquivo
    antes de entregá-lo. Assim, conhecer a URL não basta para baixar o arquivo.
    """

    @cached_property
    def base_location(self):
        return self._value_or_setting(self._location, settings.PRIVATE_MEDIA_ROOT)

    def _clear_cached_properties(self, setting, **kwargs):
        super()._clear_cached_properties(setting, **kwargs)
        if setting == "PRIVATE_MEDIA_ROOT":
            self.__dict__.pop("base_location", None)
            self.__dict__.pop("location", None)

    def url(self, name):
        return reverse("core:arquivo_privado", args=[name])


armazenamento_privado = ArmazenamentoPrivado()
