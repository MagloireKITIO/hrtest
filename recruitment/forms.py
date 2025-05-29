"""
forms.py

This module contains the form classes used in the application.

Each form represents a specific functionality or data input in the
application. They are responsible for validating
and processing user input data.

Classes:
- YourForm: Represents a form for handling specific data input.

Usage:
from django import forms

class YourForm(forms.Form):
    field_name = forms.CharField()

    def clean_field_name(self):
        # Custom validation logic goes here
        pass
"""

import logging
import uuid
from ast import Dict
from datetime import date, datetime, timedelta
from typing import Any

from django import forms
from django.apps import apps
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.utils.translation import gettext_lazy as _

from base.forms import Form
from base.methods import reload_queryset
from base.models import Company, Department
from employee.filters import EmployeeFilter
from employee.models import Employee
from horilla import horilla_middlewares
from horilla.horilla_middlewares import _thread_locals
from horilla_widgets.widgets.horilla_multi_select_field import HorillaMultiSelectField
from horilla_widgets.widgets.select_widgets import HorillaMultiSelectWidget
from recruitment import widgets
from recruitment.models import (
    AIConfiguration,
    Candidate,
    CandidatePrivacyConsent,
    InterviewSchedule,
    JobPosition,
    PrivacyPolicy,
    Recruitment,
    RecruitmentSurvey,
    RejectedCandidate,
    RejectReason,
    Resume,
    Motivation,
    Skill,
    SkillZone,
    SkillZoneCandidate,
    Stage,
    StageFiles,
    StageNote,
    SurveyTemplate,
)

logger = logging.getLogger(__name__)


class ModelForm(forms.ModelForm):
    """
    Overriding django default model form to apply some styles
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = getattr(horilla_middlewares._thread_locals, "request", None)
        reload_queryset(self.fields)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.DateInput)):
                field.initial = date.today()

            if isinstance(
                widget,
                (forms.NumberInput, forms.EmailInput, forms.TextInput, forms.FileInput),
            ):
                label = _(field.label)
                field.widget.attrs.update(
                    {"class": "oh-input w-100", "placeholder": label}
                )
            elif isinstance(widget, forms.URLInput):
                field.widget.attrs.update(
                    {"class": "oh-input w-100", "placeholder": field.label}
                )
            elif isinstance(widget, (forms.Select,)):
                field.empty_label = _("---Choose {label}---").format(
                    label=_(field.label)
                )
                self.fields[field_name].widget.attrs.update(
                    {
                        "id": uuid.uuid4,
                        "class": "oh-select oh-select-2 w-100",
                        "style": "height:50px;",
                    }
                )
            elif isinstance(widget, (forms.Textarea)):
                label = _(field.label)
                field.widget.attrs.update(
                    {
                        "class": "oh-input w-100",
                        "placeholder": label,
                        "rows": 2,
                        "cols": 40,
                    }
                )
            elif isinstance(
                widget,
                (
                    forms.CheckboxInput,
                    forms.CheckboxSelectMultiple,
                ),
            ):
                field.widget.attrs.update({"class": "oh-switch__checkbox "})

            try:
                self.fields["employee_id"].initial = request.user.employee_get
            except:
                pass

            try:
                self.fields["company_id"].initial = (
                    request.user.employee_get.get_company
                )
            except:
                pass


class RegistrationForm(forms.ModelForm):
    """
    Overriding django default model form to apply some styles
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reload_queryset(self.fields)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.Select,)):
                label = ""
                if field.label is not None:
                    label = _(field.label)
                field.empty_label = _("---Choose {label}---").format(label=label)
                self.fields[field_name].widget.attrs.update(
                    {"id": uuid.uuid4, "class": "oh-select-2 oh-select--sm w-100"}
                )
            elif isinstance(widget, (forms.TextInput)):
                field.widget.attrs.update(
                    {
                        "class": "oh-input w-100",
                    }
                )
            elif isinstance(
                widget,
                (
                    forms.CheckboxInput,
                    forms.CheckboxSelectMultiple,
                ),
            ):
                field.widget.attrs.update({"class": "oh-switch__checkbox "})


