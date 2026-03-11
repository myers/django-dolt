"""Django settings for django-dolt tests."""

import os

import pymysql

pymysql.install_as_MySQLdb()
# Django 6.0 requires mysqlclient 2.2.1+; pymysql reports 1.4.6.
# Patch the version so Django's MySQL backend accepts pymysql.
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.VERSION = pymysql.version_info

SECRET_KEY = "test-secret-key-not-for-production"

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.admin",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django_dolt",
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
    "dolt": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": os.environ.get("DOLT_HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("DOLT_PORT", "8906")),
        "USER": os.environ.get("DOLT_USER", "root"),
        "PASSWORD": os.environ.get("DOLT_PASSWORD", "dolt"),
        "NAME": "information_schema",
        "TEST": {"DEPENDENCIES": [], "NAME": "information_schema"},
    },
    "dolt1": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": os.environ.get("DOLT_HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("DOLT_PORT", "8906")),
        "USER": os.environ.get("DOLT_USER", "root"),
        "PASSWORD": os.environ.get("DOLT_PASSWORD", "dolt"),
        "NAME": "test_dolt1",
        "TEST": {"DEPENDENCIES": [], "NAME": "test_dolt1"},
    },
    "dolt2": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": os.environ.get("DOLT_HOST", "127.0.0.1"),
        "PORT": int(os.environ.get("DOLT_PORT", "8906")),
        "USER": os.environ.get("DOLT_USER", "root"),
        "PASSWORD": os.environ.get("DOLT_PASSWORD", "dolt"),
        "NAME": "test_dolt2",
        "TEST": {"DEPENDENCIES": [], "NAME": "test_dolt2"},
    },
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
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

USE_TZ = True

DOLT_DATABASES = ["dolt", "dolt1", "dolt2"]
