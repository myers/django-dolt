"""Django settings for django-dolt tests."""

import os

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
    }
}

# Add Dolt databases if DOLT_HOST is set (for integration tests)
if os.environ.get("DOLT_HOST"):
    DATABASES.update(
        {
            "dolt": {
                "ENGINE": "django.db.backends.mysql",
                "HOST": os.environ.get("DOLT_HOST", "127.0.0.1"),
                "PORT": int(os.environ.get("DOLT_PORT", "3306")),
                "USER": os.environ.get("DOLT_USER", "root"),
                "PASSWORD": os.environ.get("DOLT_PASSWORD", "dolt"),
                "NAME": "information_schema",  # Connect to root for DB creation
            },
            "dolt1": {
                "ENGINE": "django.db.backends.mysql",
                "HOST": os.environ.get("DOLT_HOST", "127.0.0.1"),
                "PORT": int(os.environ.get("DOLT_PORT", "3306")),
                "USER": os.environ.get("DOLT_USER", "root"),
                "PASSWORD": os.environ.get("DOLT_PASSWORD", "dolt"),
                "NAME": "test_dolt1",
            },
            "dolt2": {
                "ENGINE": "django.db.backends.mysql",
                "HOST": os.environ.get("DOLT_HOST", "127.0.0.1"),
                "PORT": int(os.environ.get("DOLT_PORT", "3306")),
                "USER": os.environ.get("DOLT_USER", "root"),
                "PASSWORD": os.environ.get("DOLT_PASSWORD", "dolt"),
                "NAME": "test_dolt2",
            },
        }
    )

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