class DropDownForm(forms.ModelForm):
    """
    Overriding django default model form to apply some styles
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        reload_queryset(self.fields)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(
                widget,
                (
                    forms.NumberInput,
                    forms.EmailInput,
                    forms.TextInput,
                    forms.FileInput,
                    forms.URLInput,
                ),
            ):
                if field.label is not None:
                    label = _(field.label)
                    field.widget.attrs.update(
                        {
                            "class": "oh-input oh-input--small oh-table__add-new-row d-block w-100",
                            "placeholder": label,
                        }
                    )
            elif isinstance(widget, (forms.Select,)):
                self.fields[field_name].widget.attrs.update(
                    {
                        "class": "oh-select-2 oh-select--xs-forced ",
                        "id": uuid.uuid4(),
                    }
                )
            elif isinstance(widget, (forms.Textarea)):
                if field.label is not None:
                    label = _(field.label)
                    field.widget.attrs.update(
                        {
                            "class": "oh-input oh-input--small oh-input--textarea",
                            "placeholder": label,
                            "rows": 1,
                            "cols": 40,
                        }
                    )
            elif isinstance(
                widget,
                (
                    forms.CheckboxInput,
                    forms.CheckboxSelectMultiple,
                ),
            ):
                field.widget.attrs.update({"class": "oh-switch__checkbox "})


class RecruitmentCreationForm(ModelForm):
    """
    Form for Recruitment model
    """
    google_form_url = forms.URLField(
        required=False,
        widget=forms.URLInput(
            attrs={
                'class': 'oh-input w-100',
                'placeholder': _('Google Form URL'),
            }
        )
    )

    generate_form = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(
            attrs={
                'class': 'oh-switch__checkbox',
                'data-toggle': 'generateForm',
            }
        ),
        help_text=_("Generate a new Google Form automatically")
    )
    
    start_date = forms.DateField(
        label=_("Start Date"),
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'oh-input w-100'},
            format='%Y-%m-%d',
        ),
        localize=True,
        initial=date.today  # Valeur par défaut côté serveur
    )
    
    end_date = forms.DateField(
        label=_("End Date"),
        required=False,
        widget=forms.DateInput(
            attrs={'type': 'date', 'class': 'oh-input w-100'},
            format='%Y-%m-%d',
        ),
        localize=True
    )

    optional_motivation = forms.BooleanField(
        required=False,
        initial=False,
        help_text=_("Motivation letter not mandatory for candidate creation")
    )

    is_superuser = forms.BooleanField(
        required=False, 
        label=_("Is Superuser"),
        help_text=_("Give full administrator access to this employee")
    )

    selectors = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.filter(is_selector=True),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'oh-select oh-select-2 select2-hidden-accessible',
            'data-placeholder': _('Selection du demandeur')
        }),
        label=_("Demandeur")
    )

    recruitment_type = forms.ChoiceField(
        choices=Recruitment.RECRUITMENT_TYPES,
        widget=forms.Select(attrs={
            'class': 'oh-select oh-select-2 select2-hidden-accessible',
            'data-placeholder': _('Select Recruitment Type')
        }),
        label=_("Recruitment Type"),
        initial='BOTH'
    )

    validity_duration = forms.ChoiceField(
        choices=Recruitment.VALIDITY_DURATION_CHOICES,
        required=False,
        initial=60,  # 60 jours par défaut
        widget=forms.Select(attrs={
            'class': 'oh-select oh-select-2 select2-hidden-accessible',
            'data-placeholder': _('Select Duration'),
            'id': 'id_validity_duration'
        }),
        label=_("Durée de validité"),
        help_text=_("Sélectionnez une durée prédéfinie ou choisissez 'Personnalisé' pour saisir manuellement les dates")
    )

    class Meta:
        """
        Meta class to add the additional info
        """
        model = Recruitment
        fields = "__all__"
        exclude = ["is_active"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"data-summernote": ""}),
            "is_published": forms.CheckboxInput(attrs={
                'class': 'oh-switch__checkbox',
            }),
            "optional_motivation": forms.CheckboxInput(attrs={
                'class': 'oh-switch__checkbox',
            }),
        }
        labels = {
            "description": _("Description"), 
            "vacancy": _("Vacancy"),
            "validity_duration": _("Durée de validité")
        }

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("attendance_form.html", context)
        return table_html

    def __init__(self, *args, **kwargs):
        # Récupérer l'utilisateur depuis le contexte
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        reload_queryset(self.fields)
        
        # Filtrage basé sur la compagnie de l'utilisateur
        if self.user and hasattr(self.user, 'employee_get'):
            employee = self.user.employee_get
            user_company = employee.company_id if employee else None
            
            # Si l'utilisateur n'est pas superuser, filtrer par sa compagnie
            if not self.user.is_superuser and user_company:
                # Filtrer les compagnies disponibles
                self.fields['company_id'].queryset = Company.objects.filter(id=user_company.id)
                self.fields['company_id'].initial = user_company
                
                # Filtrer les managers par compagnie
                self.fields['recruitment_managers'].queryset = Employee.objects.filter(
                    is_active=True,
                    company_id=user_company
                )
                
                # Filtrer les sélecteurs par compagnie
                self.fields['selectors'].queryset = Employee.objects.filter(
                    is_active=True,
                    is_selector=True,
                    company_id=user_company
                )
                
                # SOLUTION: Filtrer les positions via les départements de la compagnie
                departments_in_company = Department.objects.filter(company_id=user_company)
                positions_in_company = JobPosition.objects.filter(
                    department_id__in=departments_in_company,
                    is_active=True
                )
                
                self.fields['open_positions'].queryset = positions_in_company
        
        # Gestion différente selon création ou modification
        if self.instance and self.instance.pk:
            # MODIFICATION: Forcer le chargement des sélecteurs existants
            self.fields['selectors'].initial = self.instance.selectors.all()
            
            # Pour les instances existantes, calculer la durée si possible
            if self.instance.start_date and self.instance.end_date:
                delta = self.instance.end_date - self.instance.start_date
                duration_days = delta.days
                
                # Vérifier si la durée correspond à un choix prédéfini
                duration_choices = dict(Recruitment.VALIDITY_DURATION_CHOICES)
                if duration_days in [choice[0] for choice in Recruitment.VALIDITY_DURATION_CHOICES if choice[0] > 0]:
                    self.fields['validity_duration'].initial = duration_days
                else:
                    self.fields['validity_duration'].initial = 0  # Personnalisé
        else:
            # CRÉATION: Initialiser avec les valeurs par défaut
            self.fields['start_date'].initial = date.today()
            # La date de fin sera calculée côté client par JavaScript
        
        # Configuration du champ recruitment_managers pour la création
        if not self.instance.pk:
            manager_queryset = self.fields['recruitment_managers'].queryset
            self.fields["recruitment_managers"] = HorillaMultiSelectField(
                queryset=manager_queryset,
                widget=HorillaMultiSelectWidget(
                    filter_route_name="employee-widget-filter",
                    filter_class=EmployeeFilter,
                    filter_instance_contex_name="f",
                    filter_template_path="employee_filters.html",
                    required=True,
                ),
                label="Employee",
            )
        
        # Configuration des skills
        skill_choices = [("", _("---Choose Skills---"))] + list(
            self.fields["skills"].queryset.values_list("id", "title")
        )
        self.fields["skills"].choices = skill_choices
        self.fields["skills"].choices += [("create", _("Create new skill "))]
        
        # Ajouter des attributs pour JavaScript
        self.fields['start_date'].widget.attrs.update({
            'id': 'id_start_date',
            'class': 'oh-input w-100'
        })
        self.fields['end_date'].widget.attrs.update({
            'id': 'id_end_date',
            'class': 'oh-input w-100'
        })


    def clean_selectors(self):
        """
        Validation des sélecteurs assignés avec vérification de compagnie
        """
        selectors = self.cleaned_data.get('selectors')
        company_id = self.cleaned_data.get('company_id')
        
        if selectors and company_id:
            invalid_selectors = []
            
            for selector in selectors:
                # Vérifier que le sélecteur appartient à la même compagnie
                if (selector.company_id and 
                    selector.company_id != company_id and 
                    not self.user.is_superuser):
                    
                    invalid_selectors.append(
                        f"{selector.get_full_name()} (compagnie: {selector.company_id})"
                    )
            
            if invalid_selectors:
                raise forms.ValidationError(
                    _(f"Les sélecteurs suivants ne peuvent pas être assignés à un recrutement "
                      f"de la compagnie {company_id}: {', '.join(invalid_selectors)}")
                )
        
        return selectors

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate recruitment managers
        if isinstance(self.fields["recruitment_managers"], HorillaMultiSelectField):
            ids = self.data.getlist("recruitment_managers")
            if ids:
                self.errors.pop("recruitment_managers", None)

        # Validation supplémentaire pour la compagnie
        if self.user and not self.user.is_superuser:
            company_id = cleaned_data.get('company_id')
            if company_id and hasattr(self.user, 'employee_get'):
                user_company = self.user.employee_get.company_id
                if user_company and company_id != user_company:
                    raise forms.ValidationError(
                        _("Vous ne pouvez créer des recrutements que pour votre compagnie.")
                    )
        
        # Validate open positions
        open_positions = cleaned_data.get("open_positions")
        is_published = cleaned_data.get("is_published")
        if is_published and not open_positions:
            raise forms.ValidationError(
                _("Job position is required if the recruitment is publishing.")
            )
            
        # Validate Google Form fields
        generate_form = cleaned_data.get('generate_form')
        google_form_url = cleaned_data.get('google_form_url')

        # validation pour les sélecteurs
        selectors = cleaned_data.get('selectors')
        company_id = cleaned_data.get('company_id')

        if selectors and company_id:
            # Re-validation au niveau du formulaire complet
            self.clean_selectors()

        if generate_form and google_form_url:
            raise forms.ValidationError(
                _("Please either provide a Google Form URL or choose to generate one, not both.")
            )
        
        # Gestion de la durée de validité
        validity_duration = cleaned_data.get('validity_duration')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if validity_duration and int(validity_duration) > 0 and start_date:
            # Calculer automatiquement la date de fin
            calculated_end_date = start_date + timedelta(days=int(validity_duration))
            cleaned_data['end_date'] = calculated_end_date
        elif validity_duration == '0':  # Personnalisé
            if not end_date:
                self.add_error('end_date', _('La date de fin est requise quand "Personnalisé" est sélectionné'))
            
        return cleaned_data

    
class StageCreationForm(ModelForm):
    """
    Form for Stage model
    """
    class Meta:
        model = Stage
        fields = "__all__"
        exclude = ["sequence", "is_active"]
        labels = {
            "stage": _("Stage"),
        }

    def __init__(self, *args, **kwargs):
        # Récupérer l'utilisateur depuis le contexte
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        reload_queryset(self.fields)
        data = kwargs.get('data', {})
        initial = kwargs.get('initial', {})
        
        # Obtenir le type d'étape actuel
        stage_type = data.get('stage_type') or initial.get('stage_type') or self.instance.stage_type if self.instance.pk else None
        
        # Définir le queryset en fonction du type et de la compagnie
        manager_queryset = Employee.objects.filter(is_active=True)
        
        # Filtrer par compagnie si l'utilisateur n'est pas superuser
        if self.user and hasattr(self.user, 'employee_get') and not self.user.is_superuser:
            user_company = self.user.employee_get.company_id
            if user_company:
                manager_queryset = manager_queryset.filter(company_id=user_company)
        
        # Filtrer par type de stage
        if stage_type == 'selector':
            manager_queryset = manager_queryset.filter(is_selector=True)
            
        if not self.instance.pk:
            self.fields["stage_managers"] = HorillaMultiSelectField(
                queryset=manager_queryset,
                widget=HorillaMultiSelectWidget(
                    filter_route_name="employee-widget-filter",
                    filter_class=EmployeeFilter,
                    filter_instance_contex_name="f",
                    filter_template_path="employee_filters.html",
                    required=True,
                ),
                label=_("Stage Managers"),
            )
        else:
            self.fields["stage_managers"].queryset = manager_queryset
        
        # Ajout d'un champ caché pour suivre le type d'étape
        self.fields['current_type'] = forms.CharField(
            widget=forms.HiddenInput(),
            required=False,
            initial=stage_type
        )

    def clean(self):
        cleaned_data = super().clean()
        if isinstance(self.fields["stage_managers"], HorillaMultiSelectField):
            ids = self.data.getlist("stage_managers")
            if ids:
                self.errors.pop("stage_managers", None)
                
                # Vérifier que tous les managers sélectionnés sont des sélecteurs si le type est selector
                if cleaned_data.get('stage_type') == 'selector':
                    selected_managers = Employee.objects.filter(id__in=ids)
                    non_selectors = selected_managers.filter(is_selector=False)
                    if non_selectors.exists():
                        self.add_error(
                            'stage_managers',
                            _("Seuls les demandeurs peuvent être assignés à cette étape.")
                        )
        return cleaned_data


class CandidateCreationForm(ModelForm):
    """
    Form for Candidate model
    """

    load = forms.CharField(widget=widgets.RecruitmentAjaxWidget, required=False)
    mobile = forms.CharField(
        max_length=15,
        label=_("Mobile"), # Ajout du label explicite
        widget=forms.TextInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _('Mobile'),
            'id': 'mobile',
            'type': 'tel'
        })
    )
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["source"].initial = "software"
        self.fields["profile"].widget.attrs["accept"] = ".jpg, .jpeg, .png"
        self.fields["profile"].required = False
        self.fields["resume"].widget.attrs["accept"] = ".pdf"
        self.fields["resume"].required = False
        self.fields["motivation"].widget.attrs["accept"] = ".pdf"
        self.fields["motivation"].required = False
        if self.instance.recruitment_id is not None:
            if self.instance is not None:
                self.fields["job_position_id"] = forms.ModelChoiceField(
                    queryset=self.instance.recruitment_id.open_positions.all(),
                    label="Job Position",
                )
        self.fields["recruitment_id"].widget.attrs = {"data-widget": "ajax-widget"}
        self.fields["job_position_id"].widget.attrs = {"data-widget": "ajax-widget"}
        self.fields['mobile'].label = _("Mobile")

    class Meta:
        """
        Meta class to add the additional info
        """

        model = Candidate
        fields = [
            "profile",
            "name",
            "portfolio",
            "email",
            "mobile",
            "recruitment_id",
            "job_position_id",
            "dob",
            "gender",
            "address",
            "source",
            "country",
            "state",
            "zip",
            "resume",
            "motivation",
            "referral",
            "canceled",
            "is_active",
        ]
        exclude = (
            "dob",
            "referral",
        )
        

        widgets = {
            "scheduled_date": forms.DateInput(attrs={"type": "date"}),
            "dob": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "name": _("Name"),
            "email": _("Email"),
            "mobile": _("Mobile"),
            "address": _("Address"),
            "zip": _("Zip"),
        }
        
    def save(self, commit: bool = ...):
        candidate = self.instance
        recruitment = candidate.recruitment_id
        stage = candidate.stage_id
        candidate.hired = False
        candidate.start_onboard = False
        if stage is not None:
            if stage.stage_type == "hired" and candidate.canceled is False:
                candidate.hired = True
                candidate.start_onboard = True
        candidate.recruitment_id = recruitment
        candidate.stage_id = stage
        job_id = self.data.get("job_position_id")
        if job_id:
            job_position = JobPosition.objects.get(id=job_id)
            self.instance.job_position_id = job_position
        
        if commit:
            try:
                # Tentative de sauvegarde du candidat
                super().save(commit=True)
            except IntegrityError:
                # Si une IntegrityError est levée, cela signifie probablement que
                # le candidat a déjà postulé pour cette offre
                raise ValidationError(_("Vous avez déjà postulé pour cette offre d'emploi."))
        else:
            # Si commit est False, on ne fait pas la sauvegarde tout de suite
            return super().save(commit=False)
        
        return candidate

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string(
            "candidate/candidate_create_form_as_p.html", context
        )
        return table_html

         

    def clean(self):
        cleaned_data = super().clean()
        errors = {}
        
        profile = cleaned_data.get("profile")
        resume = cleaned_data.get("resume")
        recruitment = cleaned_data.get("recruitment_id")
        email = cleaned_data.get("email")
        
        # Vérification du CV et de la photo de profil
        if not resume and not recruitment.optional_resume:
            errors["resume"] = _("Ce champ est obligatoire")
        if not profile and not recruitment.optional_profile_image:
            errors["profile"] = _("Ce champ est obligatoire")
        
        # Vérification du poste
        if self.instance.name is not None:
            self.errors.pop("job_position_id", None)
            if (
                self.instance.job_position_id is None
                or self.data.get("job_position_id") == ""
            ):
                errors["job_position_id"] = _("Ce champ est obligatoire")
            if (
                self.instance.job_position_id
                not in self.instance.recruitment_id.open_positions.all()
            ):
                errors["job_position_id"] = _("Choisissez une option valide")
        
        # Nouvelle vérification pour les candidatures multiples
        if email and recruitment:
            existing_candidate = Candidate.objects.filter(
                email=email, 
                recruitment_id=recruitment
            ).exclude(pk=self.instance.pk).exists()
            
            if existing_candidate:
                errors["email"] = _("Vous avez déjà postulé pour cette offre d'emploi.")
        
        if errors:
            raise ValidationError(errors)
        
        return cleaned_data


class ApplicationForm(RegistrationForm):
   """
   Form for create Candidate
   """
   mobile = forms.CharField(
       max_length=15,
       label=_("Mobile"),
       widget=forms.TextInput(attrs={
           'class': 'oh-input w-100',
           'placeholder': _('Mobile'),
           'name': 'mobile',
           'type': 'tel'
       })
   )
   load = forms.CharField(widget=widgets.RecruitmentAjaxWidget, required=False)
   active_recruitment = Recruitment.objects.filter(
       is_active=True, closed=False, is_published=True
   )
   recruitment_id = forms.ModelChoiceField(queryset=active_recruitment)
   privacy_consent = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'id': 'privacy_consent',
            'class': 'oh-switch__checkbox',
            'onchange': 'toggleSubmitButton(this)'
        }),
        label=_("J'accepte la politique de confidentialité")
    )
   
   class Meta:
       """
       Meta class to add the additional info
       """
       model = Candidate
       exclude = (
           "stage_id",
           "schedule_date", 
           "referral",
           "start_onboard",
           "hired",
           "is_active",
           "canceled",
           "joining_date",
           "sequence",
           "offerletter_status",
           "source",
           "ai_analysis_status",
           "ai_score",
           "ai_analysis_details",
           "ai_analysis_timestamp",
           "privacy_policy_accepted",
       )
       widgets = {
           "recruitment_id": forms.TextInput(
               attrs={
                   "required": "required",
               }
           ),
           "dob": forms.DateInput(
               attrs={
                   "type": "date",
               }
           ),
       }

   def __init__(self, *args, **kwargs):
       super().__init__(*args, **kwargs)
       request = getattr(_thread_locals, "request", None)
       self.fields["profile"].widget.attrs["accept"] = ".jpg, .jpeg, .png"
       self.fields["profile"].required = False
       self.fields["resume"].widget.attrs["accept"] = ".pdf"
       self.fields["resume"].required = False
       
       self.fields["motivation"].widget.attrs["accept"] = ".pdf"
       self.fields["motivation"].required = False

       self.fields["recruitment_id"].widget.attrs = {"data-widget": "ajax-widget"}
       self.fields["job_position_id"].widget.attrs = {"data-widget": "ajax-widget"}
       if request and request.user.has_perm("recruitment.add_candidate"):
           self.fields["profile"].required = False
       self.fields['mobile'].label = _("Mobile")

   def clean(self, *args, **kwargs):
       cleaned_data = super().clean(*args, **kwargs)
       name = cleaned_data.get("name")
       request = getattr(_thread_locals, "request", None)

       errors = {}
       profile = cleaned_data.get("profile")
       resume = cleaned_data.get("resume")
       recruitment: Recruitment = cleaned_data.get("recruitment_id")
       email = cleaned_data.get("email")

       # Vérification du type de recrutement
       if recruitment and email:
           if recruitment.recruitment_type == 'INTERNAL' and not email.endswith('@group-activa.com'):
               errors["email"] = _("Ce recrutement est réservé aux employés internes")
           elif recruitment.recruitment_type == 'EXTERNAL' and email.endswith('@group-activa.com'):
               errors["email"] = _("Les candidatures externes ne peuvent pas utiliser ce type d'adresse Email")

       # Vérification du CV et de la photo de profil
       if not resume and not recruitment.optional_resume:
           errors["resume"] = _("Ce champ est obligatoire")
       if not profile and not recruitment.optional_profile_image:
           errors["profile"] = _("Ce champ est obligatoire")

       # Vérification pour les candidatures multiples
       if email and recruitment:
           existing_candidate = Candidate.objects.filter(
               email=email, 
               recruitment_id=recruitment
           ).exists()
           
           if existing_candidate:
               errors["email"] = _("Vous avez déjà postulé pour cette offre d'emploi.")

       if errors:
           raise ValidationError(errors)

       # Gestion de la photo de profil par défaut
       if (
           not profile
           and request
           and request.user.has_perm("recruitment.add_candidate")
       ):
           profile_pic_url = f"https://ui-avatars.com/api/?name={name}"
           cleaned_data["profile"] = profile_pic_url

       return cleaned_data

   def save(self, commit=True):
        """
        Override save to set privacy policy acceptance
        """
        instance = super().save(commit=False)
        
        # Set privacy policy acceptance
        instance.privacy_policy_accepted = self.cleaned_data.get('privacy_consent', False)
        
        # Set default values for AI fields
        instance.ai_analysis_status = 'pending'
        instance.ai_score = None 
        instance.ai_analysis_details = None
        instance.ai_analysis_timestamp = None

        if commit:
            try:
                instance.save()
                
                # Enregistrer le consentement si la politique existe
                if instance.privacy_policy_accepted and instance.recruitment_id:
                    policy = PrivacyPolicy.get_policy_for_company(instance.recruitment_id.company_id)
                    if policy:
                        CandidatePrivacyConsent.objects.create(
                            candidate=instance,
                            policy=policy,
                            ip_address=self.request.META.get('REMOTE_ADDR') if hasattr(self, 'request') else None
                        )
                        
            except IntegrityError as e:
                logger.error(f"Error saving candidate: {str(e)}")
                raise ValidationError(_("Vous avez déjà postulé pour cette offre d'emploi."))

        return instance


class RecruitmentDropDownForm(DropDownForm):
    """
    Form for Recruitment model
    """

    class Meta:
        """
        Meta class to add the additional info
        """

        fields = "__all__"
        model = Recruitment
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"data-summernote": ""}),
        }
        labels = {"description": _("Description"), "vacancy": _("Vacancy")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["job_position_id"].widget.attrs.update({"id": uuid.uuid4})
        self.fields["recruitment_managers"].widget.attrs.update({"id": uuid.uuid4})
        field = self.fields["is_active"]
        field.widget = field.hidden_widget()


class AddCandidateForm(ModelForm):
    """
    Form for Candidate model
    """

    verbose_name = "Add Candidate"

    class Meta:
        """
        Meta class to add the additional info
        """

        model = Candidate
        fields = [
            "profile",
            "resume",
            "motivation",
            "name",
            "email",
            "mobile",
            "gender",
            "stage_id",
            "job_position_id",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial = kwargs["initial"].get("stage_id")
        if initial:
            recruitment = Stage.objects.get(id=initial).recruitment_id
            self.instance.recruitment_id = recruitment
            self.fields["stage_id"].queryset = self.fields["stage_id"].queryset.filter(
                recruitment_id=recruitment
            )
            self.fields["job_position_id"].queryset = recruitment.open_positions
        self.fields["profile"].widget.attrs["accept"] = ".jpg, .jpeg, .png"
        self.fields["resume"].widget.attrs["accept"] = ".pdf"
        if recruitment.optional_profile_image:
            self.fields["profile"].required = False
        if recruitment.optional_resume:
            self.fields["resume"].required = False
        self.fields["gender"].empty_label = None
        self.fields["job_position_id"].empty_label = None
        self.fields["stage_id"].empty_label = None

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


class StageDropDownForm(DropDownForm):
    """
    Form for Stage model
    """

    class Meta:
        """
        Meta class to add the additional info
        """

        model = Stage
        fields = "__all__"
        exclude = ["sequence", "is_active"]
        labels = {
            "stage": _("Stage"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        stage = Stage.objects.last()
        if stage is not None and stage.sequence is not None:
            self.instance.sequence = stage.sequence + 1
        else:
            self.instance.sequence = 1


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [
                single_file_clean(data, initial),
            ]
        return result[0] if result else []


class StageNoteForm(ModelForm):
    """
    Form for StageNote model
    """

    class Meta:
        """
        Meta class to add the additional info
        """

        model = StageNote
        # exclude = (
        #     "updated_by",
        #     "stage_id",
        # )
        fields = ["description"]
        exclude = ["is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # field = self.fields["candidate_id"]
        # field.widget = field.hidden_widget()
        self.fields["stage_files"] = MultipleFileField(label="files")
        self.fields["stage_files"].required = False

    def save(self, commit: bool = ...) -> Any:
        attachment = []
        multiple_attachment_ids = []
        attachments = None
        if self.files.getlist("stage_files"):
            attachments = self.files.getlist("stage_files")
            self.instance.attachement = attachments[0]
            multiple_attachment_ids = []

            for attachment in attachments:
                file_instance = StageFiles()
                file_instance.files = attachment
                file_instance.save()
                multiple_attachment_ids.append(file_instance.pk)
        instance = super().save(commit)
        if commit:
            instance.stage_files.add(*multiple_attachment_ids)
        return instance, multiple_attachment_ids


class StageNoteUpdateForm(ModelForm):
    class Meta:
        """
        Meta class to add the additional info
        """

        model = StageNote
        exclude = ["updated_by", "stage_id", "stage_files", "is_active"]
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["candidate_id"]
        field.widget = field.hidden_widget()


class QuestionForm(ModelForm):
    """
    QuestionForm
    """

    verbose_name = "Survey Questions"

    recruitment = forms.ModelMultipleChoiceField(
        queryset=Recruitment.objects.filter(is_active=True),
        required=False,
        label=_("Recruitment"),
    )
    options = forms.CharField(
        widget=forms.TextInput, label=_("Options"), required=False
    )

    class Meta:
        """
        Class Meta for additional options
        """

        model = RecruitmentSurvey
        fields = "__all__"
        exclude = ["recruitment_ids", "job_position_ids", "is_active", "options"]
        labels = {
            "question": _("Question"),
            "sequence": _("Sequence"),
            "type": _("Type"),
            "options": _("Options"),
            "is_mandatory": _("Is Mandatory"),
        }

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string(
            "survey/question_template_organized_form.html", context
        )
        return table_html

    def clean(self):
        cleaned_data = super().clean()
        recruitment = self.cleaned_data["recruitment"]
        question_type = self.cleaned_data["type"]
        options = self.cleaned_data.get("options")
        if not recruitment.exists():  # or jobs.exists()):
            raise ValidationError(
                {"recruitment": _("Choose any recruitment to apply this question")}
            )
        self.recruitment = recruitment
        if question_type in ["options", "multiple"] and (
            options is None or options == ""
        ):
            raise ValidationError({"options": "Options field is required"})
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if instance.type in ["options", "multiple"]:
            additional_options = []
            for key, value in self.cleaned_data.items():
                if key.startswith("options") and value:
                    additional_options.append(value)

            instance.options = ", ".join(additional_options)
            if commit:
                instance.save()
                self.save_m2m()
        else:
            instance.options = ""
        return instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = kwargs.get("instance", None)
        self.option_count = 1

        def create_options_field(option_key, initial=None):
            self.fields[option_key] = forms.CharField(
                widget=forms.TextInput(
                    attrs={
                        "name": option_key,
                        "id": f"id_{option_key}",
                        "class": "oh-input w-100",
                    }
                ),
                label=_("Options"),
                required=False,
                initial=initial,
            )

        if instance:
            split_options = instance.options.split(",")
            for i, option in enumerate(split_options):
                if i == 0:
                    create_options_field("options", option)
                else:
                    self.option_count += 1
                    create_options_field(f"options{i}", option)

        if instance:
            self.fields["recruitment"].initial = instance.recruitment_ids.all()
        self.fields["type"].widget.attrs.update(
            {"class": " w-100", "style": "border:solid 1px #6c757d52;height:50px;"}
        )
        for key, value in self.data.items():
            if key.startswith("options"):
                self.option_count += 1
                create_options_field(key, initial=value)
        fields_order = list(self.fields.keys())
        fields_order.remove("recruitment")
        fields_order.insert(2, "recruitment")
        self.fields = {field: self.fields[field] for field in fields_order}


class SurveyForm(forms.Form):
    """
    SurveyTemplateForm
    """

    def __init__(self, recruitment, *args, **kwargs) -> None:
        super().__init__(recruitment, *args, **kwargs)
        questions = recruitment.recruitmentsurvey_set.all()
        all_questions = RecruitmentSurvey.objects.none() | questions
        for template in recruitment.survey_templates.all():
            questions = template.recruitmentsurvey_set.all()
            all_questions = all_questions | questions
        context = {"form": self, "questions": all_questions.distinct()}
        form = render_to_string("survey_form.html", context)
        self.form = form
        return
        # for question in questions:
        # self


class SurveyPreviewForm(forms.Form):
    """
    SurveyTemplateForm
    """

    def __init__(self, template, *args, **kwargs) -> None:
        super().__init__(template, *args, **kwargs)
        all_questions = RecruitmentSurvey.objects.filter(template_id__in=[template])
        context = {"form": self, "questions": all_questions.distinct()}
        form = render_to_string("survey_preview_form.html", context)
        self.form = form
        return
        # for question in questions:
        # self


class TemplateForm(ModelForm):
    """
    TemplateForm
    """

    verbose_name = "Template"

    class Meta:
        model = SurveyTemplate
        fields = "__all__"
        exclude = ["is_active"]

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


class AddQuestionForm(Form):
    """
    AddQuestionForm
    """

    verbose_name = "Add Question"
    question_ids = forms.ModelMultipleChoiceField(
        queryset=RecruitmentSurvey.objects.all(), label="Questions"
    )
    template_ids = forms.ModelMultipleChoiceField(
        queryset=SurveyTemplate.objects.all(), label="Templates"
    )

    def save(self):
        """
        Manual save/adding of questions to the templates
        """
        for question in self.cleaned_data["question_ids"]:
            question.template_id.add(*self.data["template_ids"])

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


exclude_fields = [
    "id",
    "profile",
    "portfolio",
    "resume",
    "motivation",
    "sequence",
    "schedule_date",
    "created_at",
    "created_by",
    "modified_by",
    "is_active",
    "last_updated",
    "horilla_history",
]


class CandidateExportForm(forms.Form):
    model_fields = Candidate._meta.get_fields()
    field_choices = [
        (field.name, field.verbose_name.capitalize())
        for field in model_fields
        if hasattr(field, "verbose_name") and field.name not in exclude_fields
    ]
    field_choices = field_choices + [
        ("rejected_candidate__description", "Rejected Description"),
    ]
    selected_fields = forms.MultipleChoiceField(
        choices=field_choices,
        widget=forms.CheckboxSelectMultiple,
        initial=[
            "name",
            "recruitment_id",
            "job_position_id",
            "stage_id",
            "email",
            "mobile",
            "hired",
            "joining_date",
        ],
    )


class SkillZoneCreateForm(ModelForm):
    verbose_name = "Skill Zone"

    class Meta:
        """
        Class Meta for additional options
        """

        model = SkillZone
        fields = "__all__"
        exclude = ["is_active"]

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


class SkillZoneCandidateForm(ModelForm):
    verbose_name = "Skill Zone Candidate"
    candidate_id = forms.ModelMultipleChoiceField(
        queryset=Candidate.objects.all(),
        widget=forms.SelectMultiple,
        label=_("Candidate"),
    )

    class Meta:
        """
        Class Meta for additional options
        """

        model = SkillZoneCandidate
        fields = "__all__"
        exclude = [
            "added_on",
            "is_active",
        ]

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html

    def clean_candidate_id(self):
        selected_candidates = self.cleaned_data["candidate_id"]

        # Ensure all selected candidates are instances of the Candidate model
        for candidate in selected_candidates:
            if not isinstance(candidate, Candidate):
                raise forms.ValidationError("Invalid candidate selected.")

        return selected_candidates.first()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["candidate_id"].empty_label = None
        if self.instance.pk:
            self.verbose_name = (
                self.instance.candidate_id.name
                + " / "
                + self.instance.skill_zone_id.title
            )

    def save(self, commit: bool = ...) -> Any:
        super().save(commit)
        other_candidates = list(
            set(self.data.getlist("candidate_id"))
            - {
                str(self.instance.candidate_id.id),
            }
        )
        if commit:
            cand = self.instance
            for id in other_candidates:
                cand.pk = None
                cand.id = None
                cand.candidate_id = Candidate.objects.get(id=id)
                try:
                    super(SkillZoneCandidate, cand).save()
                except Exception as e:
                    logger.error(e)

        return other_candidates


class ToSkillZoneForm(ModelForm):
    verbose_name = "Add To Skill Zone"
    skill_zone_ids = forms.ModelMultipleChoiceField(
        queryset=SkillZone.objects.all(), label=_("Skill Zones")
    )

    class Meta:
        """
        Class Meta for additional options
        """

        model = SkillZoneCandidate
        fields = "__all__"
        exclude = [
            "skill_zone_id",
            "is_active",
            "candidate_id",
        ]
        error_messages = {
            NON_FIELD_ERRORS: {
                "unique_together": "This candidate alreay exist in this skill zone",
            }
        }

    def clean(self):
        cleaned_data = super().clean()
        candidate = cleaned_data.get("candidate_id")
        skill_zones = cleaned_data.get("skill_zone_ids")
        skill_zone_list = []
        for skill_zone in skill_zones:
            # Check for the unique together constraint manually
            if SkillZoneCandidate.objects.filter(
                candidate_id=candidate, skill_zone_id=skill_zone
            ).exists():
                # Raise a ValidationError with a custom error message
                skill_zone_list.append(skill_zone)
        if len(skill_zone_list) > 0:
            skill_zones_str = ", ".join(
                str(skill_zone) for skill_zone in skill_zone_list
            )
            raise ValidationError(f"{candidate} already exists in {skill_zones_str}.")

            # cleaned_data['skill_zone_id'] =skill_zone
        return cleaned_data

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


class RejectReasonForm(ModelForm):
    """
    RejectReasonForm
    """

    verbose_name = "Reject Reason"

    class Meta:
        model = RejectReason
        fields = "__all__"
        exclude = ["is_active"]

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


class RejectedCandidateForm(ModelForm):
    """
    RejectedCandidateForm
    """

    verbose_name = "Rejected Candidate"

    class Meta:
        model = RejectedCandidate
        fields = "__all__"
        exclude = ["is_active"]

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reject_reason_id"].empty_label = None
        self.fields["candidate_id"].widget = self.fields["candidate_id"].hidden_widget()


class ScheduleInterviewForm(ModelForm):
    """
    ScheduleInterviewForm
    """

    verbose_name = "Schedule Interview"

    class Meta:
        model = InterviewSchedule
        fields = "__all__"
        exclude = ["is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["interview_date"].widget = forms.DateInput(
            attrs={"type": "date", "class": "oh-input w-100"}
        )
        self.fields["interview_time"].widget = forms.TimeInput(
            attrs={"type": "time", "class": "oh-input w-100"}
        )

    def clean(self):

        instance = self.instance
        cleaned_data = super().clean()
        interview_date = cleaned_data.get("interview_date")
        interview_time = cleaned_data.get("interview_time")
        managers = cleaned_data["employee_id"]
        if not instance.pk and interview_date and interview_date < date.today():
            self.add_error("interview_date", _("Interview date cannot be in the past."))

        if not instance.pk and interview_time:
            now = datetime.now().time()
            if (
                not instance.pk
                and interview_date == date.today()
                and interview_time < now
            ):
                self.add_error(
                    "interview_time", _("Interview time cannot be in the past.")
                )

        if apps.is_installed("leave"):
            from leave.models import LeaveRequest

            leave_employees = LeaveRequest.objects.filter(
                employee_id__in=managers, status="approved"
            )
        else:
            leave_employees = []

        employees = [
            leave.employee_id.get_full_name()
            for leave in leave_employees
            if interview_date in leave.requested_dates()
        ]

        if employees:
            self.add_error(
                "employee_id", _(f"{employees} have approved leave on this date")
            )

        return cleaned_data

    def as_p(self, *args, **kwargs):
        """
        Render the form fields as HTML table rows with Bootstrap styling.
        """
        context = {"form": self}
        table_html = render_to_string("common_form.html", context)
        return table_html


class SkillsForm(ModelForm):
    class Meta:
        model = Skill
        fields = ["title"]

class SkillImportForm(forms.Form):
    file = forms.FileField(
        label='Fichier Excel',
        help_text='Fichier Excel avec une colonne "title"',
        widget=forms.FileInput(attrs={
            'class': 'oh-input w-100',
            'accept': '.xlsx'
        })
    )

class ResumeForm(ModelForm):
    class Meta:
        model = Resume
        fields = ["file", "recruitment_id"]
        widgets = {"recruitment_id": forms.HiddenInput()}

class MotivationForm(ModelForm):
    class Meta:
        model = Motivation
        fields = ["file", "recruitment_id"]
        widgets = {"recruitment_id": forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs.update(
            {
                "onchange": "submitForm($(this))",
            }
        )

class AIConfigurationForm(ModelForm):
    """
    Form for AI Configuration model avec Together AI
    """
    
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'oh-switch__checkbox'
        }),
        label=_("Filiales"),
        help_text=_("Sélectionnez les filiales qui utiliseront cette configuration")
    )

    class Meta:
        model = AIConfiguration
        fields = [
            'name', 'api_key', 'model_name', 'analysis_prompt', 
            'companies', 'is_default', 'max_tokens', 'temperature'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'oh-input w-100',
                'placeholder': _('Nom de la configuration')
            }),
            'api_key': forms.PasswordInput(attrs={
                'class': 'oh-input w-100',
                'placeholder': _('Clé API Together AI (format: a1c9fd0fa475a97cc...)')
            }),
            'model_name': forms.TextInput(attrs={
                'class': 'oh-input w-100',
                'placeholder': _('deepseek-ai/DeepSeek-V3')
            }),
            'analysis_prompt': forms.Textarea(attrs={
                'class': 'oh-input w-100',
                'rows': 15,
                'placeholder': _('Prompt d\'analyse des CV pour Together AI')
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'oh-switch__checkbox'
            }),
            'max_tokens': forms.NumberInput(attrs={
                'class': 'oh-input w-100',
                'min': '100',
                'max': '4000'
            }),
            'temperature': forms.NumberInput(attrs={
                'class': 'oh-input w-100',
                'min': '0.0',
                'max': '2.0',
                'step': '0.1'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Valeurs par défaut pour Together AI
        if not self.instance.pk:
            self.fields['model_name'].initial = 'deepseek-ai/DeepSeek-V3'
            self.fields['max_tokens'].initial = 2500
            self.fields['temperature'].initial = 0.1
        
        # Si on modifie une config existante, précharger les filiales
        if self.instance and self.instance.pk:
            self.fields['companies'].initial = self.instance.companies.all()

    def clean(self):
        cleaned_data = super().clean()
        
        # Validation de la clé API Together AI
        api_key = cleaned_data.get('api_key')
        if api_key and not api_key.startswith(('sk-', 'a1c9fd0f', 'sk_', 'together_')):
            self.add_error('api_key', _('Format de clé API Together AI non reconnu'))
        
        # Validation de la température
        temperature = cleaned_data.get('temperature')
        if temperature is not None and (temperature < 0.0 or temperature > 2.0):
            self.add_error('temperature', _('La température doit être entre 0.0 et 2.0'))

        # Validation des tokens
        max_tokens = cleaned_data.get('max_tokens')
        if max_tokens is not None and (max_tokens < 100 or max_tokens > 4000):
            self.add_error('max_tokens', _('Le nombre de tokens doit être entre 100 et 4000'))

        return cleaned_data

class AIConfigurationTestForm(forms.Form):
    """
    Formulaire pour tester une configuration IA
    """
    
    test_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'oh-input w-100',
            'rows': 5,
            'placeholder': _('Texte de test pour l\'analyse IA')
        }),
        label=_("Texte de test"),
        help_text=_("Entrez un texte pour tester la configuration IA")
    )
    
    job_description = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'oh-input w-100', 
            'rows': 3,
            'placeholder': _('Description du poste pour le test')
        }),
        label=_("Description du poste"),
        help_text=_("Description du poste pour le test d'analyse")
    )

class PrivacyPolicyForm(ModelForm):
    """
    Form for Privacy Policy model
    """
    
    companies = forms.ModelMultipleChoiceField(
        queryset=Company.objects.filter(is_active=True),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'oh-switch__checkbox'
        }),
        label=_("Filiales"),
        help_text=_("Sélectionnez les filiales qui utiliseront cette politique")
    )

    class Meta:
        model = PrivacyPolicy
        fields = [
            'name', 'content_type', 'text_content', 'pdf_file', 
            'companies', 'is_default'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'oh-input w-100',
                'placeholder': _('Nom de la politique')
            }),
            'content_type': forms.RadioSelect(),
            'text_content': forms.Textarea(attrs={
                'class': 'oh-input w-100',
                'rows': 15,
                'data-summernote': '',
                'placeholder': _('Contenu de la politique de confidentialité')
            }),
            'pdf_file': forms.FileInput(attrs={
                'class': 'oh-input oh-input--file w-100',
                'accept': '.pdf'
            }),
            'is_default': forms.CheckboxInput(attrs={
                'class': 'oh-switch__checkbox'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Si on modifie une politique existante, précharger les filiales
        if self.instance and self.instance.pk:
            self.fields['companies'].initial = self.instance.companies.all()

    def clean(self):
        cleaned_data = super().clean()
        content_type = cleaned_data.get('content_type')
        text_content = cleaned_data.get('text_content')
        pdf_file = cleaned_data.get('pdf_file')
        
        # Validation selon le type de contenu
        if content_type == 'text' and not text_content:
            self.add_error('text_content', _('Le contenu textuel est requis'))
        
        if content_type == 'pdf':
            if not pdf_file and not self.instance.pdf_file:
                self.add_error('pdf_file', _('Un fichier PDF est requis'))
        
        return cleaned_data


class MultipleFileInput(forms.ClearableFileInput):
    """Widget personnalisé pour l'upload de fichiers multiples"""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """Champ personnalisé pour l'upload de fichiers multiples"""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result


class SkillZoneBulkImportForm(forms.Form):
    """Formulaire pour l'import en masse de CV"""
    
    cv_files = MultipleFileField(
        label=_("CV Files (PDF)"),
        help_text=_("Sélectionnez plusieurs fichiers PDF à importer"),
        widget=MultipleFileInput(attrs={
            'accept': '.pdf',
            'class': 'oh-input'
        })
    )
    
    default_recruitment = forms.ModelChoiceField(
        queryset=Recruitment.objects.filter(closed=False, is_active=True),
        required=False,
        label=_("Recrutement par défaut"),
        help_text=_("Recrutement à utiliser pour les candidats importés"),
        widget=forms.Select(attrs={'class': 'oh-select'})
    )
    
    auto_create_zones = forms.BooleanField(
        required=False,
        initial=True,
        label=_("Créer automatiquement les zones manquantes"),
        help_text=_("Permet à l'IA de créer de nouvelles zones si nécessaire")
    )
    
    min_confidence = forms.FloatField(
        initial=0.7,
        min_value=0.0,
        max_value=1.0,
        label=_("Score de confiance minimum"),
        help_text=_("Score minimum pour la classification automatique (0-1)"),
        widget=forms.NumberInput(attrs={
            'class': 'oh-input',
            'step': '0.1'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtrer les recrutements par compagnie si possible
        if hasattr(self, 'user') and hasattr(self.user, 'employee_get'):
            company = self.user.employee_get.company_id
            if company:
                self.fields['default_recruitment'].queryset = Recruitment.objects.filter(
                    company_id=company,
                    closed=False,
                    is_active=True
                )