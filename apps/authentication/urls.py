from django.urls import path
from apps.authentication import views

app_name = "auth"
urlpatterns = [
    path("login/",                       views.LoginView.as_view(),               name="login"),
    path("logout/",                      views.LogoutView.as_view(),              name="logout"),
    path("register/",                    views.RegisterView.as_view(),            name="register"),
    path("verify/<uuid:token>/",         views.VerifyEmailView.as_view(),         name="verify"),
    path("password-reset/",              views.PasswordResetView.as_view(),       name="password-reset"),
    path("password-reset/<uuid:token>/", views.PasswordResetConfirmView.as_view(),name="password-reset-confirm"),
    path("google/",                      views.GoogleLoginView.as_view(),         name="google-login"),
    path("google/callback/",             views.GoogleCallbackView.as_view(),      name="google-callback"),
]
