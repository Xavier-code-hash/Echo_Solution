"""Custom User model with Argon2 hashing and login-lockout protection."""
import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError("Email required.")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("role", "admin")
        return self.create_user(email, password, **extra)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN   = "admin",   "Administrator"
        OWNER   = "owner",   "Property Owner"
        MANAGER = "manager", "Property Manager"
        TENANT  = "tenant",  "Tenant"
        STAFF   = "staff",   "Maintenance Staff"

    id             = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email          = models.EmailField(unique=True, db_index=True)
    first_name     = models.CharField(max_length=150)
    last_name      = models.CharField(max_length=150)
    phone          = models.CharField(max_length=30, blank=True)
    role           = models.CharField(max_length=20, choices=Role.choices, default=Role.TENANT)
    avatar         = models.ImageField(upload_to="avatars/", blank=True, null=True)
    email_verified = models.BooleanField(default=False)
    google_id      = models.CharField(max_length=120, blank=True, null=True, unique=True)
    is_active      = models.BooleanField(default=True)
    is_staff       = models.BooleanField(default=False)
    date_joined    = models.DateTimeField(default=timezone.now)
    last_login_ip  = models.GenericIPAddressField(null=True, blank=True)
    failed_logins  = models.PositiveSmallIntegerField(default=0)
    locked_until   = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD  = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]
    objects = UserManager()

    class Meta:
        verbose_name        = "User"
        verbose_name_plural = "Users"
        ordering            = ["-date_joined"]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_locked(self):
        return bool(self.locked_until and timezone.now() < self.locked_until)

    def record_failed_login(self):
        from datetime import timedelta
        self.failed_logins += 1
        if self.failed_logins >= 5:
            self.locked_until = timezone.now() + timedelta(minutes=30)
        self.save(update_fields=["failed_logins", "locked_until"])

    def clear_failed_logins(self):
        self.failed_logins = 0
        self.locked_until  = None
        self.save(update_fields=["failed_logins", "locked_until"])

    @property
    def is_owner_or_above(self):
        return self.role in (self.Role.ADMIN, self.Role.OWNER, self.Role.MANAGER)


class EmailToken(models.Model):
    class Purpose(models.TextChoices):
        VERIFY = "verify", "Email Verification"
        RESET  = "reset",  "Password Reset"
        INVITE = "invite", "Tenant Invite"

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user       = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens")
    token      = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    purpose    = models.CharField(max_length=10, choices=Purpose.choices)
    expires_at = models.DateTimeField()
    used       = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.purpose} — {self.user.email}"
