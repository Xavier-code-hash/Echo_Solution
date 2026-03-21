"""Authentication views — login, register, Google OAuth2, password reset."""
import logging
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from apps.authentication.forms import LoginForm, RegisterForm, PasswordResetForm, SetPasswordForm
from apps.authentication.models import User, EmailToken

log = logging.getLogger("apps.authentication")


@method_decorator([csrf_protect, never_cache], name="dispatch")
class LoginView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, "auth/login.html", {
            "form": LoginForm(request),
            "google_client_id": settings.GOOGLE_CLIENT_ID,
        })

    def post(self, request):
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if getattr(settings, "REQUIRE_EMAIL_VERIFICATION", False) and not user.email_verified:
                messages.error(request, "Please verify your email before signing in.")
                return redirect("auth:login")
            if not form.cleaned_data.get("remember"):
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 14)
            ip = request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))
            user.last_login_ip = ip.split(",")[0].strip()
            user.save(update_fields=["last_login_ip"])
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_short_name()}!")
            next_url = _get_next_url(request)
            return redirect(next_url or "dashboard:home")
        return render(request, "auth/login.html", {
            "form": form,
            "google_client_id": settings.GOOGLE_CLIENT_ID,
        })


class LogoutView(View):
    def post(self, request):
        logout(request)
        messages.info(request, "You've been signed out.")
        return redirect("landing:home")


@method_decorator([csrf_protect, never_cache], name="dispatch")
class RegisterView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect("dashboard:home")
        return render(request, "auth/register.html", {
            "form": RegisterForm(),
            "google_client_id": settings.GOOGLE_CLIENT_ID,
        })

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            _send_verification(user, request)
            messages.success(request, "Account created! Please check your email to verify.")
            return redirect("auth:login")
        return render(request, "auth/register.html", {
            "form": form,
            "google_client_id": settings.GOOGLE_CLIENT_ID,
        })


class VerifyEmailView(View):
    def get(self, request, token):
        try:
            et = EmailToken.objects.select_related("user").get(
                token=token, purpose=EmailToken.Purpose.VERIFY)
            if et.is_valid():
                et.user.email_verified = True
                et.user.save(update_fields=["email_verified"])
                et.used = True
                et.save(update_fields=["used"])
                messages.success(request, "Email verified! You can now log in.")
            else:
                messages.error(request, "Verification link has expired.")
        except EmailToken.DoesNotExist:
            messages.error(request, "Invalid verification link.")
        return redirect("auth:login")


@method_decorator([csrf_protect, never_cache], name="dispatch")
class PasswordResetView(View):
    def get(self, request):
        return render(request, "auth/password_reset.html", {"form": PasswordResetForm()})

    def post(self, request):
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            try:
                user = User.objects.get(email=form.cleaned_data["email"].lower())
                _send_reset_email(user, request)
            except User.DoesNotExist:
                pass
            messages.success(request, "If that email is registered, a reset link has been sent.")
        return render(request, "auth/password_reset.html", {"form": form})


@method_decorator([csrf_protect, never_cache], name="dispatch")
class PasswordResetConfirmView(View):
    def get(self, request, token):
        if not _get_valid_token(token, EmailToken.Purpose.RESET):
            messages.error(request, "Invalid or expired reset link.")
            return redirect("auth:password-reset")
        return render(request, "auth/password_reset_confirm.html",
                      {"form": SetPasswordForm(), "token": token})

    def post(self, request, token):
        et = _get_valid_token(token, EmailToken.Purpose.RESET)
        if not et:
            messages.error(request, "Invalid or expired reset link.")
            return redirect("auth:password-reset")
        form = SetPasswordForm(request.POST)
        if form.is_valid():
            et.user.set_password(form.cleaned_data["password1"])
            et.user.save()
            et.used = True
            et.save(update_fields=["used"])
            messages.success(request, "Password updated. Please log in.")
            return redirect("auth:login")
        return render(request, "auth/password_reset_confirm.html",
                      {"form": form, "token": token})


class GoogleLoginView(View):
    def get(self, request):
        if not settings.GOOGLE_CLIENT_ID:
            messages.error(request, "Google login is not configured.")
            return redirect("auth:login")
        from google_auth_oauthlib.flow import Flow
        flow = _make_flow(settings)
        auth_url, state = flow.authorization_url(access_type="offline", include_granted_scopes="true")
        request.session["g_state"] = state
        return redirect(auth_url)


class GoogleCallbackView(View):
    def get(self, request):
        import google.oauth2.id_token
        import google.auth.transport.requests as gr
        from google_auth_oauthlib.flow import Flow

        flow = _make_flow(settings, state=request.session.get("g_state"))
        try:
            flow.fetch_token(authorization_response=request.build_absolute_uri())
            id_info = google.oauth2.id_token.verify_oauth2_token(
                flow.credentials.id_token, gr.Request(), settings.GOOGLE_CLIENT_ID)
            email   = id_info["email"]
            gid     = id_info["sub"]
            user, _ = User.objects.get_or_create(email=email, defaults={
                "first_name": id_info.get("given_name", ""),
                "last_name":  id_info.get("family_name", ""),
                "google_id":  gid,
                "email_verified": True,
                "role": User.Role.OWNER,
            })
            if not user.google_id:
                user.google_id = gid
                user.email_verified = True
                user.save(update_fields=["google_id", "email_verified"])
            login(request, user)
            messages.success(request, f"Welcome, {user.get_short_name()}!")
            return redirect("dashboard:home")
        except Exception as e:
            log.error("Google OAuth error: %s", e)
            messages.error(request, "Google sign-in failed. Please try again.")
            return redirect("auth:login")


# ─── Helpers ────────────────────────────────────────────────

def _make_flow(settings, state=None):
    from google_auth_oauthlib.flow import Flow
    cfg = {"web": {
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "auth_uri":      "https://accounts.google.com/o/oauth2/auth",
        "token_uri":     "https://oauth2.googleapis.com/token",
        "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
    }}
    kwargs = {"scopes": ["openid", "email", "profile"]}
    if state:
        kwargs["state"] = state
    flow = Flow.from_client_config(cfg, **kwargs)
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def _get_valid_token(token, purpose):
    try:
        et = EmailToken.objects.select_related("user").get(token=token, purpose=purpose)
        return et if et.is_valid() else None
    except EmailToken.DoesNotExist:
        return None


def _get_next_url(request):
    next_url = request.GET.get("next")
    if not next_url:
        return None
    if url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
        return next_url
    return None


def _send_verification(user, request):
    from django.urls import reverse
    from apps.messaging.services import send_email
    et  = EmailToken.objects.create(user=user, purpose=EmailToken.Purpose.VERIFY,
                                    expires_at=timezone.now() + timedelta(hours=24))
    url = request.build_absolute_uri(reverse("auth:verify", kwargs={"token": et.token}))
    send_email(user.email, "Verify your Echo_Solutions account",
               f"Hi {user.get_short_name()},\n\nClick to verify:\n{url}\n\nExpires in 24 hours.")


def _send_reset_email(user, request):
    from django.urls import reverse
    from apps.messaging.services import send_email
    et  = EmailToken.objects.create(user=user, purpose=EmailToken.Purpose.RESET,
                                    expires_at=timezone.now() + timedelta(hours=2))
    url = request.build_absolute_uri(reverse("auth:password-reset-confirm", kwargs={"token": et.token}))
    send_email(user.email, "Reset your Echo_Solutions password",
               f"Hi {user.get_short_name()},\n\nReset link (2h):\n{url}\n\nIgnore if you didn't request this.")
