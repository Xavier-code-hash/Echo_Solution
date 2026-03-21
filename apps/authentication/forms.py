from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from apps.authentication.models import User


class LoginForm(forms.Form):
    email    = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "you@email.com", "autofocus": "autofocus"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}))
    remember = forms.BooleanField(required=False)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self._user   = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cd       = super().clean()
        email    = cd.get("email", "").lower()
        password = cd.get("password", "")
        if email and password:
            try:
                u = User.objects.get(email=email)
                if u.is_locked:
                    raise ValidationError("Account temporarily locked. Try again in 30 minutes.")
            except User.DoesNotExist:
                pass
            self._user = authenticate(self.request, email=email, password=password)
            if self._user is None:
                try:
                    User.objects.get(email=email).record_failed_login()
                except User.DoesNotExist:
                    pass
                raise ValidationError("Incorrect email or password.")
            if not self._user.is_active:
                raise ValidationError("This account has been deactivated.")
            self._user.clear_failed_logins()
        return cd

    def get_user(self):
        return self._user


class RegisterForm(forms.ModelForm):
    password1   = forms.CharField(label="Password", min_length=10,
                                  widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Min. 10 characters"}))
    password2   = forms.CharField(label="Confirm password",
                                  widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Repeat password"}))
    agree_terms = forms.BooleanField(error_messages={"required": "You must accept the Terms of Service."})

    class Meta:
        model  = User
        fields = ["first_name", "last_name", "email", "phone", "role"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
            "last_name":  forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
            "email":      forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email address"}),
            "phone":      forms.TextInput(attrs={"class": "form-control", "placeholder": "+254 7XX XXX XXX"}),
            "role":       forms.Select(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [
            ("", "— I am a —"),
            (User.Role.OWNER,   "Property Owner / Landlord"),
            (User.Role.MANAGER, "Property Manager"),
            (User.Role.TENANT,  "Tenant"),
        ]

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cd = super().clean()
        if cd.get("password1") and cd.get("password1") != cd.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        return cd

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class PasswordResetForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "your@email.com"}))


class SetPasswordForm(forms.Form):
    password1 = forms.CharField(label="New password", min_length=10,
                                widget=forms.PasswordInput(attrs={"class": "form-control"}))
    password2 = forms.CharField(label="Confirm",
                                widget=forms.PasswordInput(attrs={"class": "form-control"}))

    def clean(self):
        cd = super().clean()
        if cd.get("password1") != cd.get("password2"):
            self.add_error("password2", "Passwords do not match.")
        return cd
