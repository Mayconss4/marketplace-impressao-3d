"""Gera, em memória, arquivos fictícios para a demonstração.

Tudo aqui é produzido pelo próprio projeto (nenhum arquivo de terceiros):
imagens de capa/logotipo desenhadas com Pillow e modelos 3D de um cubo simples.
"""

import io
import zipfile

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont

_VERTICES = [(0, 0, 0), (20, 0, 0), (20, 20, 0), (0, 20, 0), (0, 0, 20), (20, 0, 20), (20, 20, 20), (0, 20, 20)]
_FACES = [(0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7), (0, 1, 5), (0, 5, 4),
          (1, 2, 6), (1, 6, 5), (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)]


def _fonte(tamanho):
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:  # Pillow antigo
        return ImageFont.load_default()


def _cubo_isometrico(draw, cx, cy, lado, cores):
    topo, esquerda, direita = cores
    h = lado // 2
    draw.polygon([(cx, cy - lado), (cx + lado, cy - h), (cx, cy), (cx - lado, cy - h)], fill=topo)
    draw.polygon([(cx - lado, cy - h), (cx, cy), (cx, cy + lado), (cx - lado, cy + h)], fill=esquerda)
    draw.polygon([(cx + lado, cy - h), (cx, cy), (cx, cy + lado), (cx + lado, cy + h)], fill=direita)


def imagem_produto(titulo, cor_hex, nome_arquivo, variante=0):
    largura, altura = 800, 600
    base = tuple(int(cor_hex[i : i + 2], 16) for i in (1, 3, 5))
    clara = tuple(min(255, c + 70) for c in base)
    escura = tuple(max(0, c - 70) for c in base)
    img = Image.new("RGB", (largura, altura), (245, 245, 244))
    draw = ImageDraw.Draw(img)
    for y in range(altura):  # degradê suave de fundo
        t = y / altura
        draw.line([(0, y), (largura, y)], fill=tuple(int(250 - 30 * t + (c - 230) * 0.08) for c in base))
    # Camadas horizontais lembrando a impressão FDM
    for y in range(380, 470, 9):
        draw.line([(220, y), (580, y)], fill=escura, width=2)
    _cubo_isometrico(draw, 400 + variante * 40, 300, 150, (clara, base, escura))
    draw.text((40, 530), titulo, fill=(31, 41, 55), font=_fonte(34))
    draw.text((40, 30), "Imagem demonstrativa", fill=(107, 114, 128), font=_fonte(20))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return ContentFile(buffer.getvalue(), name=nome_arquivo)


def logotipo(sigla, cor_hex, nome_arquivo):
    base = tuple(int(cor_hex[i : i + 2], 16) for i in (1, 3, 5))
    img = Image.new("RGB", (400, 400), base)
    draw = ImageDraw.Draw(img)
    _cubo_isometrico(draw, 200, 170, 90, ((255, 255, 255), (229, 231, 235), (209, 213, 219)))
    draw.text((200, 330), sigla, fill=(255, 255, 255), font=_fonte(56), anchor="mm")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return ContentFile(buffer.getvalue(), name=nome_arquivo)


def stl_cubo(nome_arquivo, nome_solido="cubo_demo"):
    linhas = [f"solid {nome_solido}"]
    for a, b, c in _FACES:
        linhas += ["  facet normal 0 0 0", "    outer loop"]
        linhas += [f"      vertex {x} {y} {z}" for x, y, z in (_VERTICES[a], _VERTICES[b], _VERTICES[c])]
        linhas += ["    endloop", "  endfacet"]
    linhas.append(f"endsolid {nome_solido}")
    return ContentFile("\n".join(linhas).encode(), name=nome_arquivo)


def obj_cubo(nome_arquivo):
    linhas = ["# Cubo demonstrativo — Marketplace 3D"]
    linhas += [f"v {x} {y} {z}" for x, y, z in _VERTICES]
    linhas += [f"f {a + 1} {b + 1} {c + 1}" for a, b, c in _FACES]
    return ContentFile("\n".join(linhas).encode(), name=nome_arquivo)


def tmf_cubo(nome_arquivo):
    vertices = "".join(f'<vertex x="{x}" y="{y}" z="{z}"/>' for x, y, z in _VERTICES)
    triangulos = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in _FACES)
    modelo = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<model unit="millimeter" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
        f'<resources><object id="1" type="model"><mesh><vertices>{vertices}</vertices>'
        f"<triangles>{triangulos}</triangles></mesh></object></resources>"
        '<build><item objectid="1"/></build></model>'
    )
    tipos = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as pacote:
        pacote.writestr("[Content_Types].xml", tipos)
        pacote.writestr("_rels/.rels", rels)
        pacote.writestr("3D/3dmodel.model", modelo)
    return ContentFile(buffer.getvalue(), name=nome_arquivo)


def step_demo(nome_arquivo):
    conteudo = (
        "ISO-10303-21;\nHEADER;\n"
        "FILE_DESCRIPTION(('Arquivo STEP demonstrativo - Marketplace 3D'),'2;1');\n"
        f"FILE_NAME('{nome_arquivo}','2026-01-01T00:00:00',('Marketplace 3D'),(''),'','','');\n"
        "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    )
    return ContentFile(conteudo.encode(), name=nome_arquivo)
