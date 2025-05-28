# horilla_automations/forms.py
"""
horilla_automations/forms.py
"""

from typing import Any

from django import forms
from django.utils.translation import gettext_lazy as _

from base.forms import ModelForm
from employee.filters import EmployeeFilter
from employee.models import Employee
from horilla_automations.methods.methods import generate_choices
from horilla_automations.models import MailAutomation
from horilla_widgets.widgets.horilla_multi_select_field import HorillaMultiSelectField
from horilla_widgets.widgets.select_widgets import HorillaMultiSelectWidget


class AutomationForm(ModelForm):
    """
    AutomationForm
    """

    condition_html = forms.CharField(widget=forms.HiddenInput())
    condition_querystring = forms.CharField(widget=forms.HiddenInput())

    cols = {"template_attachments": 12}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # CORRECTION : Redéfinir complètement le champ model comme ChoiceField
        model_choices = [
            ("", "Select model"),
            ("employee.models.Employee", "Employee"),
            ("recruitment.models.Candidate", "Candidate"),
            ("recruitment.models.Recruitment", "Recruitment"),
            ("recruitment.models.Stage", "Stage"),
            ("attendance.models.Attendance", "Attendance"),
            ("leave.models.LeaveRequest", "LeaveRequest"),
        ]
        
        self.fields["model"] = forms.ChoiceField(
            choices=model_choices,
            required=True,
            widget=forms.Select(attrs={
                "onchange": "getToMail($(this))",
                "class": "oh-select oh-select-2 w-100"
            })
        )
        
        self.fields["also_sent_to"] = HorillaMultiSelectField(
            queryset=Employee.objects.all(),
            required=False,
            widget=HorillaMultiSelectWidget(
                filter_route_name="employee-widget-filter",
                filter_class=EmployeeFilter,
                filter_instance_contex_name="f",
                filter_template_path="employee_filters.html",
                instance=self.instance,
            ),
            label="Also Sent to",
            help_text=_("The employees selected here will receive the email as Cc."),
        )
        
        if not self.data:
            mail_to = []
            initial = []
            mail_details_choice = []
            if self.instance.pk and self.instance.model:
                try:
                    mail_to = generate_choices(self.instance.model)[0]
                    mail_details_choice = generate_choices(self.instance.model)[1]
                except:
                    pass
                    
            self.fields["mail_to"] = forms.MultipleChoiceField(choices=mail_to, required=False)
            self.fields["mail_details"] = forms.ChoiceField(
                choices=mail_details_choice,
                required=False,
                help_text="Fill mail template details",
            )
            self.fields["mail_to"].initial = initial
            attrs = self.fields["mail_to"].widget.attrs
            attrs["class"] = "oh-select oh-select-2 w-100"
        
        self.fields["mail_template"].empty_label = "----------"
        
        if self.instance.pk:
            self.fields["condition"].initial = self.instance.condition_html
            self.fields["condition_html"].initial = self.instance.condition_html
            self.fields["condition_querystring"].initial = self.instance.condition_querystring

    class Meta:
        model = MailAutomation
        fields = "__all__"
        exclude = []  # Inclure tous les champs y compris also_sent_to

    def clean(self):
        cleaned_data = super().clean()
        
        if isinstance(self.fields["also_sent_to"], HorillaMultiSelectField):
            self.errors.pop("also_sent_to", None)
            employee_data = self.fields["also_sent_to"].queryset.filter(
                id__in=self.data.getlist("also_sent_to")
            )
            cleaned_data["also_sent_to"] = employee_data

        return cleaned_data

    def save(self, commit: bool = True) -> Any:
        self.instance: MailAutomation = self.instance
        condition_querystring = self.cleaned_data.get("condition_querystring", "")
        condition_html = self.cleaned_data.get("condition_html", "")
        mail_to = self.data.getlist("mail_to")
        self.instance.mail_to = str(mail_to)
        self.instance.mail_details = self.data.get("mail_details", "")
        self.instance.condition_querystring = condition_querystring
        self.instance.condition_html = condition_html
        return super().save(commit)