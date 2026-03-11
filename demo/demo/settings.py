"""Django settings for django-dolt demo application.

This demo demonstrates multi-database support with two Dolt databases:
- inventory: Product inventory tracking
- orders: Customer orders tracking

Each database has its own version history, branches, and commits visible
in Django admin.
"""

import os
from pathlib import Path

# Use PyMySQL as MySQL driver
import pymysql
pymysql.install_as_MySQLdb()
# Patch version to satisfy Django's mysqlclient version check
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.VERSION = pymysql.version_info

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "demo-secret-key-not-for-production"

DEBUG = True

ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_dolt",
    "demo_app",
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

ROOT_URLCONF = "demo.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "demo.wsgi.application"

# Database configuration
# Default database uses SQLite for Django's auth/session tables
# Two Dolt databases for the demo application data

DOLT_HOST = os.environ.get("DOLT_HOST", "127.0.0.1")
DOLT_PORT = int(os.environ.get("DOLT_PORT", "8906"))
DOLT_USER = os.environ.get("DOLT_USER", "root")
DOLT_PASSWORD = os.environ.get("DOLT_PASSWORD", "dolt")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    },
    "inventory": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": DOLT_HOST,
        "PORT": DOLT_PORT,
        "USER": DOLT_USER,
        "PASSWORD": DOLT_PASSWORD,
        "NAME": "inventory",
    },
    "orders": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": DOLT_HOST,
        "PORT": DOLT_PORT,
        "USER": DOLT_USER,
        "PASSWORD": DOLT_PASSWORD,
        "NAME": "orders",
    },
}

# Database routing for demo models
DATABASE_ROUTERS = ["demo.routers.DemoRouter"]

# Dolt databases to manage via django-dolt
# Dolt databases to manage via django-dolt
DOLT_DATABASES = ["inventory", "orders"]

# Disable auto-registration on admin.site since we use DoltAdminSite
DOLT_AUTO_REGISTER_ADMIN = False

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
