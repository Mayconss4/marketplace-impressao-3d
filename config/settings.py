"""
Configurações do projeto Marketplace de Impressão 3D (GAC116).

Valores sensíveis podem ser sobrescritos por variáveis de ambiente; os padrões
abaixo destinam-se exclusivamente ao ambiente de desenvolvimento.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-somente-desenvolvimento-troque-em-producao-7c1f9b2e",
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")


# ---------------------------------------------------------------------------
# Aplicações
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Jazzmin precisa vir antes de django.contrib.admin para sobrescrever os templates.
    "jazzmin",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps do projeto (ordem respeita a direção das dependências)
    "apps.core",
    "apps.contas",
    "apps.vendedores",
    "apps.catalogo",
    "apps.orcamentos",
    "apps.pedidos",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.pedidos.contexto.carrinho",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Banco de dados relacional (SQLite)
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "contas.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "core:login"
LOGIN_REDIRECT_URL = "core:painel"
LOGOUT_REDIRECT_URL = "core:home"


# ---------------------------------------------------------------------------
# Internacionalização
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# Arquivos estáticos e de mídia
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Mídia PÚBLICA: logotipos de lojas e imagens de produtos.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Mídia PRIVADA: arquivos digitais à venda e arquivos 3D de orçamentos.
# Fica fora de MEDIA_ROOT e nunca é servida diretamente; o acesso passa pela
# view core:arquivo_privado, que verifica autenticação e autorização.
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Jazzmin — identidade visual do ambiente administrativo
# ---------------------------------------------------------------------------
JAZZMIN_SETTINGS = {
    "site_title": "Marketplace 3D | Administração",
    "site_header": "Marketplace 3D",
    "site_brand": "Marketplace 3D",
    "site_logo": "img/logo.svg",
    "login_logo": "img/logo.svg",
    "login_logo_dark": "img/logo.svg",
    "site_logo_classes": "img-fluid",
    "site_icon": "img/logo.svg",
    "welcome_sign": "Painel do Marketplace de Impressão 3D",
    "copyright": "GAC116 — Programação Web",
    # Busca global do topo: só modelos que vendedores também podem consultar
    # (o Jazzmin não filtra esta lista por permissão).
    "search_model": ["catalogo.Produto", "vendedores.Loja"],
    "user_avatar": None,
    "topmenu_links": [
        {"name": "Início do painel", "url": "admin:index"},
        {"name": "Ver marketplace", "url": "core:home", "new_window": True},
        {"model": "catalogo.Produto"},
        {"model": "pedidos.SubPedido"},
    ],
    "usermenu_links": [
        {"name": "Ver marketplace", "url": "core:home", "new_window": True, "icon": "fas fa-store"},
    ],
    "show_sidebar": True,
    "navigation_expanded": True,
    "order_with_respect_to": [
        "vendedores",
        "vendedores.SolicitacaoVendedor",
        "vendedores.PerfilVendedor",
        "vendedores.Loja",
        "catalogo",
        "catalogo.Categoria",
        "catalogo.Produto",
        "catalogo.VariacaoProduto",
        "orcamentos",
        "pedidos",
        "pedidos.Pedido",
        "pedidos.SubPedido",
        "pedidos.PagamentoSimulado",
        "pedidos.Carrinho",
        "contas",
        "contas.Usuario",
        "contas.Endereco",
        "auth",
    ],
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.Group": "fas fa-user-shield",
        "contas": "fas fa-id-card",
        "contas.Usuario": "fas fa-user",
        "contas.Endereco": "fas fa-map-marker-alt",
        "vendedores": "fas fa-store",
        "vendedores.SolicitacaoVendedor": "fas fa-user-check",
        "vendedores.PerfilVendedor": "fas fa-user-tie",
        "vendedores.Loja": "fas fa-store-alt",
        "catalogo": "fas fa-cubes",
        "catalogo.Categoria": "fas fa-sitemap",
        "catalogo.Produto": "fas fa-cube",
        "catalogo.VariacaoProduto": "fas fa-layer-group",
        "orcamentos": "fas fa-file-invoice-dollar",
        "orcamentos.Orcamento": "fas fa-file-signature",
        "pedidos": "fas fa-shopping-bag",
        "pedidos.Pedido": "fas fa-receipt",
        "pedidos.SubPedido": "fas fa-boxes",
        "pedidos.PagamentoSimulado": "fas fa-money-check",
        "pedidos.Carrinho": "fas fa-shopping-cart",
    },
    "default_icon_parents": "fas fa-folder",
    "default_icon_children": "fas fa-circle",
    "related_modal_active": True,
    "custom_css": "css/admin.css",
    "custom_js": None,
    "use_google_fonts_cdn": True,
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    "changeform_format_overrides": {
        "contas.usuario": "collapsible",
        "auth.group": "vertical_tabs",
    },
    "language_chooser": False,
}

JAZZMIN_UI_TWEAKS = {
    "navbar_small_text": False,
    "footer_small_text": True,
    "body_small_text": False,
    "brand_small_text": False,
    "brand_colour": "navbar-orange",
    "accent": "accent-orange",
    "navbar": "navbar-dark navbar-gray-dark",
    "no_navbar_border": True,
    "navbar_fixed": True,
    "layout_boxed": False,
    "footer_fixed": False,
    "sidebar_fixed": True,
    "sidebar": "sidebar-dark-orange",
    "sidebar_nav_small_text": False,
    "sidebar_disable_expand": False,
    "sidebar_nav_child_indent": True,
    "sidebar_nav_compact_style": False,
    "sidebar_nav_legacy_style": False,
    "sidebar_nav_flat_style": False,
    "theme": "flatly",
    # Jazzmin 3: qualquer tema funciona em claro/escuro; "auto" segue o sistema operacional.
    "default_theme_mode": "auto",
    "button_classes": {
        "primary": "btn-primary",
        "secondary": "btn-secondary",
        "info": "btn-info",
        "warning": "btn-warning",
        "danger": "btn-danger",
        "success": "btn-success",
    },
}
