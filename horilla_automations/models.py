# horilla_automations/models.py
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _trans

from base.models import HorillaMailTemplate
from horilla.models import HorillaModel
from horilla_views.cbv_methods import render_template

CONDITIONS = [
    ("equal", _trans("Equal (==)")),
    ("notequal", _trans("Not Equal (!=)")),
    ("lt", _trans("Less Than (<)")),
    ("gt", _trans("Greater Than (>)")),
    ("le", _trans("Less Than or Equal To (<=)")),
    ("ge", _trans("Greater Than or Equal To (>=)")),
    ("icontains", _trans("Contains")),
]


class MailAutomation(HorillaModel):
    """
    MailAutoMation
    """

    choices = [
        ("on_create", "On Create"),
        ("on_update", "On Update"),
        ("on_delete", "On Delete"),
    ]
    
    title = models.CharField(max_length=256, unique=True)
    method_title = models.CharField(max_length=50, editable=False)
    
    # CORRECTION : Supprimer totalement les choices du modèle
    model = models.CharField(max_length=100, null=False, blank=False)
    
    mail_to = models.TextField(verbose_name="Mail to")
    mail_details = models.CharField(
        max_length=250,
        help_text="Fill mail template details(reciever/instance, `self` will be the person who trigger the automation)",
    )
    mail_detail_choice = models.TextField(default="", editable=False)
    trigger = models.CharField(max_length=10, choices=choices)
    mail_template = models.ForeignKey(HorillaMailTemplate, on_delete=models.CASCADE)
    template_attachments = models.ManyToManyField(
        HorillaMailTemplate,
        related_name="template_attachment",
        blank=True,
    )
    condition_html = models.TextField(null=True, editable=False)
    condition_querystring = models.TextField(null=True, editable=False)
    condition = models.TextField()
    
    # Champ pour les destinataires supplémentaires en copie
    also_sent_to = models.ManyToManyField(
        'employee.Employee',
        blank=True,
        related_name='automation_cc_emails',
        verbose_name="Also Sent to",
        help_text="The employees selected here will receive the email as Cc."
    )

    def save(self, *args, **kwargs):
        if not self.pk:
            self.method_title = self.title.replace(" ", "_").lower()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.title

    def get_avatar(self):
        """
        Method will retun the api to the avatar or path to the profile image
        """
        url = f"https://ui-avatars.com/api/?name={self.title}&background=random"
        return url

    def get_mail_to_display(self):
        """
        method that returns the display value for `mail_to`
        field
        """
        try:
            mail_to = eval(self.mail_to)
            mappings = []
            for mapping in mail_to:
                mapping = mapping.split("__")
                display = ""
                for split in mapping:
                    split = split.replace("_id", "").replace("_", " ")
                    split = split.capitalize()
                    display = display + f"{split} >"
                display = display[:-1]
                mappings.append(display)
            return render_template(
                "horilla_automations/mail_to.html", {"instance": self, "mappings": mappings}
            )
        except Exception:
            return "Invalid mail configuration"

    def detailed_url(self):
        return reverse("automation-detailed-view", kwargs={"pk": self.pk})

    def conditions(self):
        return render_template(
            "horilla_automations/conditions.html", {"instance": self}
        )

    def delete_url(self):
        return reverse("delete-automation", kwargs={"pk": self.pk})

    def edit_url(self):
        """
        Edit url
        """
        return reverse("update-automation", kwargs={"pk": self.pk})

    def trigger_display(self):
        """"""
        return self.get_trigger_display()