from django.views.generic import TemplateView
from django.views import View
from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from apps.landing.forms import CallbackRequestForm, ContactMessageForm
from apps.messaging.services import send_email


class HomeView(TemplateView):
    template_name = "landing/index.html"


class AboutView(TemplateView):
    template_name = "landing/about.html"


def _contact_recipient() -> str:
    return (getattr(settings, "CONTACT_EMAIL", "") or
            getattr(settings, "GMAIL_SENDER", "") or
            settings.DEFAULT_FROM_EMAIL)


class ContactView(View):
    template_name = "landing/contact.html"

    def get(self, request):
        return render(request, self.template_name, {
            "callback_form": CallbackRequestForm(),
            "contact_form":  ContactMessageForm(),
        })

    def post(self, request):
        form_type = request.POST.get("form_type", "")
        callback_form = CallbackRequestForm()
        contact_form  = ContactMessageForm()

        if form_type == "callback":
            callback_form = CallbackRequestForm(request.POST)
            if callback_form.is_valid():
                req = callback_form.save()
                subj = f"Callback request — {req.full_name}"
                body = (
                    f"Name: {req.full_name}\n"
                    f"Phone: {req.phone}\n"
                    f"Email: {req.email or '-'}\n"
                    f"Preferred time: {req.get_preferred_time_display()}\n\n"
                    f"Message:\n{req.message or '-'}"
                )
                ok = send_email(_contact_recipient(), subj, body)
                if ok:
                    messages.success(request, "Thanks! We'll call you back shortly.")
                else:
                    messages.warning(request, "Request saved, but email delivery failed.")
                return redirect("landing:contact")
            messages.error(request, "Please correct the callback form errors.")

        elif form_type == "message":
            contact_form = ContactMessageForm(request.POST)
            if contact_form.is_valid():
                data = contact_form.cleaned_data
                subj = f"Contact message — {data['subject']}"
                body = (
                    f"From: {data['first_name']} {data['last_name']}\n"
                    f"Email: {data['email']}\n\n"
                    f"{data['message']}"
                )
                ok = send_email(_contact_recipient(), subj, body)
                if ok:
                    messages.success(request, "Message sent successfully.")
                else:
                    messages.warning(request, "Message could not be delivered. Please try again.")
                return redirect("landing:contact")
            messages.error(request, "Please correct the message form errors.")

        else:
            messages.error(request, "Invalid form submission.")

        return render(request, self.template_name, {
            "callback_form": callback_form,
            "contact_form":  contact_form,
        })
