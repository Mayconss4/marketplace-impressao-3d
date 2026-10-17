import re

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, RegexValidator

FORMATOS_3D = ["stl", "3mf", "obj", "step", "stp"]  # .stp é a extensão alternativa do STEP

validar_arquivo_3d = FileExtensionValidator(
    allowed_extensions=FORMATOS_3D,
    message="Formato não aceito. Envie um arquivo STL, 3MF, OBJ ou STEP (.step/.stp).",
)

validar_telefone = RegexValidator(
    regex=r"^\(?\d{2}\)?\s?9?\d{4}-?\d{4}$",
    message="Informe um telefone com DDD, por exemplo (35) 99999-0000.",
)


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def calcular_digito(digitos, pesos):
    resto = sum(int(d) * p for d, p in zip(digitos, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cpf_valido(valor):
    cpf = somente_digitos(valor)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    d1 = calcular_digito(cpf[:9], range(10, 1, -1))
    d2 = calcular_digito(cpf[:9] + d1, range(11, 1, -1))
    return cpf[-2:] == d1 + d2


def cnpj_valido(valor):
    cnpj = somente_digitos(valor)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    d1 = calcular_digito(cnpj[:12], pesos1)
    d2 = calcular_digito(cnpj[:12] + d1, [6] + pesos1)
    return cnpj[-2:] == d1 + d2


def validar_cpf(valor):
    if not cpf_valido(valor):
        raise ValidationError("CPF inválido.", code="cpf_invalido")


def validar_cnpj(valor):
    if not cnpj_valido(valor):
        raise ValidationError("CNPJ inválido.", code="cnpj_invalido")


def formatar_cpf(cpf):
    return f"{cpf[:3]}.{cpf[3:6]}.{cpf[6:9]}-{cpf[9:]}" if len(cpf) == 11 else cpf


def formatar_cnpj(cnpj):
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else cnpj
