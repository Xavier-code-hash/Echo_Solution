"""
Echo_Solutions – Base Settings
All environments inherit from here.
"""
from pathlib import Path
import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
env = environ.Env(DEBUG=(bool, False))

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    environ.Env.read_env(_env_file)

SECRET_KEY    = env("SECRET_KEY", default="django-insecure-dev-key-change-in-prod-abc123xyz")
DEBUG         = env("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# ─── Apps ────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Third-party
    "rest_framework",
    "corsheaders",
    # Local
    "apps.authentication",
    "apps.properties",
    "apps.tenants",
    "apps.payments",
    "apps.maintenance",
    "apps.messaging",
    "apps.dashboard",
    "apps.reports",
    "apps.landing",
]

# ─── Middleware ──────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF     = "Echo_Solutions.urls"
WSGI_APPLICATION = "Echo_Solutions.wsgi.application"

# ─── Templates ──────────────────────────────────────────────
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "apps.dashboard.context_processors.global_context",
    ]},
}]

# ─── Database ────────────────────────────────────────────────
DATABASES = {"default": {
    "ENGINE":   env("DB_ENGINE",   default="django.db.backends.sqlite3"),
    "NAME":     env("DB_NAME",     default=str(BASE_DIR / "db.sqlite3")),
    "USER":     env("DB_USER",     default=""),
    "PASSWORD": env("DB_PASSWORD", default=""),
    "HOST":     env("DB_HOST",     default="localhost"),
    "PORT":     env("DB_PORT",     default="5432"),
}}

# ─── Auth ────────────────────────────────────────────────────
AUTH_USER_MODEL = "authentication.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
REQUIRE_EMAIL_VERIFICATION = env.bool("REQUIRE_EMAIL_VERIFICATION", default=False)
LOGIN_URL           = "/auth/login/"
LOGIN_REDIRECT_URL  = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ─── Sessions ────────────────────────────────────────────────
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE      = 3600
CSRF_COOKIE_HTTPONLY    = False
CSRF_COOKIE_SAMESITE    = "Lax"
X_FRAME_OPTIONS         = "DENY"

# ─── Static / Media ──────────────────────────────────────────
STATIC_URL       = "/static/"
STATIC_ROOT      = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL        = "/media/"
MEDIA_ROOT       = BASE_DIR / "media"

# ─── i18n ────────────────────────────────────────────────────
LANGUAGE_CODE      = "en-us"
TIME_ZONE          = "Africa/Nairobi"
USE_I18N = USE_TZ  = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── DRF ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES":     ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/hour", "user": "2000/day"},
}

# ─── CORS ────────────────────────────────────────────────────
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS   = env.list("CORS_ALLOWED_ORIGINS", default=["http://localhost:3000"])

# ─── External APIs ───────────────────────────────────────────
GOOGLE_CLIENT_ID     = env("GOOGLE_CLIENT_ID",     default="")
GOOGLE_CLIENT_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
GOOGLE_REDIRECT_URI  = env("GOOGLE_REDIRECT_URI",  default="http://localhost:8000/auth/google/callback/")

STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_SECRET_KEY      = env("STRIPE_SECRET_KEY",      default="")
STRIPE_WEBHOOK_SECRET  = env("STRIPE_WEBHOOK_SECRET",  default="")

MPESA_ENVIRONMENT     = env("MPESA_ENVIRONMENT",     default="sandbox")
MPESA_CONSUMER_KEY    = env("MPESA_CONSUMER_KEY",    default="")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE       = env("MPESA_SHORTCODE",       default="174379")
MPESA_PASSKEY         = env("MPESA_PASSKEY",         default="")
MPESA_CALLBACK_URL    = env("MPESA_CALLBACK_URL",    default="https://yourdomain.com/payments/mpesa/callback/")

PAYPAL_CLIENT_ID     = env("PAYPAL_CLIENT_ID",     default="")
PAYPAL_CLIENT_SECRET = env("PAYPAL_CLIENT_SECRET", default="")
PAYPAL_ENVIRONMENT   = env("PAYPAL_ENVIRONMENT",   default="sandbox")

ENCRYPTION_KEY = env("ENCRYPTION_KEY", default="")
SITE_URL       = env("SITE_URL",       default="http://localhost:8000")

# ─── Email ───────────────────────────────────────────────────
# Use smtp.EmailBackend in all environments that need real sending.
# Override to console.EmailBackend locally if you don't want real sends.
EMAIL_BACKEND       = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST          = env("EMAIL_HOST",     default="smtp-relay.brevo.com")
EMAIL_PORT          = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS       = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER     = env("GMAIL_SENDER",        default="")   # Brevo SMTP login
EMAIL_HOST_PASSWORD = env("GMAIL_APP_PASSWORD",  default="")   # Brevo SMTP key
DEFAULT_FROM_EMAIL  = env("DEFAULT_FROM_EMAIL",  default="noreply@echo-solutions.com")  # Must be a verified sender in Brevo
CONTACT_EMAIL       = env("CONTACT_EMAIL", default=DEFAULT_FROM_EMAIL)

# ─── Logging ─────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "Echo_Solutions.log",
            "maxBytes": 5_242_880, "backupCount": 3,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "apps": {"handlers": ["console", "file"], "level": "DEBUG", "propagate": False},
    },
}