"""
views.py

This module contains the view functions for handling HTTP requests and rendering
responses in your application.

Each view function corresponds to a specific URL route and performs the necessary
actions to handle the request, process data, and generate a response.

This module is part of the recruitment project and is intended to
provide the main entry points for interacting with the application's functionality.
"""

import ast
import asyncio
import contextlib
import io
import json
import os
import random
import re
from datetime import datetime, timedelta
from itertools import chain
from urllib.parse import parse_qs, parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4
from django.views.decorators.cache import cache_control
from django.forms import ValidationError
from click import File
from django.template.loader import render_to_string
import fitz
from django import template
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.core import serializers
from django.core.cache import cache as CACHE
from django.core.mail import EmailMessage
from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q, Count, F, Value,Avg
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods
import pandas as pd
from requests import request
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import models
from django.conf import settings
from recruitment.utils.google_calendar import create_calendar_event, get_google_calendar_service
from recruitment.utils.google_forms import create_google_form
from base.backends import ConfiguredEmailBackend
from base.context_processors import check_candidate_self_tracking
from base.countries import country_arr, s_a, states
from base.forms import MailTemplateForm
from base.methods import export_data, generate_pdf, get_key_instances, sortby
from base.models import EmailLog, HorillaMailTemplate, JobPosition
from employee.models import Employee, EmployeeWorkInformation
import os
from django.template import Template, Context
from django.views.decorators.csrf import csrf_exempt
from django.utils.dateparse import parse_datetime

from recruitment.utils.skillzone_classifier import get_skillzone_classifier
from ..utils.cv_analysis import cv_analysis_manager,_event_loop
from horilla import settings
from recruitment.utils.google_calendar import handle_oauth2callback
from django.contrib.auth.models import User
from candidate_portal.models import VerificationToken, CandidateAuth

import logging
logger = logging.getLogger('recruitment')

from horilla.decorators import (
    hx_request_required,
    logger,
    login_required,
    permission_required,
)
from horilla.group_by import group_by_queryset
from notifications.signals import notify
from recruitment.decorators import manager_can_enter, recruitment_manager_can_enter
from recruitment.filters import (
    CandidateFilter,
    CandidateReGroup,
    InterviewFilter,
    RecruitmentFilter,
    SkillZoneCandFilter,
    SkillZoneFilter,
    StageFilter,
)
from recruitment.forms import (
    AIConfigurationForm,
    AIConfigurationTestForm,
    AddCandidateForm,
    ApplicationForm,
    CandidateCreationForm,
    CandidateExportForm,
    PrivacyPolicyForm,
    RecruitmentCreationForm,
    RejectReasonForm,
    ResumeForm,
    ModelForm,
    ScheduleInterviewForm,
    SkillImportForm,
    SkillsForm,
    SkillZoneCandidateForm,
    SkillZoneCreateForm,
    StageCreationForm,
    StageNoteForm,
    StageNoteUpdateForm,
    ToSkillZoneForm,
)
from recruitment.methods import recruitment_manages
from recruitment.models import (
    AIConfiguration,
    Candidate,
    CandidateRating,
    CandidateValidation,
    InterviewSchedule,
    PrivacyPolicy,
    Recruitment,
    RecruitmentGeneralSetting,
    RecruitmentSurvey,
    RejectReason,
    Resume,
    Motivation, 
    Skill,
    SkillZone,
    SkillZoneCandidate,
    SkillZoneImportHistory,
    Stage,
    StageFiles,
    StageNote,
)
from recruitment.views.paginator_qry import paginator_qry


def is_stagemanager(request, stage_id=False):
    """
    This method is used to identify the employee is a stage manager or
    not, if stage_id is passed through args, method will
    check the employee is manager to the corresponding stage, return
    tuple with boolean and all stages that employee is manager.
    if called this method without stage_id args it will return boolean
     with all the stage that the employee is stage manager
    Args:
        request : django http request
        stage_id : stage instance id
    """
    user = request.user
    employee = user.employee_get
    if not stage_id:
        return (
            employee.stage_set.exists() or user.is_superuser,
            employee.stage_set.all(),
        )
    stage_obj = Stage.objects.get(id=stage_id)
    return (
        employee in stage_obj.stage_managers.all()
        or user.is_superuser
        or is_recruitmentmanager(request, rec_id=stage_obj.recruitment_id.id)[0],
        employee.stage_set.all(),
    )


def is_recruitmentmanager(request, rec_id=False):
    """
    This method is used to identify the employee is a recruitment
    manager or not, if rec_id is passed through args, method will
    check the employee is manager to the corresponding recruitment,
    return tuple with boolean and all recruitment that employee is manager.
    if called this method without recruitment args it will return
    boolean with all the recruitment that the employee is recruitment manager
    Args:
        request : django http request
        rec_id : recruitment instance id
    """
    user = request.user
    employee = user.employee_get
    if not rec_id:
        return (
            employee.recruitment_set.exists() or user.is_superuser,
            employee.recruitment_set.all(),
        )
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    return (
        employee in recruitment_obj.recruitment_managers.all() or user.is_superuser,
        employee.recruitment_set.all(),
    )


def pipeline_grouper(request, recruitments):
    groups = []
    employee = request.user.employee_get
    for rec in recruitments:
        stages = StageFilter(request.GET, queryset=rec.stage_set.all()).qs.order_by(
            "sequence"
        )
        
        # Si c'est un demandeur, filtrer uniquement ses étapes
        if employee.is_selector:
            stages = stages.filter(
                stage_managers=employee,
                stage_type='selector'
            )
            
        all_stages_grouper = []
        data = {"recruitment": rec, "stages": []}
        
        for stage in stages.order_by("sequence"):
            all_stages_grouper.append({"grouper": stage, "list": []})
            stage_candidates = CandidateFilter(
                request.GET,
                stage.candidate_set.filter(
                    is_active=True,
                ),
            ).qs.order_by("sequence")

            page_name = "page" + stage.stage + str(rec.id)
            grouper = group_by_queryset(
                stage_candidates,
                "stage_id",
                request.GET.get(page_name),
                page_name,
            ).object_list
            data["stages"] = data["stages"] + grouper

        ordered_data = []

        # combining un used groups in to the grouper
        groupers = data["stages"]
        
        # Si c'est un demandeur, n'utiliser que ses étapes pour ordered_data
        stages_to_process = stages
        
        for stage in stages_to_process:
            found = False
            for grouper in groupers:
                if grouper["grouper"] == stage:
                    ordered_data.append(grouper)
                    found = True
                    break
            if not found:
                ordered_data.append({"grouper": stage})

        data = {
            "recruitment": rec,
            "stages": ordered_data,
        }
        
        # N'ajouter le recrutement que s'il y a des étapes visibles pour l'utilisateur
        if ordered_data or not employee.is_selector:
            groups.append(data)
            
    return groups


@login_required
@hx_request_required
@permission_required(perm="recruitment.add_recruitment")
def recruitment(request):
    """
    This method is used to create recruitment, when create recruitment this method
    add  recruitment view,create candidate, change stage sequence and so on, some of
    the permission is checking manually instead of using django permission permission
    to the  recruitment managers
    """
    form = RecruitmentCreationForm(user=request.user)  # Passer l'utilisateur
    if request.GET:
        form = RecruitmentCreationForm(initial=request.GET.dict(), user=request.user)
    dynamic = (
        request.GET.get("dynamic") if request.GET.get("dynamic") != "None" else None
    )
    if request.method == "POST":
        form = RecruitmentCreationForm(request.POST, user=request.user)
        if form.is_valid():
            recruitment_obj = form.save(commit=False)
            
            # S'assurer que la compagnie est celle de l'utilisateur si pas superuser
            if not request.user.is_superuser and hasattr(request.user, 'employee_get'):
                user_company = request.user.employee_get.company_id
                if user_company:
                    recruitment_obj.company_id = user_company
            
            # Handle Google Form generation if requested
            if form.cleaned_data.get('generate_form'):
                try:
                    form_url = create_google_form(
                        title=f"Application Form - {recruitment_obj.title}",
                        description=recruitment_obj.description or ""
                    )
                    if form_url:
                        recruitment_obj.google_form_url = form_url
                    else:
                        messages.error(
                            request, 
                            _("Failed to create Google Form. Please provide a form URL manually.")
                        )
                except Exception as e:
                    logger.error(f"Google Form creation error: {str(e)}")
                    messages.error(
                        request,
                        _("An error occurred while creating the Google Form. Please try again or provide a form URL manually.")
                    )

            recruitment_obj.save()
            
            # Set recruitment managers
            recruitment_obj.recruitment_managers.set(
                Employee.objects.filter(
                    id__in=form.data.getlist("recruitment_managers")
                )
            )

            recruitment_obj.selectors.set(
                Employee.objects.filter(
                    id__in=form.data.getlist("selectors")
                )
            )
            
            # Set open positions
            recruitment_obj.open_positions.set(
                JobPosition.objects.filter(id__in=form.data.getlist("open_positions"))
            )
            
            # Handle survey templates if they exist
            if "survey_templates" in form.cleaned_data:
                for survey in form.cleaned_data["survey_templates"]:
                    for sur in survey.recruitmentsurvey_set.all():
                        sur.recruitment_ids.add(recruitment_obj)
            
            messages.success(request, _("Recruitment added."))
            
            # Send notifications to recruitment managers
            with contextlib.suppress(Exception):
                managers = recruitment_obj.recruitment_managers.select_related(
                    "employee_user_id"
                )
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb="You are chosen as one of recruitment manager",
                    verb_ar="تم اختيارك كأحد مديري التوظيف",
                    verb_de="Sie wurden als einer der Personalvermittler ausgewählt",
                    verb_es="Has sido elegido/a como uno de los gerentes de contratación",
                    verb_fr="Vous êtes choisi(e) comme l'un des responsables du recrutement",
                    icon="people-circle",
                    redirect=reverse("pipeline"),
                )
            
            return HttpResponse("<script>location.reload();</script>")
            
    return render(
        request, 
        "recruitment/recruitment_form.html", 
        {"form": form, "dynamic": dynamic}
    )


def application_form(request):
    """
    This method renders candidate form to create candidate
    Args:
        request: The HTTP request object
    Returns:
        HttpResponse object with rendered template
    """
    logger.info("Starting application form processing")
    form = ApplicationForm()
    recruitment = None
    recruitment_id = request.GET.get("recruitmentId")
    resume_id = request.GET.get("resumeId")
    resume_obj = Resume.objects.filter(id=resume_id).first()
    
    # Variable pour vérifier si l'offre est expirée - sans modifier d'autres fonctionnalités
    is_expired = False

    if resume_obj:
        logger.debug(f"Found resume object with ID: {resume_id}")
        initial_data = {"resume": resume_obj.file.url if resume_obj else None}
        form = ApplicationForm(initial=initial_data)

    if recruitment_id is not None:
        logger.debug(f"Processing recruitment ID: {recruitment_id}")
        recruitment = Recruitment.objects.filter(id=recruitment_id)
        if recruitment.exists():
            recruitment = recruitment.first()
            logger.info(f"Found recruitment: {recruitment.title}")
            
            # Vérifier si l'offre est expirée - uniquement pour le bouton de soumission
            if recruitment.end_date:
                from django.utils import timezone
                today = timezone.now().date()
                is_expired = recruitment.end_date < today

    if request.method == "POST":
        logger.info("Processing POST request for application form")
        
        # Handle pre-uploaded resume
        if "resume" not in request.FILES and resume_id:
            if resume_obj and resume_obj.file:
                logger.debug("Using pre-uploaded resume")
                try:
                    file_content = resume_obj.file.read()
                    pdf_file = SimpleUploadedFile(
                        resume_obj.file.name, file_content, content_type="application/pdf"
                    )
                    request.FILES["resume"] = pdf_file
                except Exception as e:
                    logger.error(f"Error processing pre-uploaded resume: {str(e)}")
                    messages.error(request, _("Error processing resume file"))

        form = ApplicationForm(request.POST, request.FILES)
        # Passer la requête au formulaire pour obtenir l'adresse IP
        form.request = request
        
        try:
            if form.is_valid():
                logger.info("Form validation successful")
                candidate_obj = form.save(commit=False)
                recruitment_obj = candidate_obj.recruitment_id
                
                # Set initial stage
                stages = recruitment_obj.stage_set.all()
                if stages.filter(stage_type="applied").exists():
                    stage = stages.filter(stage_type="applied").first()
                else:
                    stage = stages.order_by("sequence").first()
                    
                candidate_obj.stage_id = stage
                logger.info(f"Set initial stage to: {stage}")

                # Handle resume file
                if 'resume' in request.FILES:
                    try:
                        resume = request.FILES.get("resume")
                        resume_path = f"recruitment/resume/{resume.name}"
                        with default_storage.open(resume_path, "wb+") as destination:
                            for chunk in resume.chunks():
                                destination.write(chunk)
                        candidate_obj.resume = resume_path
                        logger.info("Resume file processed successfully")
                    except Exception as e:
                        logger.error(f"Error saving resume file: {str(e)}")
                        messages.error(request, _("Error saving resume file"))
                        return render(
                            request,
                            "candidate/application_form.html",
                            {"form": form, "recruitment": recruitment, "resume": resume_obj},
                        )

                # Handle profile picture
                if 'profile' in request.FILES:
                    try:
                        profile = request.FILES["profile"]
                        profile_name = f"{candidate_obj.name.replace(' ', '_')}_{uuid4()}"
                        profile_path = f"recruitment/profile/{profile_name}_{profile.name}"
                        with default_storage.open(profile_path, "wb+") as destination:
                            for chunk in profile.chunks():
                                destination.write(chunk)
                        candidate_obj.profile = profile_path
                        logger.info("Profile picture processed successfully")
                    except Exception as e:
                        logger.error(f"Error saving profile picture: {str(e)}")
                        messages.error(request, _("Error saving profile picture"))

                try:
                    # Save the candidate
                    candidate_obj.save()
                    logger.info(f"Candidate saved successfully: {candidate_obj.name}")

                    # Mark resume as used if it was pre-uploaded
                    if resume_obj:
                        resume_obj.is_candidate = True
                        resume_obj.save()
                        logger.info("Pre-uploaded resume marked as used")
                    
                    # Vérifier si un candidat existe déjà avec cet email
                    user_exists = CandidateAuth.objects.filter(email=candidate_obj.email).exists()
                    logger.info(f"User already exists: {user_exists}")
                    
                    # Créer le token uniquement si l'utilisateur n'existe pas
                    token = None
                    if not user_exists:
                        try:
                            token = VerificationToken.objects.create(
                                email=candidate_obj.email,
                                candidate_id=candidate_obj.id,
                                expires_at=timezone.now() + timezone.timedelta(days=7)
                            )
                            logger.info(f"Token créé avec succès: {token.token}")
                        except Exception as e:
                            logger.error(f"Erreur lors de la création du token: {str(e)}")
                    # Préparer le contexte de la template
                    context = {
                        "message": _("Thank you for your application. We will review it shortly."),
                        "user_exists": user_exists,
                        "token": token if not user_exists and 'token' in locals() else None
                    }

                    logger.info(f"Contexte success.html: user_exists={user_exists}, token présent={token is not None if 'token' in locals() else False}")
                    
                    # Ajouter le token au contexte seulement s'il existe
                    if token:
                        context["token"] = token
                        logger.info(f"Token ajouté au contexte: {token.token}")
                    else:
                        logger.warning("Aucun token ajouté au contexte")

                    logger.debug(f"Contexte complet: {context}")
                    
                    # Handle redirection based on Google Form presence
                    if recruitment_obj.google_form_url:
                        logger.info("Redirecting to Google Form")
                        context["google_form_url"] = recruitment_obj.google_form_url
                        context["message"] = _("Thank you for your application. Please complete the additional questionnaire.")
                    logger.critical(f"DÉBOGAGE TOKEN: token existe: {'token' in locals()}")
                    if 'token' in locals():
                        logger.critical(f"DÉBOGAGE TOKEN: token.id={token.id}, token.token={token.token}")
                    logger.critical(f"DÉBOGAGE CONTEXTE: {context}")
                    return render(request, "candidate/success.html", context)
                        
                except ValidationError as e:
                    logger.error(f"Validation error saving candidate: {str(e)}")
                    messages.error(request, str(e))
                except Exception as e:
                    logger.error(f"Unexpected error saving candidate: {str(e)}")
                    messages.error(request, _("An error occurred while saving your application"))
            
            else:
                logger.warning("Form validation failed")
                logger.debug(f"Form errors: {form.errors}")
        
        except Exception as e:
            logger.error(f"Unexpected error in form processing: {str(e)}")
            messages.error(request, _("An error occurred while processing your application"))

        # Update job positions queryset
        form.fields["job_position_id"].queryset = (
            form.instance.recruitment_id.open_positions.all()
        )

    logger.debug("Rendering application form template")
    return render(
        request,
        "candidate/application_form.html",
        {"form": form, "recruitment": recruitment, "resume": resume_obj, "is_expired": is_expired},
    )

def google_form_callback(request):
    """
    Handle callback after Google Form submission
    """
    try:
        candidate_data = request.session.get("candidate")
        if not candidate_data:
            messages.error(request, _("Application session expired"))
            return redirect('open-recruitments')

        # Deserialize candidate data
        candidate_obj = next(
            serializers.deserialize("json", candidate_data['data'])
        ).object

        # Restore file paths from session
        if candidate_data.get('files'):
            if candidate_data['files'].get('resume_path'):
                candidate_obj.resume = candidate_data['files']['resume_path']
            if candidate_data['files'].get('profile_path'):
                candidate_obj.profile = candidate_data['files']['profile_path']

        # Save the candidate
        candidate_obj.save()

        # Clean up session
        del request.session['candidate']
        if 'candidate_token' in request.session:
            del request.session['candidate_token']

        messages.success(request, _("Your application has been successfully submitted."))
        return render(request, "candidate/success.html")

    except Exception as e:
        logger.error(f"Error in google_form_callback: {str(e)}")
        messages.error(
            request,
            _("An error occurred while processing your application. Please try again.")
        )
        return redirect('open-recruitments')

def get_recruitment_badge_class(recruitment):
    """
    Retourne la classe CSS appropriée selon le type de recrutement.
    """
    return {
        'INTERNAL': 'oh-badge--internal',
        'EXTERNAL': 'oh-badge--external',
        'BOTH': 'oh-badge--both',
    }.get(recruitment.recruitment_type, 'oh-badge--default')

@login_required
def get_selectors(request):
    """Return list of employees who are selectors"""
    selectors = Employee.objects.filter(is_active=True, is_selector=True)
    data = {str(emp.id): emp.get_full_name() for emp in selectors}
    return JsonResponse({'selectors': data})

@login_required
def get_all_employees(request):
    """Return list of all active employees"""
    employees = Employee.objects.filter(is_active=True)
    data = {str(emp.id): emp.get_full_name() for emp in employees}
    return JsonResponse({'employees': data})

@login_required
def get_company_selectors(request):
    """Return list of selectors from the user's company"""
    if not hasattr(request.user, 'employee_get'):
        return JsonResponse({'selectors': {}})
    
    user_company = request.user.employee_get.company_id
    
    if request.user.is_superuser:
        # Superuser voit tous les sélecteurs
        selectors = Employee.objects.filter(is_active=True, is_selector=True)
    elif user_company:
        # Utilisateur normal voit seulement les sélecteurs de sa compagnie
        selectors = Employee.objects.filter(
            is_active=True, 
            is_selector=True,
            company_id=user_company
        )
    else:
        selectors = Employee.objects.none()
    
    data = {str(emp.id): emp.get_full_name() for emp in selectors}
    return JsonResponse({'selectors': data})

@login_required
def get_company_managers(request):
    """Return list of managers from the user's company"""
    if not hasattr(request.user, 'employee_get'):
        return JsonResponse({'managers': {}})
    
    user_company = request.user.employee_get.company_id
    
    if request.user.is_superuser:
        # Superuser voit tous les managers
        managers = Employee.objects.filter(is_active=True)
    elif user_company:
        # Utilisateur normal voit seulement les managers de sa compagnie
        managers = Employee.objects.filter(
            is_active=True,
            company_id=user_company
        )
    else:
        managers = Employee.objects.none()
    
    data = {str(emp.id): emp.get_full_name() for emp in managers}
    return JsonResponse({'managers': data})

@login_required
def get_company_positions(request):
    """Return list of job positions from the user's company"""
    if not hasattr(request.user, 'employee_get'):
        return JsonResponse({'positions': {}})
    
    user_company = request.user.employee_get.company_id
    
    if request.user.is_superuser:
        # Superuser voit toutes les positions
        positions = JobPosition.objects.filter(is_active=True)
    elif user_company:
        # Utilisateur normal voit seulement les positions de sa compagnie
        positions = JobPosition.objects.filter(
            is_active=True,
            company_id=user_company
        )
    else:
        positions = JobPosition.objects.none()
    
    data = {str(pos.id): str(pos) for pos in positions}
    return JsonResponse({'positions': data})

@login_required
def stage_managers_options(request):
    """
    Return filtered list of employees based on stage type
    """
    stage_type = request.GET.get('stage_type')
    queryset = Employee.objects.filter(is_active=True)
    
    if stage_type == 'selector':
        queryset = queryset.filter(is_selector=True)
        
    managers = {
        str(emp.id): emp.get_full_name() 
        for emp in queryset.order_by('employee_first_name')
    }
    
    return JsonResponse({'managers': managers})

@login_required
@permission_required(perm="recruitment.view_recruitment")
def recruitment_view(request):
    """
    This method is used to render all recruitment to view
    """
    if not request.GET:
        request.GET.copy().update({"is_active": "on"})
    
    # Obtenir l'employé connecté
    employee = request.user.employee_get
    queryset = Recruitment.objects.filter(is_active=True)

    # Appliquer les filtres selon le type d'utilisateur
    if employee.is_selector:
        # Un sélecteur ne voit que les recrutements où il est sélecteur
        queryset = queryset.filter(selectors=employee)
    elif not request.user.is_superuser and employee.company_id:
        # Un utilisateur normal ne voit que les recrutements de sa compagnie
        queryset = queryset.filter(company_id=employee.company_id)

    # Choisir le template selon qu'il y a des recrutements ou non
    if Recruitment.objects.all():
        template = "recruitment/recruitment_view.html"
    else:
        template = "recruitment/recruitment_empty.html"

    # Gestion du filtre closed
    initial_tag = {}
    if request.GET.get("closed") == "false":
        queryset = queryset.filter(closed=True)
        initial_tag["closed"] = ["true"]
    else:
        queryset = queryset.filter(closed=False)
        initial_tag["closed"] = ["false"]

    # Application des filtres
    filter_obj = RecruitmentFilter(request.GET, queryset)
    filter_dict = request.GET.copy()
    for key, value in initial_tag.items():
        filter_dict[key] = value

    return render(
        request,
        template,
        {
            "data": paginator_qry(filter_obj.qs, request.GET.get("page")),
            "f": filter_obj,
            "filter_dict": filter_dict,
            "pd": request.GET.urlencode() + "&closed=false",
            "get_badge_class": get_recruitment_badge_class,
        },
    )

@login_required
@permission_required(perm="recruitment.change_recruitment")
@hx_request_required
def recruitment_update(request, rec_id):
    """
    This method is used to update recruitment, including selectors
    Args:
        rec_id (int): Recruitment ID
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    
    # Vérifier les permissions de compagnie
    if not request.user.is_superuser and hasattr(request.user, 'employee_get'):
        user_company = request.user.employee_get.company_id
        if user_company and recruitment_obj.company_id != user_company:
            messages.error(request, _("Vous n'avez pas l'autorisation de modifier ce recrutement."))
            return HttpResponse("<script>window.location.reload();</script>")
    
    survey_template_list = []
    survey_templates = RecruitmentSurvey.objects.filter(
        recruitment_ids=rec_id
    ).distinct()
    
    for survey in survey_templates:
        survey_template_list.append(survey.template_id.all())

    # Initialisation des données existantes
    initial_data = {
        'selectors': recruitment_obj.selectors.all(),
        'recruitment_managers': recruitment_obj.recruitment_managers.all(),
        'open_positions': recruitment_obj.open_positions.all(),
        'survey_templates': survey_template_list,
    }

    form = RecruitmentCreationForm(
        instance=recruitment_obj, 
        initial=initial_data,
        user=request.user  # Passer l'utilisateur
    )
    
    dynamic = request.GET.get("dynamic") if request.GET.get("dynamic") != "None" else None

    if request.method == "POST":
        form = RecruitmentCreationForm(
            request.POST, 
            instance=recruitment_obj,
            user=request.user  # Passer l'utilisateur
        )
        if form.is_valid():
            recruitment_obj = form.save(commit=False)
            
            # Mise à jour des relations ManyToMany
            recruitment_obj.selectors.set(form.cleaned_data['selectors'])
            recruitment_obj.recruitment_managers.set(
                Employee.objects.filter(
                    id__in=form.data.getlist("recruitment_managers")
                )
            )
            recruitment_obj.open_positions.set(
                JobPosition.objects.filter(id__in=form.data.getlist("open_positions"))
            )

            # Gestion Google Form
            if form.cleaned_data.get('generate_form'):
                try:
                    form_url = create_google_form(
                        title=f"Application Form - {recruitment_obj.title}",
                        description=recruitment_obj.description or ""
                    )
                    if form_url:
                        recruitment_obj.google_form_url = form_url
                except Exception as e:
                    logger.error(f"Google Form error: {str(e)}")

            recruitment_obj.save()

            # Mise à jour des templates de sondage
            if "survey_templates" in form.cleaned_data:
                for survey in form.cleaned_data["survey_templates"]:
                    for sur in survey.recruitmentsurvey_set.all():
                        sur.recruitment_ids.add(recruitment_obj)

            messages.success(request, _("Recruitment Updated."))
            
            # Notification aux managers
            try:
                managers = recruitment_obj.recruitment_managers.select_related("employee_user_id")
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"You are chosen as recruitment manager for {recruitment_obj.title}",
                    icon="people-circle",
                    redirect=reverse("pipeline"),
                )
            except Exception as e:
                logger.error(f"Notification error: {str(e)}")

            return HttpResponse("<script>window.location.reload();</script>")

    return render(
        request,
        "recruitment/recruitment_update_form.html",
        {
            "form": form, 
            "dynamic": dynamic,
            "recruitment": recruitment_obj
        },
    )


def paginator_qry_recruitment_limited(qryset, page_number):
    """
    This method is used to generate common paginator limit with ordering.
    """
    # Add default ordering by created_at in descending order
    qryset = qryset.order_by('-created_at')
    paginator = Paginator(qryset, 4)
    qryset = paginator.get_page(page_number)
    return qryset


@login_required
@manager_can_enter(perm="recruitment.view_recruitment") 
def recruitment_pipeline(request):
    """
    This method is used to filter out candidate through pipeline structure
    """
    employee = request.user.employee_get
    view = request.GET.get('view', 'list')

    # Logique spécifique pour les demandeurs
    if employee.is_selector:
        # Récupérer les recrutements où l'employé est assigné comme demandeur
        selector_stages = Stage.objects.filter(
            stage_managers=employee,
            stage_type='selector'
        )
        recruitment_ids = selector_stages.values_list('recruitment_id', flat=True).distinct()
        base_queryset = Recruitment.objects.filter(id__in=recruitment_ids)
    else:
        # Logique existante pour les autres utilisateurs
        base_queryset = employee.get_visible_recruitments()
    
    filter_obj = RecruitmentFilter(
        request.GET,
        queryset=base_queryset
    )

    if filter_obj.qs.exists():
        template = "pipeline/pipeline.html"
    else:
        template = "pipeline/pipeline_empty.html"

    visible_recruitment_ids = base_queryset.values_list('id', flat=True)
    
    # Pour les demandeurs, ne montrer que leurs étapes
    if employee.is_selector:
        stage_queryset = Stage.objects.filter(
            recruitment_id__in=visible_recruitment_ids,
            stage_managers=employee,
            stage_type='selector'
        )
    else:
        stage_queryset = Stage.objects.filter(
            recruitment_id__in=visible_recruitment_ids
        )

    stage_filter = StageFilter(
        request.GET, 
        queryset=stage_queryset
    )
    
    candidate_filter = CandidateFilter(
        request.GET,
        queryset=Candidate.objects.filter(recruitment_id__in=visible_recruitment_ids)
    )

    recruitments = paginator_qry_recruitment_limited(
        filter_obj.qs, 
        request.GET.get("page")
    )

    now = timezone.now()

    return render(
        request,
        template,
        {
            "rec_filter_obj": filter_obj,
            "recruitment": recruitments,
            "stage_filter_obj": stage_filter,
            "candidate_filter_obj": candidate_filter,
            "now": now,
            "view": view,
        },
    )

@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.view_recruitment")
def filter_pipeline(request):
    """
    This method is used to search/filter from pipeline
    """
    filter_obj = RecruitmentFilter(request.GET)
    stage_filter = StageFilter(request.GET)
    candidate_filter = CandidateFilter(request.GET)
    view = request.GET.get("view")
    recruitments = filter_obj.qs.filter(is_active=True)
    if not request.user.has_perm("recruitment.view_recruitment"):
        recruitments = recruitments.filter(
            Q(recruitment_managers=request.user.employee_get)
        )
        stage_recruitment_ids = (
            stage_filter.qs.filter(stage_managers=request.user.employee_get)
            .values_list("recruitment_id", flat=True)
            .distinct()
        )
        recruitments = recruitments | filter_obj.qs.filter(id__in=stage_recruitment_ids)
        recruitments = recruitments.filter(is_active=True).distinct()

    closed = request.GET.get("closed")
    filter_dict = parse_qs(request.GET.urlencode())
    filter_dict = get_key_instances(Recruitment, filter_dict)

    cache_key = request.session.session_key + "pipeline"
    CACHE.set(
        cache_key,
        {
            "candidates": candidate_filter.qs.filter(is_active=True).order_by(
                "sequence"
            ),
            "stages": stage_filter.qs.order_by("sequence"),
            "recruitments": recruitments,
            "filter_dict": filter_dict,
            "filter_query": request.GET,
        },
        timeout=3600  # Ajout d'un timeout explicite d'une heure
    )

    previous_data = request.GET.urlencode()
    recruitments = recruitments.order_by('-created_at')
    paginator = Paginator(recruitments, 4)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    template = "pipeline/components/pipeline_search_components.html"
    if request.GET.get("view") == "card":
        template = "pipeline/kanban_components/kanban.html"
    return render(
        request,
        template,
        {
            "recruitment": page_obj,
            "stage_filter_obj": stage_filter,
            "candidate_filter_obj": candidate_filter,
            "filter_dict": filter_dict,
            "status": closed,
            "view": view,
            "pd": previous_data,
        },
    )


@login_required
@manager_can_enter("recruitment.view_recruitment")
def get_stage_badge_count(request):
    """
    Method to update stage badge count
    """
    stage_id = request.GET["stage_id"]
    stage = Stage.objects.get(id=stage_id)
    count = stage.candidate_set.filter(is_active=True).count()
    return HttpResponse(count)


@login_required
@manager_can_enter(perm="recruitment.view_recruitment")
@cache_control(max_age=60)  # Cache de 1 minute 
def stage_component(request, view: str = "list"):
    """
    Composant d'affichage des étapes avec filtrage pour les demandeurs
    """
    recruitment_id = request.GET["rec_id"]
    recruitment = Recruitment.objects.get(id=recruitment_id)
    employee = request.user.employee_get
    
    # Filtrer les étapes visibles selon le type d'utilisateur
    if employee.is_selector:
        base_queryset = Stage.objects.filter(
            recruitment_id=recruitment_id,
            stage_managers=employee,
            stage_type='selector'
        )
    else:
        base_queryset = Stage.objects.filter(
            recruitment_id=recruitment_id
        )
    
    # Ajouter l'annotation pour le tri dynamique
    ordered_stages = base_queryset.annotate(
        has_candidates=models.Exists(
            Candidate.objects.filter(
                stage_id=models.OuterRef('pk'),
                is_active=True
            )
        ),
        # Les stages fixes
        stage_order=models.Case(
            # Applied et selector toujours fixes en premier
            models.When(stage_type='applied', then=models.Value(0)),
            models.When(stage_type='selector', then=models.Value(1)),
            # Stages avec candidats montent en priorité
            models.When(
                has_candidates=True,
                stage_type='test',
                then=models.Value(2)
            ),
            models.When(
                has_candidates=True,
                stage_type='interview',
                then=models.Value(3)
            ),
            # Stages sans candidats descendent
            models.When(stage_type='test', then=models.Value(12)),
            models.When(stage_type='interview', then=models.Value(13)),
            # Stages spéciaux toujours à la fin
            models.When(stage_type='cancelled', then=models.Value(98)),
            models.When(stage_type='hired', then=models.Value(99)),
            default=models.Value(50),
            output_field=models.IntegerField(),
        )
    ).order_by('stage_order', 'sequence')

    template = "pipeline/components/stages_tab_content.html"
    if view == "card":
        template = "pipeline/kanban_components/kanban_stage_components.html"
        
    return render(
        request,
        template,
        {
            "rec": recruitment,
            "ordered_stages": ordered_stages,
        }
    )

@login_required
@require_http_methods(["POST"])
def validate_selected_candidates(request):
    """
    Vue pour valider/dévalider les candidats sélectionnés
    """
    try:
        # Récupérer les données
        candidate_ids = request.POST.getlist('candidate_ids[]') or request.POST.get('candidate_ids', '').split(',')
        stage_id = request.POST.get('stage_id')
        action = request.POST.get('action', 'validate')
        stage = get_object_or_404(Stage, id=stage_id)
        selector = request.user.employee_get
        is_validating = action == 'validate'

        # Vérifier les permissions
        if not (selector.is_selector and stage.stage_managers.filter(id=selector.id).exists()):
            return JsonResponse({
                'status': 'error',
                'message': "Vous n'êtes pas autorisé à valider les candidats"
            }, status=403)

        # Traiter chaque candidat
        results = []
        for candidate_id in candidate_ids:
            candidate = get_object_or_404(Candidate, id=candidate_id)
            
            # Créer ou mettre à jour la validation
            validation, _ = CandidateValidation.objects.update_or_create(
                stage=stage,
                candidate=candidate,
                selector=selector,
                defaults={
                    'is_validated': is_validating,
                    'validated_at': timezone.now()
                }
            )
            
            results.append({
                'id': str(candidate.id),
                'isValidated': validation.is_validated
            })

        # Retourner la réponse
        return JsonResponse({
            'status': 'success',
            'message': "Candidats validés" if is_validating else "Candidats annuler",
            'validatedCandidates': results
        })

    except Exception as e:
        print(f"Error in validate_selected_candidates: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': f"Une erreur s'est produite: {str(e)}"
        }, status=500)
def is_currently_validated(self):
        """
        Retourne True si le candidat est actuellement validé
        """
        validation = self.selector_validations.filter(is_validated=True).first()
        return bool(validation)

@login_required
@require_http_methods(["POST"])
def toggle_candidate_validation(request):
    """
    Vue pour basculer la validation d'un candidat
    """
    candidate_id = request.POST.get('candidate_id')
    stage_id = request.POST.get('stage_id')
    
    candidate = get_object_or_404(Candidate, id=candidate_id)
    stage = get_object_or_404(Stage, id=stage_id)
    selector = request.user.employee_get
    
    if not selector.is_selector or not stage.stage_managers.filter(id=selector.id).exists():
        return JsonResponse({
            'status': 'error',
            'message': _("Permission refusée")
        }, status=403)
        
    validation, created = CandidateValidation.objects.get_or_create(
        candidate=candidate,
        stage=stage,
        selector=selector,
        defaults={'is_active': True}
    )
    
    if not created:
        validation.is_active = not validation.is_active
        validation.save()
    
    message = _("Candidat validé") if validation.is_active else _("Candidat dévalidé")
    
    return JsonResponse({
        'status': 'success',
        'is_validated': validation.is_active,
        'message': message
    })

@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def update_candidate_stage_and_sequence(request):
    """
    Update candidate sequence method
    """
    order_list = request.GET.getlist("order")
    stage_id = request.GET["stage_id"]
    stage = (
        CACHE.get(request.session.session_key + "pipeline")["stages"]
        .filter(id=stage_id)
        .first()
    )
    context = {}
    for index, cand_id in enumerate(order_list):
        candidate = CACHE.get(request.session.session_key + "pipeline")[
            "candidates"
        ].filter(id=cand_id)
        candidate.update(sequence=index, stage_id=stage)
    if stage.stage_type == "hired":
        if stage.recruitment_id.is_vacancy_filled():
            context["message"] = _("Vaccancy is filled")
            context["vacancy"] = stage.recruitment_id.vacancy
    return JsonResponse(context)


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def update_candidate_sequence(request):
    """
    Update candidate sequence method
    """
    order_list = request.GET.getlist("order")
    stage_id = request.GET["stage_id"]
    stage = (
        CACHE.get(request.session.session_key + "pipeline")["stages"]
        .filter(id=stage_id)
        .first()
    )
    data = {}
    for index, cand_id in enumerate(order_list):
        candidate = CACHE.get(request.session.session_key + "pipeline")[
            "candidates"
        ].filter(id=cand_id)
        candidate.update(sequence=index, stage_id=stage)
    return JsonResponse(data)


def limited_paginator_qry(queryset, page):
    """
    Limited pagination
    """
    paginator = Paginator(queryset, 20)
    queryset = paginator.get_page(page)
    return queryset


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.view_recruitment")
def candidate_component(request):
    """
    Candidate component
    """
    # Vérifier si le cache existe
    cached_data = CACHE.get(request.session.session_key + "pipeline")
    if cached_data is None:
        response = render(request, "pipeline/components/pipeline_search_components.html")
        return HttpResponse(response.content.decode("utf-8") + "<script>htmx.trigger('#pipeline-container', 'load')</script>")

    stage_id = request.GET.get("stage_id")
    stage = cached_data["stages"].filter(id=stage_id).first()
   
    candidates = cached_data["candidates"]
    candidates = [cand for cand in candidates if cand.stage_id == stage]
    
    # Ajout du tri par score
    order_by = request.GET.get('orderby', '-score')
    reverse_order = order_by.startswith('-')
    order_by = order_by.lstrip('-')

    # Fonction de tri sécurisée qui gère les valeurs None
    def safe_sort_key(candidate):
        if order_by == 'score':
            # Utiliser 0 comme valeur par défaut pour le score
            return candidate.score or 0
        elif order_by == 'ai_score':
            # Utiliser 0 comme valeur par défaut pour le score AI
            return candidate.ai_score or 0
        else:
            # Pour les autres attributs, utiliser getattr avec 0 comme valeur par défaut
            return getattr(candidate, order_by, 0)

    # Trier les candidats en utilisant la fonction sécurisée  
    candidates = sorted(candidates, key=safe_sort_key, reverse=reverse_order)

    template = "pipeline/components/candidate_stage_component.html"
    if cached_data["filter_query"].get("view") == "card":
        template = "pipeline/kanban_components/candidate_kanban_components.html"

    now = timezone.now()

    # Utilisez le premier candidat de la liste s'il existe, sinon un dictionnaire vide
    first_candidate = candidates[0] if candidates else {}

    return render(
        request,
        template,
        {
            "candidates": limited_paginator_qry(
                candidates, request.GET.get("candidate_page")
            ),
            "stage": stage,
            "rec": getattr(first_candidate, "recruitment_id", {}),
            "now": now,
        },
    )
   

@login_required 
@manager_can_enter("recruitment.change_candidate") 
def change_candidate_stage(request):
    if request.method == "POST":
        try:
            canIds = request.POST.get("canIds")
            stage_id = request.POST.get("stageId")
            
            if not canIds or not stage_id:
                return JsonResponse({"error": "Missing required data"}, status=400)
                
            context = {}
            stages_to_update = set()
            recruitment_id = None

            # Traiter le changement d'étape
            if request.GET.get("bulk") == "True":
                canIds = json.loads(canIds)
                updated_count = len(canIds)
                for cand_id in canIds:
                    candidate = Candidate.objects.get(id=cand_id)
                    old_stage = candidate.stage_id
                    stages_to_update.add(old_stage.id)
                    
                    stage = Stage.objects.select_related('recruitment_id').get(id=stage_id)
                    if not recruitment_id:
                        recruitment_id = stage.recruitment_id.id
                    candidate.stage_id = stage
                    candidate.save()
                    stages_to_update.add(stage.id)
                
                # Ajouter le message de succès pour le bulk update
                context["message"] = _("{} candidates successfully updated").format(updated_count)
                context["update_type"] = "bulk"
            else:
                candidate = Candidate.objects.get(id=canIds)
                old_stage = candidate.stage_id
                stages_to_update.add(old_stage.id)
                
                stage = Stage.objects.select_related('recruitment_id').get(id=stage_id)
                recruitment_id = stage.recruitment_id.id
                candidate.stage_id = stage
                candidate.save()
                stages_to_update.add(stage.id)

                # Message pour une mise à jour individuelle
                context["message"] = _("Candidate {} successfully moved to {}").format(
                    candidate.name, 
                    stage.stage
                )
                context["update_type"] = "single"

            # IMPORTANT: Nettoyer le cache pour éviter les données obsolètes
            cache_key = request.session.session_key + "pipeline"
            CACHE.delete(cache_key)

            # Préparer les données de mise à jour
            stages_html = {}
            stage_counts = {}
            
            # Récupérer toutes les étapes triées du recrutement
            recruitment_stages = Stage.objects.filter(
                recruitment_id=recruitment_id
            ).annotate(
                has_candidates=models.Exists(
                    Candidate.objects.filter(
                        stage_id=models.OuterRef('pk'),
                        is_active=True
                    )
                ),
                stage_order=models.Case(
                    models.When(stage_type='applied', then=models.Value(0)),
                    models.When(stage_type='selector', then=models.Value(1)),
                    models.When(
                        has_candidates=True,
                        stage_type='test',
                        then=models.Value(2)
                    ),
                    models.When(
                        has_candidates=True,
                        stage_type='interview',
                        then=models.Value(3)
                    ),
                    models.When(stage_type='test', then=models.Value(12)),
                    models.When(stage_type='interview', then=models.Value(13)),
                    models.When(stage_type='cancelled', then=models.Value(98)),
                    models.When(stage_type='hired', then=models.Value(99)),
                    default=models.Value(50),
                    output_field=models.IntegerField(),
                )
            ).order_by('stage_order', 'sequence')

            # Vérifier si l'étape est de type "hired" et mettre à jour le statut de vacance
            stage = Stage.objects.get(id=stage_id)
            if stage.stage_type == 'hired':
                recruitment = stage.recruitment_id
                if recruitment.is_vacancy_filled():
                    context['vacancy_filled'] = True
                    context['vacancy'] = recruitment.vacancy
                    context['message'] += _(". Note: All positions are now filled")

            # Mettre à jour uniquement les étapes affectées
            for s_id in stages_to_update:
                try:
                    stage = recruitment_stages.get(id=s_id)
                    candidates = Candidate.objects.filter(
                        stage_id=s_id, 
                        is_active=True
                    ).order_by('sequence')
                    
                    stages_html[s_id] = render_to_string(
                        "pipeline/components/candidate_stage_component.html",
                        {
                            "candidates": limited_paginator_qry(candidates, request.GET.get("candidate_page")),
                            "stage": stage,
                            "rec": stage.recruitment_id,
                            "now": timezone.now(),
                        },
                        request
                    )
                    stage_counts[s_id] = candidates.count()
                except Exception as e:
                    logger.warning(f"Erreur lors du rendu de l'étape {s_id}: {str(e)}")
                    continue

            # Ajouter les méta-informations de mise à jour
            context.update({
                "stages_html": stages_html,
                "stage_counts": stage_counts,
                "stages_order": {stage.id: idx for idx, stage in enumerate(recruitment_stages)},
                "recruitment_id": recruitment_id,
                "updated_stages": list(stages_to_update),
                "status": "success",
                "timestamp": timezone.now().isoformat()
            })
            
            return JsonResponse(context)
            
        except Candidate.DoesNotExist:
            return JsonResponse({
                "error": _("Candidate not found"),
                "status": "error"
            }, status=404)
        except Stage.DoesNotExist:
            return JsonResponse({
                "error": _("Stage not found"),
                "status": "error"
            }, status=404)
        except Exception as e:
            logger.error(f"Error in change_candidate_stage: {str(e)}", exc_info=True)
            
            # En cas d'erreur, assurez-vous également de nettoyer le cache
            if hasattr(request, 'session') and request.session.session_key:
                cache_key = request.session.session_key + "pipeline"
                CACHE.delete(cache_key)
                
            return JsonResponse({
                "error": _("An error occurred while updating stages"),
                "details": str(e),
                "status": "error"
            }, status=500)
    
    return JsonResponse({
        "error": _("Invalid request method"),
        "status": "error"
    }, status=400)

@login_required
@permission_required(perm="recruitment.view_recruitment")
def recruitment_pipeline_card(request):
    """
    This method is used to render pipeline card structure.
    """
    search = request.GET.get("search")
    search = search if search is not None else ""
    recruitment_obj = Recruitment.objects.all()
    candidates = Candidate.objects.filter(name__icontains=search, is_active=True)
    stages = Stage.objects.all()
    return render(
        request,
        "pipeline/pipeline_components/pipeline_card_view.html",
        {"recruitment": recruitment_obj, "candidates": candidates, "stages": stages},
    )


@login_required
@permission_required(perm="recruitment.delete_recruitment")
def recruitment_archive(request, rec_id):
    """
    This method is used to archive and unarchive the recruitment
    args:
        rec_id: The id of the Recruitment
    """
    try:
        recruitment = Recruitment.objects.get(id=rec_id)
        if recruitment.is_active:
            recruitment.is_active = False
        else:
            recruitment.is_active = True
        recruitment.save()
    except (Recruitment.DoesNotExist, OverflowError):
        messages.error(request, _("Recruitment Does not exists.."))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@hx_request_required
@recruitment_manager_can_enter(perm="recruitment.change_stage")
def stage_update_pipeline(request, stage_id):
    """
    This method is used to update stage from pipeline view
    """
    stage_obj = Stage.objects.get(id=stage_id)
    form = StageCreationForm(instance=stage_obj)
    if request.POST:
        form = StageCreationForm(request.POST, instance=stage_obj)
        if form.is_valid():
            stage_obj = form.save()
            messages.success(request, _("Stage updated."))
            with contextlib.suppress(Exception):
                managers = stage_obj.stage_managers.select_related("employee_user_id")
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"{stage_obj.stage} stage in recruitment {stage_obj.recruitment_id}\
                            is updated, You are chosen as one of the managers",
                    verb_ar=f"تم تحديث مرحلة {stage_obj.stage} في التوظيف {stage_obj.recruitment_id}\
                            ، تم اختيارك كأحد المديرين",
                    verb_de=f"Die Stufe {stage_obj.stage} in der Rekrutierung {stage_obj.recruitment_id}\
                            wurde aktualisiert. Sie wurden als einer der Manager ausgewählt",
                    verb_es=f"Se ha actualizado la etapa {stage_obj.stage} en la contratación\
                          {stage_obj.recruitment_id}.Has sido elegido/a como uno de los gerentes",
                    verb_fr=f"L'étape {stage_obj.stage} dans le recrutement {stage_obj.recruitment_id}\
                          a été mise à jour.Vous avez été choisi(e) comme l'un des responsables",
                    icon="people-circle",
                    redirect=reverse("pipeline"),
                )

            return HttpResponse("<script>window.location.reload()</script>")

    return render(request, "pipeline/form/stage_update.html", {"form": form})

def update_stage_containers(response, recruitment_id):
    """Helper to update all stages in a recruitment"""
    stages = Stage.objects.filter(recruitment_id=recruitment_id)
    stages_html = {}
    stage_counts = {}
    
    for stage in stages:
        candidates = Candidate.objects.filter(stage_id=stage.id)
        stages_html[stage.id] = render_to_string(
            "pipeline/components/candidate_stage_component.html",
            {
                "candidates": paginator_qry(candidates, None),
                "stage": stage, 
                "rec": stage.recruitment_id,
                "now": timezone.now(),
            },
            request
        )
        stage_counts[stage.id] = candidates.count()
        
    return {
        'stages_html': stages_html,
        'stage_counts': stage_counts
    }

@login_required
def get_unsuccessful_candidates(request):
    """
    Retourne les IDs des candidats qui n'ont pas été retenus
    """
    recruitment_id = request.GET.get('recruitment_id')
    
    # Liste des stages à exclure
    excluded_stages = [
        "Présélection des CV",
        "validation des CVs",
        "Mail aux candidats retenus",
        "Mail aux candidats malheureux"
    ]
    
    # Récupérer le stage des candidats malheureux
    rejected_stage = Stage.objects.filter(
        recruitment_id=recruitment_id,
        stage__icontains="Mail aux candidats malheureux"
    ).first()
    
    # Récupérer tous les candidats qui ne sont pas dans les stages exclus
    candidates = Candidate.objects.filter(
        recruitment_id=recruitment_id
    ).exclude(
        stage_id__stage__in=excluded_stages
    ).exclude(
        stage_id__stage_type="hired"
    ).values_list('id', flat=True)
    
    return JsonResponse({
        'candidate_ids': list(candidates),
        'rejected_stage_id': rejected_stage.id if rejected_stage else None
    })

@login_required
@hx_request_required
@recruitment_manager_can_enter(perm="recruitment.change_recruitment")
def recruitment_update_pipeline(request, rec_id):
    """
    This method is used to update recruitment from pipeline view
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    form = RecruitmentCreationForm(instance=recruitment_obj)
    if request.POST:
        form = RecruitmentCreationForm(request.POST, instance=recruitment_obj)
        if form.is_valid():
            recruitment_obj = form.save()
            messages.success(request, _("Recruitment updated."))
            with contextlib.suppress(Exception):
                managers = recruitment_obj.recruitment_managers.select_related(
                    "employee_user_id"
                )
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"{recruitment_obj} is updated, You are chosen as one of the managers",
                    verb_ar=f"تم تحديث {recruitment_obj}، تم اختيارك كأحد المديرين",
                    verb_de=f"{recruitment_obj} wurde aktualisiert.\
                          Sie wurden als einer der Manager ausgewählt",
                    verb_es=f"{recruitment_obj} ha sido actualizado/a. Has sido elegido\
                            a como uno de los gerentes",
                    verb_fr=f"{recruitment_obj} a été mis(e) à jour. Vous avez été\
                            choisi(e) comme l'un des responsables",
                    icon="people-circle",
                    redirect=reverse("pipeline"),
                )

            response = render(
                request, "pipeline/form/recruitment_update.html", {"form": form}
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(request, "pipeline/form/recruitment_update.html", {"form": form})


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_recruitment")
def recruitment_close_pipeline(request, rec_id):
    """
    This method is used to close recruitment from pipeline view
    """
    try:
        recruitment_obj = Recruitment.objects.get(id=rec_id)
        recruitment_obj.closed = True
        recruitment_obj.save()
        messages.success(request, "Recruitment closed successfully")
    except (Recruitment.DoesNotExist, OverflowError):
        messages.error(request, _("Recruitment Does not exists.."))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_recruitment")
def recruitment_reopen_pipeline(request, rec_id):
    """
    This method is used to reopen recruitment from pipeline view
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    recruitment_obj.closed = False
    recruitment_obj.save()

    messages.success(request, "Recruitment reopend successfully")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_stage_update(request, cand_id):
    """
    This method is a ajax method used to update candidate stage when drag and drop
    the candidate from one stage to another on the pipeline template
    Args:
        id : candidate_id
    """
    stage_id = request.POST["stageId"]
    candidate_obj = Candidate.objects.get(id=cand_id)
    history_queryset = candidate_obj.history_set.all().first()
    stage_obj = Stage.objects.get(id=stage_id)
    if candidate_obj.stage_id == stage_obj:
        return JsonResponse({"type": "noChange", "message": _("No change detected.")})
    # Here set the last updated schedule date on this stage if schedule exists in history
    history_queryset = candidate_obj.history_set.filter(stage_id=stage_obj)
    schedule_date = None
    if history_queryset.exists():
        # this condition is executed when a candidate dropped back to any previous
        # stage, if there any scheduled date then set it back
        schedule_date = history_queryset.first().schedule_date
    stage_manager_on_this_recruitment = (
        is_stagemanager(request)[1]
        .filter(recruitment_id=stage_obj.recruitment_id)
        .exists()
    )
    if (
        stage_manager_on_this_recruitment
        or request.user.is_superuser
        or is_recruitmentmanager(rec_id=stage_obj.recruitment_id.id)[0]
    ):
        candidate_obj.stage_id = stage_obj
        candidate_obj.hired = stage_obj.stage_type == "hired"
        candidate_obj.canceled = stage_obj.stage_type == "cancelled"
        candidate_obj.schedule_date = schedule_date
        candidate_obj.start_onboard = False
        candidate_obj.save()

        

        with contextlib.suppress(Exception):
            managers = stage_obj.stage_managers.select_related("employee_user_id")
            users = [employee.employee_user_id for employee in managers]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb=f"New candidate arrived on stage {stage_obj.stage}",
                verb_ar=f"وصل مرشح جديد إلى المرحلة {stage_obj.stage}",
                verb_de=f"Neuer Kandidat ist auf der Stufe {stage_obj.stage} angekommen",
                verb_es=f"Nuevo candidato llegó a la etapa {stage_obj.stage}",
                verb_fr=f"Nouveau candidat arrivé à l'étape {stage_obj.stage}",
                icon="person-add",
                redirect=reverse("pipeline"),
            )

        return JsonResponse(
            {"type": "success", "message": _("Candidate stage updated")}
        )
    return JsonResponse(
        {"type": "danger", "message": _("Something went wrong, Try agian.")}
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.view_stagenote")
def view_note(request, cand_id):
    """
    This method renders a template components to view candidate remark or note
    Args:
        id : candidate instance id
    """
    candidate_obj = Candidate.objects.get(id=cand_id)
    notes = candidate_obj.stagenote_set.all().order_by("-id")
    return render(
        request,
        "pipeline/pipeline_components/view_note.html",
        {"cand": candidate_obj, "notes": notes},
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_stagenote")
def add_note(request, cand_id=None):
    """
    This method renders template component to add candidate remark
    """
    form = StageNoteForm(initial={"candidate_id": cand_id})
    if request.method == "POST":
        form = StageNoteForm(
            request.POST,
            request.FILES,
        )
        if form.is_valid():
            note, attachment_ids = form.save(commit=False)
            candidate = Candidate.objects.get(id=cand_id)
            note.candidate_id = candidate
            note.stage_id = candidate.stage_id
            note.updated_by = request.user.employee_get
            note.save()
            note.stage_files.set(attachment_ids)
            messages.success(request, _("Note added successfully.."))
    candidate_obj = Candidate.objects.get(id=cand_id)
    return render(
        request,
        "candidate/individual_view_note.html",
        {
            "candidate": candidate_obj,
            "note_form": form,
        },
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_stagenote")
def create_note(request, cand_id=None):
    """
    This method renders template component to add candidate remark
    """
    form = StageNoteForm(initial={"candidate_id": cand_id})
    if request.method == "POST":
        form = StageNoteForm(request.POST, request.FILES)
        if form.is_valid():
            note, attachment_ids = form.save(commit=False)
            candidate = Candidate.objects.get(id=cand_id)
            note.candidate_id = candidate
            note.stage_id = candidate.stage_id
            note.updated_by = request.user.employee_get
            note.save()
            note.stage_files.set(attachment_ids)
            messages.success(request, _("Note added successfully.."))
            return redirect("view-note", cand_id=cand_id)
    candidate_obj = Candidate.objects.get(id=cand_id)
    notes = candidate_obj.stagenote_set.all().order_by("-id")
    return render(
        request,
        "pipeline/pipeline_components/view_note.html",
        {"note_form": form, "cand": candidate_obj, "notes": notes},
    )


@login_required
@manager_can_enter(perm="recruitment.change_stagenote")
def note_update(request, note_id):
    """
    This method is used to update the stage not
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=note_id)
    form = StageNoteUpdateForm(instance=note)
    if request.POST:
        form = StageNoteUpdateForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, _("Note updated successfully..."))
            cand_id = note.candidate_id.id
            return redirect("view-note", cand_id=cand_id)

    return render(
        request, "pipeline/pipeline_components/update_note.html", {"form": form}
    )


@login_required
@manager_can_enter(perm="recruitment.change_stagenote")
def note_update_individual(request, note_id):
    """
    This method is used to update the stage not
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=note_id)
    form = StageNoteForm(instance=note)
    if request.POST:
        form = StageNoteForm(request.POST, request.FILES, instance=note)
        if form.is_valid():
            form.save()
            messages.success(request, _("Note updated successfully..."))
            response = render(
                request,
                "pipeline/pipeline_components/update_note_individual.html",
                {"form": form},
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(
        request,
        "pipeline/pipeline_components/update_note_individual.html",
        {
            "form": form,
        },
    )


@login_required
@hx_request_required
def add_more_files(request, id):
    """
    This method is used to Add more files to the stage candidate note.
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=id)
    if request.method == "POST":
        files = request.FILES.getlist("files")
        files_ids = []
        for file in files:
            instance = StageFiles.objects.create(files=file)
            files_ids.append(instance.id)

            note.stage_files.add(instance.id)
    return redirect("view-note", cand_id=note.candidate_id.id)


@login_required
@hx_request_required
def add_more_individual_files(request, id):
    """
    This method is used to Add more files to the stage candidate note.
    Args:
        id : stage note instance id
    """
    note = StageNote.objects.get(id=id)
    if request.method == "POST":
        files = request.FILES.getlist("files")
        files_ids = []
        for file in files:
            instance = StageFiles.objects.create(files=file)
            files_ids.append(instance.id)
            note.stage_files.add(instance.id)
        messages.success(request, _("Files uploaded successfully"))
    return redirect(f"/recruitment/add-note/{note.candidate_id.id}/")


@login_required
def delete_stage_note_file(request, id):
    """
    This method is used to delete the stage note file
    Args:
        id : stage file instance id
    """
    file = StageFiles.objects.get(id=id)
    cand_id = file.stagenote_set.all().first().candidate_id.id
    file.delete()
    return redirect("view-note", cand_id=cand_id)


@login_required
@hx_request_required
def delete_individual_note_file(request, id):
    """
    This method is used to delete the stage note file
    Args:
        id : stage file instance id
    """
    file = StageFiles.objects.get(id=id)
    cand_id = file.stagenote_set.all().first().candidate_id.id
    file.delete()
    messages.success(request, _("File deleted successfully"))
    return redirect(f"/recruitment/add-note/{cand_id}/")


@login_required
@permission_required(perm="recruitment.change_candidate")
def candidate_schedule_date_update(request):
    """
    This is a an ajax method to update schedule date for a candidate
    """
    candidate_id = request.POST["candidateId"]
    schedule_date = request.POST["date"]
    candidate_obj = Candidate.objects.get(id=candidate_id)
    candidate_obj.schedule_date = schedule_date
    candidate_obj.save()
    return JsonResponse({"message": "congratulations"})


@login_required
@manager_can_enter(perm="recruitment.add_stage")
def stage(request):
    """
    This method is used to create stages, also several permission assigned to the stage managers
    """
    form = StageCreationForm(
        initial={"recruitment_id": request.GET.get("recruitment_id")},
        user=request.user  # Passer l'utilisateur
    )
    if request.method == "POST":
        form = StageCreationForm(request.POST, user=request.user)
        if form.is_valid():
            stage_obj = form.save()
            stage_obj.stage_managers.set(
                Employee.objects.filter(id__in=form.data.getlist("stage_managers"))
            )
            stage_obj.save()
            recruitment_obj = stage_obj.recruitment_id
            rec_stages = (
                Stage.objects.filter(recruitment_id=recruitment_obj, is_active=True)
                .order_by("sequence")
                .last()
            )
            if rec_stages.sequence is None:
                stage_obj.sequence = 1
            else:
                stage_obj.sequence = rec_stages.sequence + 1
            stage_obj.save()
            messages.success(request, _("Stage added."))
            with contextlib.suppress(Exception):
                managers = stage_obj.stage_managers.select_related("employee_user_id")
                users = [employee.employee_user_id for employee in managers]
                notify.send(
                    request.user.employee_get,
                    recipient=users,
                    verb=f"Stage {stage_obj} is updated on recruitment {stage_obj.recruitment_id},\
                          You are chosen as one of the managers",
                    verb_ar=f"تم تحديث المرحلة {stage_obj} في التوظيف\
                          {stage_obj.recruitment_id}، تم اختيارك كأحد المديرين",
                    verb_de=f"Stufe {stage_obj} wurde in der Rekrutierung {stage_obj.recruitment_id}\
                          aktualisiert. Sie wurden als einer der Manager ausgewählt",
                    verb_es=f"La etapa {stage_obj} ha sido actualizada en la contratación\
                          {stage_obj.recruitment_id}. Has sido elegido/a como uno de los gerentes",
                    verb_fr=f"L'étape {stage_obj} a été mise à jour dans le recrutement\
                          {stage_obj.recruitment_id}. Vous avez été choisi(e) comme l'un des responsables",
                    icon="people-circle",
                    redirect=reverse("pipeline"),
                )

            return HttpResponse("<script>location.reload();</script>")
    return render(request, "stage/stage_form.html", {"form": form})


@login_required
@permission_required(perm="recruitment.view_stage")
def stage_view(request):
    """
    This method is used to render all stages to a template
    """
    stages = Stage.objects.all()
    stages = stages.filter(recruitment_id__is_active=True)
    recruitments = group_by_queryset(
        stages,
        "recruitment_id",
        request.GET.get("rpage"),
    )
    filter_obj = StageFilter()
    form = StageCreationForm()
    if stages.exists():
        template = "stage/stage_view.html"
    else:
        template = "stage/stage_empty.html"
    return render(
        request,
        template,
        {
            "data": paginator_qry(stages, request.GET.get("page")),
            "form": form,
            "f": filter_obj,
            "recruitments": recruitments,
        },
    )


def stage_data(request, rec_id):
    stages = StageFilter(request.GET).qs.filter(recruitment_id__id=rec_id)
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(Stage, data_dict)

    return render(
        request,
        "stage/stage_component.html",
        {
            "data": paginator_qry(stages, request.GET.get("page")),
            "filter_dict": data_dict,
            "pd": request.GET.urlencode(),
            "hx_target": request.META.get("HTTP_HX_TARGET"),
        },
    )


@login_required
@manager_can_enter(perm="recruitment.change_stage")
@hx_request_required
def stage_update(request, stage_id):
    """
    This method is used to update stage, if the managers changed then\
    permission assigned to new managers also
    Args:
        id : stage_id

    """
    stages = Stage.objects.get(id=stage_id)
    form = StageCreationForm(instance=stages)
    if request.method == "POST":
        form = StageCreationForm(request.POST, instance=stages)
        if form.is_valid():
            form.save()
            messages.success(request, _("Stage updated."))
            response = render(
                request, "recruitment/recruitment_form.html", {"form": form}
            )
            return HttpResponse(
                response.content.decode("utf-8") + "<script>location.reload();</script>"
            )
    return render(request, "stage/stage_update_form.html", {"form": form})


@login_required
@hx_request_required
@manager_can_enter("recruitment.add_candidate")
def add_candidate(request):
    """
    This method is used to add candidate directly to the stage
    """
    form = AddCandidateForm(initial={"stage_id": request.GET.get("stage_id")})
    if request.POST:
        form = AddCandidateForm(
            request.POST,
            request.FILES,
            initial={"stage_id": request.GET.get("stage_id")},
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Candidate Added")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, "pipeline/form/candidate_form.html", {"form": form})


@login_required
@require_http_methods(["POST"])
@hx_request_required
def stage_title_update(request, stage_id):
    """
    This method is used to update the name of recruitment stage
    """
    stage_obj = Stage.objects.get(id=stage_id)
    stage_obj.stage = request.POST["stage"]
    stage_obj.save()
    message = _("The stage title has been updated successfully")
    return HttpResponse(
        f'<div class="oh-alert-container"><div class="oh-alert oh-alert--animated oh-alert--success">{message}</div></div>'
    )


@login_required
@permission_required(perm="recruitment.add_candidate")
def candidate(request):
    """
    This method used to create candidate
    """
    form = CandidateCreationForm()
    open_recruitment = Recruitment.objects.filter(closed=False, is_active=True)
    path = "/recruitment/candidate-view"
    if request.method == "POST":
        form = CandidateCreationForm(request.POST, request.FILES)
        if form.is_valid():
            candidate_obj = form.save(commit=False)
            candidate_obj.start_onboard = False
            candidate_obj.source = "software"
            if candidate_obj.stage_id is None:
                candidate_obj.stage_id = Stage.objects.filter(
                    recruitment_id=candidate_obj.recruitment_id, stage_type="initial"
                ).first()
            # when creating new candidate from onboarding view
            if request.GET.get("onboarding") == "True":
                candidate_obj.hired = True
                path = "/onboarding/candidates-view"
            if form.data.get("job_position_id"):
                candidate_obj.save()
                messages.success(request, _("Candidate added."))
            else:
                messages.error(request, "Job position field is required")
                return render(
                    request,
                    "candidate/candidate_create_form.html",
                    {"form": form, "open_recruitment": open_recruitment},
                )
            return redirect(path)

    return render(
        request,
        "candidate/candidate_create_form.html",
        {"form": form, "open_recruitment": open_recruitment},
    )


@login_required
@permission_required(perm="recruitment.add_candidate")
def recruitment_stage_get(_, rec_id):
    """
    This method returns all stages as json
    Args:
        id: recruitment_id
    """
    recruitment_obj = Recruitment.objects.get(id=rec_id)
    all_stages = recruitment_obj.stage_set.all()
    all_stage_json = serializers.serialize("json", all_stages)
    return JsonResponse({"stages": all_stage_json})


@login_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view(request):
    """
    Filtrer les candidats visibles pour les sélecteurs 
    """
    view_type = request.GET.get("view")
    previous_data = request.GET.urlencode()
    
    # Obtenir l'employé connecté
    employee = request.user.employee_get
    
    # Initialiser le queryset de base
    visible_recruitments = employee.get_visible_recruitments()
    candidates = Candidate.objects.filter(
        is_active=True,
        recruitment_id__in=visible_recruitments
    )
    
    # Si l'employé est un sélecteur, filtrer les candidats
    if employee.is_selector:
        # Obtenir les étapes où l'employé est sélecteur
        selector_stages = Stage.objects.filter(
            stage_managers=employee,
            stage_type='selector'
        )
        # Filtrer les candidats qui sont dans ces étapes
        candidates = candidates.filter(stage_id__in=selector_stages)
    
    recruitments = Recruitment.objects.filter(closed=False, is_active=True)
    mails = list(candidates.values_list("email", flat=True))
    existing_emails = list(
        User.objects.filter(username__in=mails).values_list("email", flat=True)
    )

    filter_obj = CandidateFilter(request.GET, queryset=candidates)
    
    if candidates.exists():
        template = "candidate/candidate_view.html"
    else:
        template = "candidate/candidate_empty.html"
        
    data_dict = parse_qs(previous_data)
    get_key_instances(Candidate, data_dict)

    # Store the candidates in the session
    request.session["filtered_candidates"] = [candidate.id for candidate in candidates]

    return render(
        request,
        template,
        {
            "data": paginator_qry(filter_obj.qs, request.GET.get("page")),
            "pd": previous_data,
            "f": filter_obj,
            "view_type": view_type,
            "filter_dict": data_dict,
            "gp_fields": CandidateReGroup.fields,
            "emp_list": existing_emails,
            "recruitments": recruitments,
        },
    )


@login_required
@hx_request_required
def interview_filter_view(request):
    """
    This method is used to filter Disciplinary Action.
    """

    previous_data = request.GET.urlencode()

    if request.user.has_perm("view_interviewschedule"):
        interviews = InterviewSchedule.objects.all().order_by("-interview_date")
    else:
        interviews = InterviewSchedule.objects.filter(
            employee_id=request.user.employee_get.id
        ).order_by("-interview_date")

    if request.GET.get("sortby"):
        interviews = sortby(request, interviews, "sortby")

    dis_filter = InterviewFilter(request.GET, queryset=interviews).qs

    page_number = request.GET.get("page")
    page_obj = paginator_qry(dis_filter, page_number)
    data_dict = parse_qs(previous_data)
    get_key_instances(InterviewSchedule, data_dict)
    now = timezone.now()
    return render(
        request,
        "candidate/interview_list.html",
        {
            "data": page_obj,
            "pd": previous_data,
            "filter_dict": data_dict,
            "now": now,
        },
    )


@login_required
def interview_view(request):
    """
    This method render all interviews to the template
    """
    view_type = request.GET.get('view_type', 'list')
    
    # Logique pour les interviews
    if request.user.has_perm("view_interviewschedule"):
        interviews = InterviewSchedule.objects.all().order_by("-interview_date")
    else:
        interviews = InterviewSchedule.objects.filter(
            employee_id=request.user.employee_get.id
        ).order_by("-interview_date")
    
    # Uniquement paginer si on est en vue liste
    if view_type == 'list':
        form = InterviewFilter(request.GET, queryset=interviews)
        page_number = request.GET.get("page")
        page_obj = paginator_qry(form.qs, page_number)
    else:
        form = InterviewFilter(request.GET, queryset=interviews)
        page_obj = interviews
    
    context = {
        "data": page_obj,
        "pd": request.GET.urlencode(),
        "f": form,
        "now": timezone.now(),
        "view_type": view_type,  # Important: s'assurer que ceci est passé au template
    }
    
    return render(request, "candidate/interview_view.html", context)

@login_required
@manager_can_enter(perm="recruitment.change_interviewschedule")
def interview_employee_remove(request, interview_id, employee_id):
    """
    This view is used to remove the employees from the meeting ,
    Args:
        interview_id(int) : primarykey of the interview.
        employee_id(int) : primarykey of the employee
    """
    interview = InterviewSchedule.objects.filter(id=interview_id).first()
    interview.employee_id.remove(employee_id)
    messages.success(request, "Interviewer removed succesfully.")
    interview.save()
    return redirect(interview_filter_view)


@login_required
def candidate_export(request):
    """
    This method is used to Export candidate data
    """
    if request.META.get("HTTP_HX_REQUEST"):
        export_column = CandidateExportForm()
        export_filter = CandidateFilter()
        content = {
            "export_filter": export_filter,
            "export_column": export_column,
        }
        return render(request, "candidate/export_filter.html", context=content)
    return export_data(
        request=request,
        model=Candidate,
        filter_class=CandidateFilter,
        form_class=CandidateExportForm,
        file_name="Candidate_export",
    )


@login_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view_list(request):
    """
    This method renders all candidate on candidate_list.html template
    """
    previous_data = request.GET.urlencode()
    candidates = Candidate.objects.all()
    if request.GET.get("is_active") is None:
        candidates = candidates.filter(is_active=True)
    candidates = CandidateFilter(request.GET, queryset=candidates).qs
    return render(
        request,
        "candidate/candidate_list.html",
        {
            "data": paginator_qry(candidates, request.GET.get("page")),
            "pd": previous_data,
        },
    )


@login_required
@hx_request_required
@permission_required(perm="recruitment.view_candidate")
def candidate_view_card(request):
    """
    This method renders all candidate on candidate_card.html template
    """
    previous_data = request.GET.urlencode()
    candidates = Candidate.objects.all()
    if request.GET.get("is_active") is None:
        candidates = candidates.filter(is_active=True)
    candidates = CandidateFilter(request.GET, queryset=candidates).qs
    return render(
        request,
        "candidate/candidate_card.html",
        {
            "data": paginator_qry(candidates, request.GET.get("page")),
            "pd": previous_data,
        },
    )


@login_required
@manager_can_enter(perm="recruitment.view_candidate")
def candidate_view_individual(request, cand_id, **kwargs):
    """
    This method is used to view profile of candidate.
    """
    candidate_obj = Candidate.find(cand_id)
    if not candidate_obj:
        messages.error(request, _("Candidate not found"))
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))

    mails = list(Candidate.objects.values_list("email", flat=True))
    # Query the User model to check if any email is present
    existing_emails = list(
        User.objects.filter(username__in=mails).values_list("email", flat=True)
    )
    ratings = candidate_obj.candidate_rating.all()
    rating_list = []
    avg_rate = 0
    for rating in ratings:
        rating_list.append(rating.rating)
    if len(rating_list) != 0:
        avg_rate = round(sum(rating_list) / len(rating_list))

    # Retrieve the filtered candidate from the session
    filtered_candidate_ids = request.session.get("filtered_candidates", [])

    # Convert the string to an actual list of integers
    requests_ids = (
        ast.literal_eval(filtered_candidate_ids)
        if isinstance(filtered_candidate_ids, str)
        else filtered_candidate_ids
    )

    next_id = None
    previous_id = None

    for index, req_id in enumerate(requests_ids):
        if req_id == cand_id:

            if index == len(requests_ids) - 1:
                next_id = None
            else:
                next_id = requests_ids[index + 1]
            if index == 0:
                previous_id = None
            else:
                previous_id = requests_ids[index - 1]
            break

    now = timezone.now()

    return render(
        request,
        "candidate/individual.html",
        {
            "candidate": candidate_obj,
            "previous": previous_id,
            "next": next_id,
            "requests_ids": requests_ids,
            "emp_list": existing_emails,
            "average_rate": avg_rate,
            "now": now,
        },
    )


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_update(request, cand_id, **kwargs):
    """
    Used to update or change the candidate
    Args:
        id : candidate_id
    """
    try:
        candidate_obj = Candidate.objects.get(id=cand_id)
        form = CandidateCreationForm(instance=candidate_obj)
        path = "/recruitment/candidate-view"
        if request.method == "POST":
            form = CandidateCreationForm(
                request.POST, request.FILES, instance=candidate_obj
            )
            if form.is_valid():
                candidate_obj = form.save()
                if candidate_obj.stage_id is None:
                    candidate_obj.stage_id = Stage.objects.filter(
                        recruitment_id=candidate_obj.recruitment_id,
                        stage_type="initial",
                    ).first()
                if candidate_obj.stage_id is not None:
                    if (
                        candidate_obj.stage_id.recruitment_id
                        != candidate_obj.recruitment_id
                    ):
                        candidate_obj.stage_id = (
                            candidate_obj.recruitment_id.stage_set.filter(
                                stage_type="initial"
                            ).first()
                        )
                if request.GET.get("onboarding") == "True":
                    candidate_obj.hired = True
                    path = "/onboarding/candidates-view"
                candidate_obj.save()
                messages.success(request, _("Candidate Updated Successfully."))
                return redirect(path)
        return render(request, "candidate/candidate_create_form.html", {"form": form})
    except (Candidate.DoesNotExist, OverflowError):
        messages.error(request, _("Candidate Does not exists.."))
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_conversion(request, cand_id, **kwargs):
    """
    This method is used to convert a candidate into employee
    Args:
        cand_id : candidate instance id
    """
    candidate_obj = Candidate.find(cand_id)
    if not candidate_obj:
        messages.error(request, _("Candidate not found"))
        return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    can_name = candidate_obj.name
    can_mob = candidate_obj.mobile
    can_job = candidate_obj.job_position_id
    can_dep = can_job.department_id
    can_mail = candidate_obj.email
    can_gender = candidate_obj.gender
    can_company = candidate_obj.recruitment_id.company_id
    user_exists = User.objects.filter(username=can_mail).exists()
    if user_exists:
        messages.error(request, _("Employee instance already exist"))
    elif not Employee.objects.filter(employee_user_id__username=can_mail).exists():
        new_employee = Employee.objects.create(
            employee_first_name=can_name,
            email=can_mail,
            phone=can_mob,
            gender=can_gender,
            is_directly_converted=True,
        )
        candidate_obj.converted_employee_id = new_employee
        candidate_obj.save()
        work_info, created = EmployeeWorkInformation.objects.get_or_create(
            employee_id=new_employee
        )
        work_info.job_position_id = can_job
        work_info.department_id = can_dep
        work_info.company_id = can_company
        work_info.save()
        messages.success(request, _("Employee instance created successfully"))
    else:
        messages.info(request, "A employee with this mail already exists")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def delete_profile_image(request, obj_id):
    """
    This method is used to delete the profile image of the candidate
    Args:
        obj_id : candidate instance id
    """
    candidate_obj = Candidate.objects.get(id=obj_id)
    try:
        if candidate_obj.profile:
            file_path = candidate_obj.profile.path
            absolute_path = os.path.join(settings.MEDIA_ROOT, file_path)
            os.remove(absolute_path)
            candidate_obj.profile = None
            candidate_obj.save()
            messages.success(request, _("Profile image removed."))
    except Exception as e:
        pass
    return redirect("rec-candidate-update", cand_id=obj_id)


@login_required
@permission_required(perm="recruitment.view_history")
def candidate_history(request, cand_id):
    """
    This method is used to view candidate stage changes
    Args:
        id : candidate_id
    """
    candidate_obj = Candidate.objects.get(id=cand_id)
    candidate_history_queryset = candidate_obj.history.all()
    return render(
        request,
        "candidate/candidate_history.html",
        {"history": candidate_history_queryset},
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.change_candidate")
def form_send_mail(request, cand_id=None):
    """
    This method is used to render the bootstrap modal content body form
    """
    candidate_obj = None
    stage_id = None
    if request.GET.get("stage_id"):
        stage_id = eval(request.GET.get("stage_id"))
    if cand_id:
        candidate_obj = Candidate.objects.get(id=cand_id)
    candidates = Candidate.objects.all()
    if stage_id and isinstance(stage_id, int):
        candidates = candidates.filter(stage_id__id=stage_id)
    else:
        stage_id = None

    templates = HorillaMailTemplate.objects.all()
    return render(
        request,
        "pipeline/pipeline_components/send_mail.html",
        {
            "cand": candidate_obj,
            "templates": templates,
            "candidates": candidates,
            "stage_id": stage_id,
            "searchWords": MailTemplateForm().get_template_language(),
        },
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_interviewschedule")
def interview_schedule(request, cand_id):
    """
    This method is used to Schedule interview to candidate
    Args:
        cand_id : candidate instance id
    """
    candidate = Candidate.objects.get(id=cand_id)
    candidates = Candidate.objects.filter(id=cand_id)
    template = "pipeline/pipeline_components/schedule_interview.html"
    form = ScheduleInterviewForm(initial={"candidate_id": candidate})
    form.fields["candidate_id"].queryset = candidates
    if request.method == "POST":
        form = ScheduleInterviewForm(request.POST)
        if form.is_valid():
            form.save()
            emp_ids = form.cleaned_data["employee_id"]
            cand_id = form.cleaned_data["candidate_id"]
            interview_date = form.cleaned_data["interview_date"]
            interview_time = form.cleaned_data["interview_time"]
            users = [employee.employee_user_id for employee in emp_ids]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb=f"You are scheduled as an interviewer for an interview with {cand_id.name} on {interview_date} at {interview_time}.",
                verb_ar=f"أنت مجدول كمقابلة مع {cand_id.name} يوم {interview_date} في توقيت {interview_time}.",
                verb_de=f"Sie sind als Interviewer für ein Interview mit {cand_id.name} am {interview_date} um {interview_time} eingeplant.",
                verb_es=f"Estás programado como entrevistador para una entrevista con {cand_id.name} el {interview_date} a las {interview_time}.",
                verb_fr=f"Vous êtes programmé en tant qu'intervieweur pour un entretien avec {cand_id.name} le {interview_date} à {interview_time}.",
                icon="people-circle",
                redirect=reverse("interview-view"),
            )

            messages.success(request, "Interview Scheduled successfully.")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, template, {"form": form, "cand_id": cand_id})


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_interviewschedule")
def create_interview_schedule(request):
    """
    This method is used to Schedule interview to candidate
    Args:
        cand_id : candidate instance id
    """
    candidates = Candidate.objects.all()
    template = "candidate/interview_form.html"
    form = ScheduleInterviewForm()
    form.fields["candidate_id"].queryset = candidates
    if request.method == "POST":
        form = ScheduleInterviewForm(request.POST)
        if form.is_valid():
            form.save()
            emp_ids = form.cleaned_data["employee_id"]
            cand_id = form.cleaned_data["candidate_id"]
            interview_date = form.cleaned_data["interview_date"]
            interview_time = form.cleaned_data["interview_time"]
            users = [employee.employee_user_id for employee in emp_ids]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb=f"You are scheduled as an interviewer for an interview with {cand_id.name} on {interview_date} at {interview_time}.",
                verb_ar=f"أنت مجدول كمقابلة مع {cand_id.name} يوم {interview_date} في توقيت {interview_time}.",
                verb_de=f"Sie sind als Interviewer für ein Interview mit {cand_id.name} am {interview_date} um {interview_time} eingeplant.",
                verb_es=f"Estás programado como entrevistador para una entrevista con {cand_id.name} el {interview_date} a las {interview_time}.",
                verb_fr=f"Vous êtes programmé en tant qu'intervieweur pour un entretien avec {cand_id.name} le {interview_date} à {interview_time}.",
                icon="people-circle",
                redirect=reverse("interview-view"),
            )

            messages.success(request, "Interview Scheduled successfully.")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, template, {"form": form})


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.delete_interviewschedule")
def interview_delete(request, interview_id):
    """
    This method is used to delete interview
    Args:
        interview_id : interview schedule instance id
    """
    view = request.GET["view"]
    interview = InterviewSchedule.objects.get(id=interview_id)
    interview.delete()
    messages.success(request, "Interview deleted successfully.")
    if view == "true":
        return redirect(interview_filter_view)
    else:
        return HttpResponse("<script>window.location.reload()</script>")


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.change_interviewschedule")
def interview_edit(request, interview_id):
    """
    This method is used to Edit Schedule interview
    Args:
        interview_id : interview schedule instance id
    """
    interview = InterviewSchedule.objects.get(id=interview_id)
    view = request.GET["view"]
    if view == "true":
        candidates = Candidate.objects.all()
        view = "true"
    else:
        candidates = Candidate.objects.filter(id=interview.candidate_id.id)
        view = "false"
    template = "pipeline/pipeline_components/schedule_interview_update.html"
    form = ScheduleInterviewForm(instance=interview)
    form.fields["candidate_id"].queryset = candidates
    if request.method == "POST":
        form = ScheduleInterviewForm(request.POST, instance=interview)
        if form.is_valid():
            emp_ids = form.cleaned_data["employee_id"]
            cand_id = form.cleaned_data["candidate_id"]
            interview_date = form.cleaned_data["interview_date"]
            interview_time = form.cleaned_data["interview_time"]
            form.save()
            users = [employee.employee_user_id for employee in emp_ids]
            notify.send(
                request.user.employee_get,
                recipient=users,
                verb=f"You are scheduled as an interviewer for an interview with {cand_id.name} on {interview_date} at {interview_time}.",
                verb_ar=f"أنت مجدول كمقابلة مع {cand_id.name} يوم {interview_date} في توقيت {interview_time}.",
                verb_de=f"Sie sind als Interviewer für ein Interview mit {cand_id.name} am {interview_date} um {interview_time} eingeplant.",
                verb_es=f"Estás programado como entrevistador para una entrevista con {cand_id.name} el {interview_date} a las {interview_time}.",
                verb_fr=f"Vous êtes programmé en tant qu'intervieweur pour un entretien avec {cand_id.name} le {interview_date} à {interview_time}.",
                icon="people-circle",
                redirect=reverse("interview-view"),
            )
            messages.success(request, "Interview updated successfully.")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        template,
        {
            "form": form,
            "interview_id": interview_id,
            "view": view,
        },
    )


def get_managers(request):
    cand_id = request.GET.get("cand_id")
    candidate_obj = Candidate.objects.get(id=cand_id)
    stage_obj = Stage.objects.filter(recruitment_id=candidate_obj.recruitment_id.id)

    # Combine the querysets into a single iterable
    all_managers = chain(
        candidate_obj.recruitment_id.recruitment_managers.all(),
        *[stage.stage_managers.all() for stage in stage_obj],
    )

    # Extract unique managers from the combined iterable
    unique_managers = list(set(all_managers))

    # Assuming you have a list of employee objects called 'unique_managers'
    employees_dict = {
        employee.id: employee.get_full_name() for employee in unique_managers
    }
    return JsonResponse({"employees": employees_dict})


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def send_acknowledgement(request):
    """
    Envoi d'un mail de confirmation avec option de planification d'entretien
    """
    logger.info("Début de send_acknowledgement")
    
    try:
        # Récupération des données de base
        candidate_id = request.POST.get("id")
        subject = request.POST.get("subject")
        body = request.POST.get("body")
        candidate_ids = request.POST.getlist("candidates")
        schedule_interview = request.POST.get("schedule_interview") == "on"
        
        # Traitement des pièces jointes
        attachments = [
            (f.name, f.read(), f.content_type) 
            for f in request.FILES.getlist("other_attachments")
        ]
        
        # Récupération des candidats
        candidates = Candidate.objects.filter(
            id__in=candidate_ids + ([candidate_id] if candidate_id else [])
        ).distinct()

        if not candidates.exists():
            raise ValueError("Aucun candidat sélectionné")

        # Si planification d'entretien demandée
        if schedule_interview:
            # Sauvegarder le contexte pour le callback OAuth
            request.session['pending_mail_data'] = {
                'candidate_id': candidate_id,
                'subject': subject,
                'body': body,
                'candidate_ids': candidate_ids,
                'template_attachments': request.POST.getlist("template_attachments"),
                'interview_date': request.POST.get("interview_date"),
                'interview_time': request.POST.get("interview_time"),
                'duration': request.POST.get("duration", "60"),
                'attendees': request.POST.get("attendees", "[]"),
                'schedule_interview': True,
            }

            # Initialisation Google Calendar
            service = get_google_calendar_service(request)
            if isinstance(service, HttpResponse):
                logger.info("Redirection vers l'authentification Google")
                return service

            # Configuration de l'entretien
            interview_date = request.POST.get("interview_date")
            interview_time = request.POST.get("interview_time")
            duration = int(request.POST.get("duration", 60))
            attendees = json.loads(request.POST.get("attendees", "[]"))

            # Traitement pour chaque candidat
            for candidate in candidates:
                try:
                    # Préparation du mail
                    context = {
                        "instance": candidate,
                        "self": request.user.employee_get
                    }
                    email_body = Template(body).render(Context(context))

                    # Création de l'événement Calendar
                    start_datetime = datetime.strptime(
                        f"{interview_date} {interview_time}", 
                        "%Y-%m-%d %H:%M"
                    )
                    end_datetime = start_datetime + timedelta(minutes=duration)
                    
                    all_attendees = [
                        {'email': candidate.email},
                        *[{'email': email} for email in attendees]
                    ]

                    event_details = {
                        'summary': f"Interview with {candidate.name}",
                        'description': email_body,
                        'start_time': start_datetime.isoformat(),
                        'end_time': end_datetime.isoformat(),
                        'attendees': all_attendees,
                        'id': f"interview_{candidate.id}_{start_datetime.strftime('%Y%m%d')}"
                    }
                    
                    logger.info("Création de l'événement Calendar")
                    event = create_calendar_event(service, event_details)
                    
                    if event:
                        logger.info("Événement Calendar créé avec succès")
                        interview = InterviewSchedule.objects.create(
                            candidate_id=candidate,
                            interview_date=interview_date,
                            interview_time=interview_time,
                            description=email_body,
                            google_event_id=event.get('id'),
                            google_meet_link=event.get('hangoutLink')
                        )
                        
                        email_body += f"\n\nLien Google Meet : {event.get('hangoutLink')}"
                    else:
                        logger.error("Échec de la création de l'événement Calendar")

                    # Envoi du mail
                    email = EmailMessage(
                        subject=subject,
                        body=email_body,
                        from_email=request.user.email,
                        to=[candidate.email],
                        attachments=attachments
                    )
                    email.content_subtype = "html"
                    email.send()
                    
                    logger.info(f"Mail envoyé à {candidate.email}")

                except Exception as e:
                    logger.error(f"Erreur pour le candidat {candidate.name}: {str(e)}")
                    messages.error(
                        request,
                        f"Erreur lors du traitement de {candidate.name}: {str(e)}"
                    )
        else:
            # Sans planification d'entretien, envoi simple des mails
            for candidate in candidates:
                try:
                    context = {
                        "instance": candidate,
                        "self": request.user.employee_get
                    }
                    email_body = Template(body).render(Context(context))

                    email = EmailMessage(
                        subject=subject,
                        body=email_body,
                        from_email=request.user.email,
                        to=[candidate.email],
                        attachments=attachments
                    )
                    email.content_subtype = "html"
                    email.send()
                    logger.info(f"Mail envoyé à {candidate.email}")

                except Exception as e:
                    logger.error(f"Erreur pour le candidat {candidate.name}: {str(e)}")
                    messages.error(request, f"Erreur lors du traitement de {candidate.name}")

        messages.success(request, "Opération terminée avec succès")
        return HttpResponse("<script>window.location.reload()</script>")

    except Exception as e:
        logger.error(f"Erreur générale: {str(e)}", exc_info=True)
        messages.error(request, f"Une erreur s'est produite: {str(e)}")
        return HttpResponse(status=500)


@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def candidate_sequence_update(request):
    """
    This method is used to update the sequence of candidate
    """
    sequence_data = json.loads(request.POST["sequenceData"])
    for cand_id, seq in sequence_data.items():
        cand = Candidate.objects.get(id=cand_id)
        cand.sequence = seq
        cand.save()

    return JsonResponse({"message": "Sequence updated", "type": "info"})


@login_required
@recruitment_manager_can_enter(perm="recruitment.change_stage")
def stage_sequence_update(request):
    """
    This method is used to update the sequence of the stages
    """
    sequence_data = json.loads(request.POST["sequence"])
    for stage_id, seq in sequence_data.items():
        stage = Stage.objects.get(id=stage_id)
        stage.sequence = seq
        stage.save()
    return JsonResponse({"type": "success", "message": "Stage sequence updated"})


@login_required
def candidate_select(request):
    """
    This method is used for select all in candidate
    """
    page_number = request.GET.get("page")

    if page_number == "all":
        employees = Candidate.objects.filter(is_active=True)
    else:
        employees = Candidate.objects.all()

    employee_ids = [str(emp.id) for emp in employees]
    total_count = employees.count()

    context = {"employee_ids": employee_ids, "total_count": total_count}

    return JsonResponse(context, safe=False)


@login_required
def candidate_select_filter(request):
    """
    This method is used to select all filtered candidates
    """
    page_number = request.GET.get("page")
    filtered = request.GET.get("filter")
    filters = json.loads(filtered) if filtered else {}

    if page_number == "all":
        candidate_filter = CandidateFilter(filters, queryset=Candidate.objects.all())

        # Get the filtered queryset
        filtered_candidates = candidate_filter.qs

        employee_ids = [str(emp.id) for emp in filtered_candidates]
        total_count = filtered_candidates.count()

        context = {"employee_ids": employee_ids, "total_count": total_count}

        return JsonResponse(context)


@login_required
def create_candidate_rating(request, cand_id):
    """
    This method is used to create rating for the candidate
    Args:
        cand_id : candidate instance id
    """
    cand_id = cand_id
    candidate = Candidate.objects.get(id=cand_id)
    employee_id = request.user.employee_get
    rating = request.POST.get("rating")
    CandidateRating.objects.create(
        candidate_id=candidate, rating=rating, employee_id=employee_id
    )
    return redirect(recruitment_pipeline)


# ///////////////////////////////////////////////
# skill zone
# ///////////////////////////////////////////////


@login_required
@manager_can_enter(perm="recruitment.view_skillzone")
def skill_zone_view(request):
    """
    This method is used to show Skill zone view
    """
    candidates = SkillZoneCandFilter(request.GET).qs.filter(is_active=True)
    skill_groups = group_by_queryset(
        candidates,
        "skill_zone_id",
        request.GET.get("page"),
        "page",
    )

    all_zones = []
    for zone in skill_groups:
        all_zones.append(zone["grouper"])

    skill_zone_filtered = SkillZoneFilter(request.GET).qs.filter(is_active=True)
    all_zone_objects = list(skill_zone_filtered)
    unused_skill_zones = list(set(all_zone_objects) - set(all_zones))

    unused_zones = []
    for zone in unused_skill_zones:
        unused_zones.append(
            {
                "grouper": zone,
                "list": [],
                "dynamic_name": "",
            }
        )
    skill_groups = skill_groups.object_list + unused_zones
    skill_groups = paginator_qry(skill_groups, request.GET.get("page"))
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(SkillZone, data_dict)
    if skill_groups.object_list:
        template = "skill_zone/skill_zone_view.html"
    else:
        template = "skill_zone/empty_skill_zone.html"

    context = {
        "skill_zones": skill_groups,
        "page": request.GET.get("page"),
        "pd": previous_data,
        "f": SkillZoneCandFilter(),
        "filter_dict": data_dict,
    }
    return render(request, template, context=context)


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_skillzone")
def skill_zone_create(request):
    """
    This method is used to create Skill zone.
    """
    form = SkillZoneCreateForm()
    if request.method == "POST":
        form = SkillZoneCreateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Skill Zone created successfully."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "skill_zone/skill_zone_create.html",
        {"form": form},
    )


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.change_skillzone")
def skill_zone_update(request, sz_id):
    """
    This method is used to update Skill zone.
    """
    skill_zone = SkillZone.objects.get(id=sz_id)
    form = SkillZoneCreateForm(instance=skill_zone)
    if request.method == "POST":
        form = SkillZoneCreateForm(request.POST, instance=skill_zone)
        if form.is_valid():
            form.save()
            messages.success(request, _("Skill Zone updated successfully."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(
        request,
        "skill_zone/skill_zone_update.html",
        {"form": form, "sz_id": sz_id},
    )


@login_required
@manager_can_enter(perm="recruitment.delete_skillzone")
def skill_zone_delete(request, sz_id):
    """
    function used to delete Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_id : Skill zone id

    Returns:
    GET : return Skill zone view template
    """
    try:
        skill_zone = SkillZone.find(sz_id)
        if skill_zone:
            skill_zone.delete()
            messages.success(request, _("Skill zone deleted successfully.."))
        else:
            messages.error(request, _("Skill zone not found."))
    except ProtectedError:
        messages.error(request, _("Related entries exists"))
    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.delete_skillzone")
def skill_zone_archive(request, sz_id):
    """
    function used to archive or un-archive Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_id : Skill zone id

    Returns:
    GET : return Skill zone view template
    """
    skill_zone = SkillZone.find(sz_id)
    if skill_zone:
        is_active = skill_zone.is_active
        if is_active == True:
            skill_zone.is_active = False
            skill_zone_candidates = SkillZoneCandidate.objects.filter(
                skill_zone_id=sz_id
            )
            for i in skill_zone_candidates:
                i.is_active = False
                i.save()
            messages.success(request, _("Skill zone archived successfully.."))
        else:
            skill_zone.is_active = True
            skill_zone_candidates = SkillZoneCandidate.objects.filter(
                skill_zone_id=sz_id
            )
            for i in skill_zone_candidates:
                i.is_active = True
                i.save()
            messages.success(request, _("Skill zone unarchived successfully.."))
        skill_zone.save()
    else:
        messages.error(request, _("Skill zone not found."))
    return redirect(skill_zone_view)


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.view_skillzone")
def skill_zone_filter(request):
    """
    This method is used to filter and show Skill zone view.
    """
    template = "skill_zone/skill_zone_list.html"
    if request.GET.get("view") == "card":
        template = "skill_zone/skill_zone_card.html"

    candidates = SkillZoneCandFilter(request.GET).qs
    skill_zone_filtered = SkillZoneFilter(request.GET).qs
    if request.GET.get("is_active") == "false":
        skill_zone_filtered = SkillZoneFilter(request.GET).qs.filter(is_active=False)
        candidates = SkillZoneCandFilter(request.GET).qs.filter(is_active=False)

    else:
        skill_zone_filtered = SkillZoneFilter(request.GET).qs.filter(is_active=True)
        candidates = SkillZoneCandFilter(request.GET).qs.filter(is_active=True)
    skill_groups = group_by_queryset(
        candidates,
        "skill_zone_id",
        request.GET.get("page"),
        "page",
    )
    all_zones = []
    for zone in skill_groups:
        all_zones.append(zone["grouper"])

    all_zone_objects = list(skill_zone_filtered)
    unused_skill_zones = list(set(all_zone_objects) - set(all_zones))

    unused_zones = []
    for zone in unused_skill_zones:
        unused_zones.append(
            {
                "grouper": zone,
                "list": [],
                "dynamic_name": "",
            }
        )
    skill_groups = skill_groups.object_list + unused_zones
    skill_groups = paginator_qry(skill_groups, request.GET.get("page"))
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(SkillZone, data_dict)
    context = {
        "skill_zones": skill_groups,
        "pd": previous_data,
        "filter_dict": data_dict,
    }
    return render(
        request,
        template,
        context,
    )


@login_required
@manager_can_enter(perm="recruitment.view_skillzonecandidate")
def skill_zone_cand_card_view(request, sz_id):
    """
    This method is used to show Skill zone candidates.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone id

    Returns:
    GET : return Skill zone candidate view template
    """
    skill_zone = SkillZone.objects.get(id=sz_id)
    template = "skill_zone_cand/skill_zone_cand_view.html"
    sz_candidates = SkillZoneCandidate.objects.filter(
        skill_zone_id=skill_zone, is_active=True
    )
    context = {
        "sz_candidates": paginator_qry(sz_candidates, request.GET.get("page")),
        "pd": request.GET.urlencode(),
        "sz_id": sz_id,
    }
    return render(request, template, context)


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.add_skillzonecandidate")
def skill_zone_candidate_create(request, sz_id):
    """
    This method is used to add candidates to a Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone id

    Returns:
    GET : return Skill zone candidate create template
    """
    skill_zone = SkillZone.objects.get(id=sz_id)
    template = "skill_zone_cand/skill_zone_cand_form.html"
    form = SkillZoneCandidateForm(initial={"skill_zone_id": skill_zone})
    if request.method == "POST":
        form = SkillZoneCandidateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, _("Candidate added successfully."))
            return HttpResponse("<script>window.location.reload()</script>")

    return render(request, template, {"form": form, "sz_id": sz_id})


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.change_skillzonecandidate")
def skill_zone_cand_edit(request, sz_cand_id):
    """
    This method is used to edit candidates in a Skill zone.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone candidate edit template
    """
    skill_zone_cand = SkillZoneCandidate.objects.filter(id=sz_cand_id).first()
    template = "skill_zone_cand/skill_zone_cand_form.html"
    form = SkillZoneCandidateForm(instance=skill_zone_cand)
    if request.method == "POST":
        form = SkillZoneCandidateForm(request.POST, instance=skill_zone_cand)
        if form.is_valid():
            form.save()
            messages.success(request, _("Candidate edited successfully."))
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, template, {"form": form, "sz_cand_id": sz_cand_id})


@login_required
@manager_can_enter(perm="recruitment.delete_skillzonecandidate")
def skill_zone_cand_delete(request, sz_cand_id):
    """
    function used to delete Skill zone candidate.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone view template
    """

    try:
        SkillZoneCandidate.objects.get(id=sz_cand_id).delete()
        messages.success(request, _("Skill zone deleted successfully.."))
    except SkillZoneCandidate.DoesNotExist:
        messages.error(request, _("Skill zone not found."))
    except ProtectedError:
        messages.error(request, _("Related entries exists"))
    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.view_skillzonecandidate")
def skill_zone_cand_filter(request):
    """
    This method is used to filter the skill zone candidates
    """
    template = "skill_zone_cand/skill_zone_cand_card.html"
    if request.GET.get("view") == "list":
        template = "skill_zone_cand/skill_zone_cand_list.html"

    candidates = SkillZoneCandidate.objects.all()
    candidates_filter = SkillZoneCandFilter(request.GET, queryset=candidates).qs
    previous_data = request.GET.urlencode()
    data_dict = parse_qs(previous_data)
    get_key_instances(SkillZoneCandidate, data_dict)
    context = {
        "candidates": paginator_qry(candidates_filter, request.GET.get("page")),
        "pd": previous_data,
        "filter_dict": data_dict,
        "f": SkillZoneCandFilter(),
    }
    return render(
        request,
        template,
        context,
    )


@login_required
@manager_can_enter(perm="recruitment.delete_skillzonecandidate")
def skill_zone_cand_archive(request, sz_cand_id):
    """
    function used to archive or un-archive Skill zone candidate.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone candidate view template
    """
    try:
        skill_zone_cand = SkillZoneCandidate.objects.get(id=sz_cand_id)
        is_active = skill_zone_cand.is_active
        if is_active == True:
            skill_zone_cand.is_active = False
            messages.success(request, _("Candidate archived successfully.."))

        else:
            skill_zone_cand.is_active = True
            messages.success(request, _("Candidate unarchived successfully.."))

        skill_zone_cand.save()
    except SkillZone.DoesNotExist:
        messages.error(request, _("Candidate not found."))
    return redirect(skill_zone_view)


@login_required
@manager_can_enter(perm="recruitment.delete_skillzonecandidate")
def skill_zone_cand_delete(request, sz_cand_id):
    """
    function used to delete Skill zone candidate.

    Parameters:
    request (HttpRequest): The HTTP request object.
    sz_cand_id : Skill zone candidate id

    Returns:
    GET : return Skill zone view template
    """
    try:
        SkillZoneCandidate.objects.get(id=sz_cand_id).delete()
        messages.success(request, _("Candidate deleted successfully.."))
    except SkillZoneCandidate.DoesNotExist:
        messages.error(request, _("Candidate not found."))
    except ProtectedError:
        messages.error(request, _("Related entries exists"))
    return redirect(skill_zone_view)


@login_required
@hx_request_required
@manager_can_enter(perm="recruitment.change_candidate")
def to_skill_zone(request, cand_id):
    """
    This method is used to Add candidate into skill zone
    Args:
        cand_id : candidate instance id
    """
    candidate = Candidate.objects.get(id=cand_id)
    template = "skill_zone_cand/to_skill_zone_form.html"
    form = ToSkillZoneForm(
        initial={
            "candidate_id": candidate,
            "skill_zone_ids": SkillZoneCandidate.objects.filter(
                candidate_id=candidate
            ).values_list("skill_zone_id", flat=True),
        }
    )
    if request.method == "POST":
        form = ToSkillZoneForm(request.POST)
        if form.is_valid():
            skill_zones = form.cleaned_data["skill_zone_ids"]
            for zone in skill_zones:
                if not SkillZoneCandidate.objects.filter(
                    candidate_id=candidate, skill_zone_id=zone
                ).exists():
                    zone_candidate = SkillZoneCandidate()
                    zone_candidate.candidate_id = candidate
                    zone_candidate.skill_zone_id = zone
                    zone_candidate.reason = form.cleaned_data["reason"]
                    zone_candidate.save()
            messages.success(request, "Candidate Added to skill zone successfully")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, template, {"form": form, "cand_id": cand_id})


@login_required
def update_candidate_rating(request, cand_id):
    """
    This method is used to update the candidate rating
    Args:
        id : candidate rating instance id
    """
    cand_id = cand_id
    candidate = Candidate.objects.get(id=cand_id)
    employee_id = request.user.employee_get
    rating = request.POST.get("rating")
    rate = CandidateRating.objects.get(candidate_id=candidate, employee_id=employee_id)
    rate.rating = int(rating)
    rate.save()
    return redirect(recruitment_pipeline)


def open_recruitments(request):
    """
    This method is used to render the open recruitment page.
    Public users see open positions, authenticated users are redirected to admin.
    """
    # Si l'utilisateur est authentifié et accède à la racine,
    # rediriger vers l'interface d'administration
    if request.user.is_authenticated and request.path == '/': 
        return redirect(request.GET.get('next', '/'))

    # Pour les visiteurs publics, afficher les recrutements ouverts et publiés
    recruitments = Recruitment.default.filter(closed=False, is_published=True)
    context = {
        "recruitments": recruitments,
    }
    response = render(request, "recruitment/open_recruitments.html", context)
    response["X-Frame-Options"] = "ALLOW-FROM *"
    
    return response


def recruitment_details(request, id):
    """
    This method is used to render the recruitment details page
    """
    recruitment = Recruitment.default.get(id=id)
    context = {
        "recruitment": recruitment,
    }
    return render(request, "recruitment/recruitment_details.html", context)


@login_required
@manager_can_enter("recruitment.view_candidate")
def get_mail_log(request):
    """
    This method is used to track mails sent along with the status
    """
    candidate_id = request.GET["candidate_id"]
    candidate = Candidate.objects.get(id=candidate_id)
    tracked_mails = EmailLog.objects.filter(to__icontains=candidate.email).order_by(
        "-created_at"
    )
    return render(request, "candidate/mail_log.html", {"tracked_mails": tracked_mails})


@login_required
@hx_request_required
@permission_required("recruitment.add_recruitmentgeneralsetting")
def candidate_self_tracking(request):
    """
    This method is used to update the recruitment general setting
    """
    settings = RecruitmentGeneralSetting.objects.first()
    settings = settings if settings else RecruitmentGeneralSetting()
    settings.candidate_self_tracking = "candidate_self_tracking" in request.GET.keys()
    settings.save()
    return HttpResponse("success")


@login_required
@hx_request_required
@permission_required("recruitment.add_recruitmentgeneralsetting")
def candidate_self_tracking_rating_option(request):
    """
    This method is used to enable/disable the selt tracking rating field
    """
    settings = RecruitmentGeneralSetting.objects.first()
    settings = settings if settings else RecruitmentGeneralSetting()
    settings.show_overall_rating = "candidate_self_tracking" in request.GET.keys()
    settings.save()
    return HttpResponse("success")


def candidate_self_status_tracking(request):
    """
    This method is accessed by the candidates
    """
    self_tracking_feature = check_candidate_self_tracking(request)[
        "check_candidate_self_tracking"
    ]
    if self_tracking_feature:
        if request.method == "POST":
            email = request.POST["email"]
            phone = request.POST["phone"]
            candidate = Candidate.objects.filter(
                email=email, mobile=phone, is_active=True
            ).first()
            if candidate:
                return render(
                    request, "candidate/self_tracking.html", {"candidate": candidate}
                )
            messages.info(request, "No matching record")
        return render(request, "candidate/self_login.html")
    return render(request, "404.html")


@login_required
@hx_request_required
@permission_required("recruitment.add_rejectreason")
def create_reject_reason(request):
    """
    This method is used to create/update the reject reasons
    """
    instance_id = eval(str(request.GET.get("instance_id")))
    instance = None
    if instance_id:
        instance = RejectReason.objects.get(id=instance_id)
    form = RejectReasonForm(instance=instance)
    if request.method == "POST":
        form = RejectReasonForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Reject reason saved")
            return HttpResponse("<script>window.location.reload()</script>")
    return render(request, "settings/reject_reason_form.html", {"form": form})


@login_required
@permission_required("recruitment.view_recruitment")
def self_tracking_feature(request):
    """
    Recruitment optional feature for candidate self tracking
    """
    return render(request, "recruitment/settings/settings.html")


@login_required
@permission_required("recruitment.delete_rejectreason")
def delete_reject_reason(request):
    """
    This method is used to delete the reject reasons
    """
    ids = request.GET.getlist("ids")
    reasons = RejectReason.objects.filter(id__in=ids)
    for reason in reasons:
        reasons.delete()
        messages.success(request, f"{reason.title} is deleted.")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


def extract_text_with_font_info(pdf):
    """
    This method is used to extract text from the pdf and create a list of dictionaries containing details about the extracted text.
    Args:
        pdf (): pdf file to extract text from
    """
    pdf_bytes = pdf.read()
    pdf_doc = io.BytesIO(pdf_bytes)
    doc = fitz.open("pdf", pdf_doc)
    text_info = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            try:
                for line in block["lines"]:
                    for span in line["spans"]:
                        text_info.append(
                            {
                                "text": span["text"],
                                "font_size": span["size"],
                                "capitalization": sum(
                                    1 for c in span["text"] if c.isupper()
                                )
                                / len(span["text"]),
                            }
                        )
            except:
                pass

    return text_info


def rank_text(text_info):
    """
    This method is used to rank the text

    Args:
        text_info: List of dictionary containing the details

    Returns:
        Returns a sorted list
    """
    ranked_text = sorted(
        text_info, key=lambda x: (x["font_size"], x["capitalization"]), reverse=True
    )
    return ranked_text


def dob_matching(dob):
    """
    This method is used to change the date format to YYYY-MM-DD

    Args:
        dob: Date

    Returns:
        Return date in YYYY-MM-DD
    """
    date_formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y.%m.%d",
        "%d.%m.%Y",
    ]

    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(dob, fmt)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return dob


def extract_info(pdf):
    """
    This method creates the contact information dictionary from the provided pdf file
    Args:
        pdf_file: pdf file
    """

    text_info = extract_text_with_font_info(pdf)
    ranked_text = rank_text(text_info)

    phone_pattern = re.compile(r"\b\+?\d{1,2}\s?\d{9,10}\b")
    dob_pattern = re.compile(
        r"\b(?:\d{1,2}|\d{4})[-/.,]\d{1,2}[-/.,](?:\d{1,2}|\d{4})\b"
    )
    email_pattern = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    zip_code_pattern = re.compile(r"\b\d{5,6}(?:-\d{4})?\b")

    extracted_info = {
        "full_name": "",
        "address": "",
        "country": "Cameroon",
        "state": "",
        "phone_number": "",
        "dob": "",
        "email_id": "",
        "zip": "",
    }

    name_candidates = [
        item["text"]
        for item in ranked_text
        if item["font_size"] == max(item["font_size"] for item in ranked_text)
    ]

    if name_candidates:
        extracted_info["full_name"] = " ".join(name_candidates)

    for item in ranked_text:
        text = item["text"]

        if not text:
            continue

        if not extracted_info["phone_number"]:
            phone_match = phone_pattern.search(text)
            if phone_match:
                extracted_info["phone_number"] = phone_match.group()

        if not extracted_info["dob"]:
            dob_match = dob_pattern.search(text)
            if dob_match:
                extracted_info["dob"] = dob_matching(dob_match.group())

        if not extracted_info["zip"]:
            zip_match = zip_code_pattern.search(text)
            if zip_match:
                extracted_info["zip"] = zip_match.group()

        if not extracted_info["email_id"]:
            email_match = email_pattern.search(text)
            if email_match:
                extracted_info["email_id"] = email_match.group()

        if "address" in text.lower() and not extracted_info["address"]:
            extracted_info["address"] = text.replace("Address:", "").strip()

        for item in text.split(" "):
            if item.capitalize() in country_arr:
                extracted_info["country"] = item

        for item in text.split(" "):
            if item.capitalize() in states:
                extracted_info["state"] = item

    return extracted_info


def resume_completion(request):
    """
    This function is returns the data for completing the candidate creation form
    """
    resume_file = request.FILES["resume"]
    contact_info = extract_info(resume_file)

    return JsonResponse(contact_info)


def check_vaccancy(request):
    """
    check vaccancy of recruitment
    """
    stage_id = request.GET.get("stageId")
    stage = Stage.objects.get(id=stage_id)
    message = "No message"
    if stage and stage.recruitment_id.is_vacancy_filled():
        message = _("Vaccancy is filled")
    return JsonResponse({"message": message})


@login_required
def skills_view(request):
    """
    This function is used to view skills page in settings
    """
    skills = Skill.objects.all().order_by('title')
    paginator = Paginator(skills, 50)  # 10 skills par page
    page = request.GET.get('page')
    skills = paginator.get_page(page)
    
    return render(request, "settings/skills/skills_view.html", {
        "skills": skills
    })


@login_required
def create_skills(request):
    """
    This method is used to create the skills
    """
    instance_id = eval(str(request.GET.get("instance_id")))
    dynamic = request.GET.get("dynamic")
    hx_vals = request.GET.get("data")
    instance = None
    if instance_id:
        instance = Skill.objects.get(id=instance_id)
    form = SkillsForm(instance=instance)
    if request.method == "POST":
        form = SkillsForm(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Skill created successfully")

            if request.GET.get("dynamic") == "True":
                

                url = reverse("recruitment-create")
                instance = Skill.objects.all().last()
                mutable_get = request.GET.copy()
                skills = mutable_get.getlist("skills")
                skills.remove("create")
                skills.append(str(instance.id))
                mutable_get["skills"] = skills[-1]
                skills.pop()
                data = mutable_get.urlencode()
                try:
                    for item in skills:
                        data += f"&skills={item}"
                except:
                    pass
                return redirect(f"{url}?{data}")

            return HttpResponse("<script>window.location.reload()</script>")

    context = {
        "form": form,
        "dynamic": dynamic,
        "hx_vals": hx_vals,
    }

    return render(request, "settings/skills/skills_form.html", context=context)

@login_required
@permission_required('recruitment.add_skill')  # Ajout permission
def import_skills(request):
    print("Vue import_skills appelée") # Debug
    
    if request.method == 'POST':
        print("POST reçu") # Debug
        file = request.FILES.get('file')
        
        if not file:
            messages.error(request, "Aucun fichier n'a été téléchargé")
            return redirect('skills-view')
            
        print(f"Fichier reçu: {file.name}") # Debug
        
        try:
            df = pd.read_excel(file)
            print(f"Données Excel: {df.head()}") # Debug
            print(f"Colonnes: {df.columns}") # Debug
            
            if 'title' not in df.columns:
                messages.error(request, "Le fichier doit contenir une colonne 'title'")
                return redirect('skills-view')

            count = 0
            for index, row in df.iterrows():
                title = str(row['title']).strip()
                if title:
                    skill, created = Skill.objects.get_or_create(title=title)
                    if created:
                        count += 1
                        print(f"Skill créé: {title}") # Debug

            messages.success(request, f"{count} nouveaux skills ont été ajoutés")
        except Exception as e:
            print(f"Erreur: {str(e)}") # Debug
            messages.error(request, f"Erreur lors de l'import: {str(e)}")
            
        return redirect('skills-view')

    return render(request, 'settings/skills/import_skills.html', {'form': SkillImportForm()})

@login_required
@permission_required("recruitment.delete_rejectreason")
def delete_skills(request):
    """
    This method is used to delete the skills
    """
    ids = request.GET.getlist("ids")
    skills = Skill.objects.filter(id__in=ids)
    for skill in skills:
        skill.delete()
        messages.success(request, f"{skill.title} is deleted.")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))


@login_required
@hx_request_required
@manager_can_enter("recruitment.add_candidate")
def view_bulk_resumes(request):
    """
    This function returns the bulk_resume.html page to the modal
    """
    rec_id = eval(str(request.GET.get("rec_id")))
    resumes = Resume.objects.filter(recruitment_id=rec_id)

    return render(
        request, "pipeline/bulk_resume.html", {"resumes": resumes, "rec_id": rec_id}
    )


@login_required
@hx_request_required
@manager_can_enter("recruitment.add_candidate")
def add_bulk_resumes(request):
    """
    This function is used to create bulk resume
    """
    rec_id = eval(str(request.GET.get("rec_id")))
    recruitment = Recruitment.objects.get(id=rec_id)
    if request.method == "POST":
        files = request.FILES.getlist("files")
        for file in files:
            Resume.objects.create(
                file=file,
                recruitment_id=recruitment,
            )

        url = reverse("view-bulk-resume")
        query_params = f"?rec_id={rec_id}"

        return redirect(f"{url}{query_params}")


@login_required
@hx_request_required
@manager_can_enter("recruitment.add_candidate")
def delete_resume_file(request):
    """
    Used to delete resume
    """
    ids = request.GET.getlist("ids")
    rec_id = request.GET.get("rec_id")
    Resume.objects.filter(id__in=ids).delete()

    url = reverse("view-bulk-resume")
    query_params = f"?rec_id={rec_id}"

    return redirect(f"{url}{query_params}")


@login_required
@manager_can_enter("recruitment.change_candidate")
def shortlist_candidates(request, stage_id):
    stage = get_object_or_404(Stage, id=stage_id)
    candidates = Candidate.objects.filter(stage_id=stage)
    
    recruitment = stage.recruitment_id
    skills = list(recruitment.skills.values_list('title', flat=True))

    for candidate in candidates:
        if candidate.score is None:  # N'évaluez que les candidats qui n'ont pas encore de score
            score = 0
            if candidate.resume:
                try:
                    words = extract_words_from_pdf(candidate.resume)
                    matching_skills_count = sum(skill.lower() in words for skill in skills)
                    score = int(matching_skills_count) if skills else 0

                except Exception as e:
                    messages.error(request, _(f"Erreur lors de l'évaluation du CV de {candidate.name}: {str(e)}"))

            candidate.score = score
            candidate.save()

    messages.success(request, _("Les candidats ont été évalués et classés avec succès."))
    return redirect('pipeline')

    # cache_key = request.session.session_key + "pipeline"
    # CACHE.delete(cache_key)

def extract_words_from_pdf(pdf_file):
    """
    Extract words from PDF stored locally/Azure Blob
    """
    try:
        # Lire le contenu du PDF directement
        if hasattr(pdf_file, 'read'):
            pdf_bytes = pdf_file.read()
        else:
            pdf_bytes = pdf_file.file.read()
            
        pdf_io = io.BytesIO(pdf_bytes)
        pdf_document = fitz.open(stream=pdf_io, filetype="pdf")
        
        words = []
        for page in pdf_document:
            text = page.get_text()
            words.extend(re.findall(r"\b\w+\b", text.lower()))
            
        pdf_document.close()
        return words
        
    except Exception as e:
        print(f"PDF Error: {str(e)}")
        return []


@login_required
@hx_request_required
@manager_can_enter("recruitment.add_candidate")
def matching_resumes(request, rec_id):
    """
    This function returns the matching resume table after sorting the resumes according to their scores

    Args:
        rec_id: Recruitment ID

    """
    recruitment = Recruitment.objects.filter(id=rec_id).first()
    skills = recruitment.skills.values_list("title", flat=True)
    resumes = recruitment.resume.all()
    is_candidate = resumes.filter(is_candidate=True)
    is_candidate_ids = set(is_candidate.values_list("id", flat=True))

    resume_ranks = []
    for resume in resumes:
        words = extract_words_from_pdf(resume.file)
        matching_skills_count = sum(skill.lower() in words for skill in skills)

        item = {"resume": resume, "matching_skills_count": matching_skills_count}
        if not len(words):
            item["image_pdf"] = True

        resume_ranks.append(item)

    candidate_resumes = [
        rank for rank in resume_ranks if rank["resume"].id in is_candidate_ids
    ]
    non_candidate_resumes = [
        rank for rank in resume_ranks if rank["resume"].id not in is_candidate_ids
    ]

    non_candidate_resumes = sorted(
        non_candidate_resumes, key=lambda x: x["matching_skills_count"], reverse=True
    )
    candidate_resumes = sorted(
        candidate_resumes, key=lambda x: x["matching_skills_count"], reverse=True
    )

    ranked_resumes = non_candidate_resumes + candidate_resumes

    return render(
        request,
        "pipeline/matching_resumes.html",
        {
            "matched_resumes": ranked_resumes,
            "rec_id": rec_id,
        },
    )


@login_required
@manager_can_enter("recruitment.add_candidate")
def matching_resume_completion(request):
    """
    This function is returns the data for completing the candidate creation form
    """
    resume_id = request.GET.get("resume_id")
    resume_obj = get_object_or_404(Resume, id=resume_id)
    resume_file = resume_obj.file
    contact_info = extract_info(resume_file)

    return JsonResponse(contact_info)


@login_required
@permission_required("recruitment.view_rejectreason")
def candidate_reject_reasons(request):
    """
    This method is used to view all the reject reasons
    """
    reject_reasons = RejectReason.objects.all()
    return render(
        request, "settings/reject_reasons.html", {"reject_reasons": reject_reasons}
    )


@login_required
def hired_candidate_chart(request):
    """
    function used to show hired candidates in all recruitments.

    Parameters:
    request (HttpRequest): The HTTP request object.

    Returns:
    GET : return Json response labels, data, background_color, border_color.
    """
    labels = []
    data = []
    background_color = []
    border_color = []
    recruitments = Recruitment.objects.filter(closed=False, is_active=True)
    for recruitment in recruitments:
        red = random.randint(0, 255)
        green = random.randint(0, 255)
        blue = random.randint(0, 255)
        background_color.append(f"rgba({red}, {green}, {blue}, 0.2")
        border_color.append(f"rgb({red}, {green}, {blue})")
        labels.append(f"{recruitment}")
        data.append(recruitment.candidate.filter(hired=True).count())
    return JsonResponse(
        {
            "labels": labels,
            "data": data,
            "background_color": background_color,
            "border_color": border_color,
            "message": _("No data Found..."),
        },
        safe=False,
    )

def oauth2callback(request):
    """
    Vue pour gérer le callback OAuth2 de Google.
    Délègue le traitement à la fonction handle_oauth2callback.
    """
    return handle_oauth2callback(request)

@login_required
def get_interviews_json(request):
    """Retourne les interviews au format JSON pour FullCalendar"""
    logger.info("Starting get_interviews_json view")
    try:
        # Débogage des paramètres reçus
        logger.info(f"Request parameters: {request.GET}")
        
        if request.user.has_perm("view_interviewschedule"):
            interviews = InterviewSchedule.objects.all()
        else:
            interviews = InterviewSchedule.objects.filter(
                Q(employee_id=request.user.employee_get.id) |
                Q(candidate_id__recruitment_id__recruitment_managers=request.user.employee_get)
            )
        
        # Débogage du nombre d'interviews trouvés
        logger.info(f"Found {interviews.count()} interviews")

        interviews = interviews.select_related(
            'candidate_id',
            'candidate_id__job_position_id'
        )

        events = []
        for interview in interviews:
            try:
                start_datetime = datetime.combine(
                    interview.interview_date,
                    interview.interview_time
                )
                end_datetime = start_datetime + timedelta(minutes=interview.duration or 60)

                # Créons un événement avec seulement les données essentielles
                event = {
                    'id': str(interview.id),  # Convertir en string pour éviter les problèmes de sérialisation
                    'title': str(interview.candidate_id.name),  # S'assurer que c'est une chaîne
                    'start': start_datetime.isoformat(),
                    'end': end_datetime.isoformat(),
                    'backgroundColor': '#4CAF50' if interview.completed else '#2196F3',
                }
                events.append(event)
                logger.info(f"Added event: {event}")
                
            except Exception as e:
                logger.error(f"Error processing interview {interview.id}: {str(e)}")
                continue

        # Débogage de la réponse finale
        logger.info(f"Returning {len(events)} events")
        
        response_data = {'success': True, 'events': events}
        return JsonResponse(response_data, safe=False)
        
    except Exception as e:
        logger.error(f"Error in get_interviews_json: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@login_required
def interview_detail(request, interview_id):
    """Vue pour afficher les détails d'une interview"""
    try:
        interview = get_object_or_404(
            InterviewSchedule.objects.select_related(
                'candidate_id',
                'candidate_id__job_position_id'
            ),
            id=interview_id
        )

        # Vérifier les permissions
        has_permission = (
            request.user.has_perm("recruitment.view_interviewschedule") or
            request.user.employee_get in interview.employee_id.all() or
            request.user.employee_get in interview.candidate_id.recruitment_id.recruitment_managers.all()
        )

        if not has_permission:
            raise PermissionDenied

        # Récupérer les attendees
        try:
            attendees_list = json.loads(interview.attendees) if interview.attendees else []
        except json.JSONDecodeError:
            attendees_list = []

        context = {
            'interview': interview,
            'attendees_list': attendees_list,
            'now': timezone.now(),
        }

        return render(request, 'candidate/interview_detail.html', context)
        
    except Exception as e:
        logger.error(f"Error in interview_detail: {str(e)}")
        return JsonResponse(
            {"error": "An error occurred while loading the interview details"},
            status=500
        )

@login_required
@require_http_methods(["POST"])
def update_interview_datetime(request):
    """Met à jour la date/heure d'une interview (drag & drop calendar)"""
    try:
        data = json.loads(request.body)
        interview = get_object_or_404(InterviewSchedule, id=data['interview_id'])
        
        # Vérifier les permissions
        if not request.user.employee_get in interview.candidate_id.recruitment_id.recruitment_managers.all():
            raise PermissionDenied
            
        start = parse_datetime(data['start'])
        end = parse_datetime(data['end'])
        
        interview.interview_date = start.date()
        interview.interview_time = start.time()
        interview.duration = int((end - start).total_seconds() / 60)
        interview.save()
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    
@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def start_ai_analysis(request, stage_id):
   try:
       stage = get_object_or_404(Stage, id=stage_id)
       
       # Filtrer uniquement les candidats qui n'ont pas été analysés ou qui ont échoué
       candidates = Candidate.objects.filter(
           stage_id=stage,
           is_active=True
       ).filter(
           Q(ai_analysis_status='pending') |
           Q(ai_analysis_status='failed') |
           Q(ai_analysis_status=None)  # Pour les anciens candidats
       )

       if not candidates.exists():
           return JsonResponse({
               'status': 'info',
               'message': _("Tous les candidats ont déjà été analysés"),
               'count': 0
           })

       # Compteur pour le nombre de candidats à analyser
       count = 0
       
       # Mise à jour du statut uniquement pour les nouveaux candidats
       for candidate in candidates:
           candidate.ai_analysis_status = 'in_progress'
           candidate.save(update_fields=['ai_analysis_status'])
           _event_loop.run_until_complete(cv_analysis_manager.add_to_queue(candidate))
           count += 1

       messages.success(
           request, 
           _("Analyse démarrée pour {} candidat(s)").format(count)
       )
       
       return JsonResponse({
           'status': 'success',
           'message': _("Analyse démarrée pour {} candidat(s)").format(count),
           'count': count
       })

   except Exception as e:
       logger.error(f"ERREUR DÉMARRAGE ANALYSE: {str(e)}", exc_info=True)
       return JsonResponse({
           'status': 'error', 
           'message': str(e)
       }, status=500)
   
@login_required
@manager_can_enter(perm="recruitment.view_candidate")
def get_analysis_details(request, candidate_id):
    try:
        candidate = get_object_or_404(Candidate, id=candidate_id)
        if not candidate.ai_analysis_details:
            return JsonResponse({'status': 'error', 'message': _("Aucune analyse disponible")})
            
        return render(request, 'pipeline/analysis_details_modal.html', {
            'candidate': candidate,
            'analysis': candidate.ai_analysis_details
        })
        
    except Exception as e:
        logger.error(f"ERREUR DÉTAILS: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error', 'message': _("Erreur de chargement")}, status=500)

@login_required
@manager_can_enter(perm="recruitment.view_candidate")
def get_analysis_details(request, candidate_id):
    """Get AI analysis details for a candidate"""
    try:
        candidate = get_object_or_404(Candidate, id=candidate_id)
        if not candidate.ai_analysis_details:
            return JsonResponse({
                'status': 'error',
                'message': _("No analysis available")
            })

        return render(request, 'pipeline/analysis_details_modal.html', {
            'candidate': candidate,
            'analysis': candidate.ai_analysis_details
        })
    except Exception as e:
        logger.error(f"Error fetching analysis details: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _("Failed to fetch analysis details")
        }, status=500)

@login_required
@manager_can_enter(perm="recruitment.change_candidate")
def retry_analysis(request, candidate_id):
    try:
        candidate = get_object_or_404(Candidate, id=candidate_id)
        
        # Créer une nouvelle boucle d'événements asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Ajouter le candidat à la file d'attente
        loop.run_until_complete(cv_analysis_manager.add_to_queue(candidate))
        
        loop.close()
        
        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.error(f"Error retrying analysis: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': _("Failed to retry analysis")
        }, status=500)

@login_required
@manager_can_enter(perm="recruitment.view_candidate")
def get_stage_analysis_status(request, stage_id):
    """Get analysis status for all candidates in a stage"""
    try:
        stage = Stage.objects.get(id=stage_id)
        candidates = stage.candidate_set.all()
        
        stats = {
            'completed': candidates.filter(ai_analysis_status='completed').count(),
            'in_progress': candidates.filter(ai_analysis_status='in_progress').count(),
            'pending': candidates.filter(ai_analysis_status='pending').count(),
            'candidates': []
        }
        
        for candidate in candidates:
            stats['candidates'].append({
                'id': candidate.id,
                'status': candidate.ai_analysis_status,
                'score': candidate.ai_score
            })
            
        return JsonResponse({'stats': stats})
    except Exception as e:
        logger.error(f"Error getting analysis status: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)
    

from django.utils import translation

def set_public_language(request, language_code):
    """Change la langue pour les pages publiques"""
    # Sauvegarder la langue dans la session
    request.session['public_language'] = language_code
    translation.activate(language_code)
    
    # Rediriger vers la page précédente
    next_url = request.GET.get('next', '/')
    return redirect(next_url)


@login_required
@permission_required('recruitment.view_aiconfiguration')
def ai_configuration_view(request):
    """
    Vue pour afficher toutes les configurations IA
    """
    configurations = AIConfiguration.objects.filter(is_active=True).order_by('-is_default', 'name')
    
    if configurations.exists():
        template = "recruitment/ai_config/ai_config_view.html"
    else:
        template = "recruitment/ai_config/ai_config_empty.html"
    
    return render(request, template, {
        'configurations': configurations
    })


@login_required
@permission_required('recruitment.add_aiconfiguration') 
@hx_request_required
def ai_configuration_create(request):
    """
    Vue pour créer une nouvelle configuration IA
    """
    form = AIConfigurationForm()
    
    if request.method == 'POST':
        form = AIConfigurationForm(request.POST)
        if form.is_valid():
            config = form.save()
            messages.success(request, _("Configuration IA créée avec succès"))
            return HttpResponse("<script>window.location.reload()</script>")
    
    return render(request, 'recruitment/ai_config/ai_config_form.html', {
        'form': form,
        'title': _("Créer une configuration IA")
    })


@login_required
@permission_required('recruitment.change_aiconfiguration')
@hx_request_required  
def ai_configuration_update(request, config_id):
    """
    Vue pour modifier une configuration IA
    """
    config = get_object_or_404(AIConfiguration, id=config_id)
    form = AIConfigurationForm(instance=config)
    
    if request.method == 'POST':
        form = AIConfigurationForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, _("Configuration IA mise à jour avec succès"))
            return HttpResponse("<script>window.location.reload()</script>")
    
    return render(request, 'recruitment/ai_config/ai_config_form.html', {
        'form': form,
        'config': config,
        'title': _("Modifier la configuration IA")
    })


@login_required
@permission_required('recruitment.delete_aiconfiguration')
def ai_configuration_delete(request, config_id):
    """
    Vue pour supprimer une configuration IA
    """
    try:
        config = AIConfiguration.objects.get(id=config_id)
        if config.is_default:
            messages.error(request, _("Impossible de supprimer la configuration par défaut"))
        else:
            config.delete()
            messages.success(request, _("Configuration IA supprimée avec succès"))
    except AIConfiguration.DoesNotExist:
        messages.error(request, _("Configuration IA introuvable"))
    except Exception as e:
        messages.error(request, _("Erreur lors de la suppression: {}").format(str(e)))
    
    return redirect('ai-configuration-view')


@login_required
@permission_required('recruitment.change_aiconfiguration')
@hx_request_required
def ai_configuration_test(request, config_id):
    """
    Vue pour tester une configuration IA avec Together AI
    """
    config = get_object_or_404(AIConfiguration, id=config_id)
    form = AIConfigurationTestForm()
    test_result = None
    
    if request.method == 'POST':
        form = AIConfigurationTestForm(request.POST)
        if form.is_valid():
            try:
                # Import Together AI
                from together import Together
                import os
                import json
                
                # Configuration de la clé API
                os.environ['TOGETHER_API_KEY'] = config.api_key
                
                # Test de la configuration Together AI
                client = Together()
                
                test_text = form.cleaned_data['test_text']
                job_description = form.cleaned_data['job_description']
                
                # Formatage du prompt
                formatted_prompt = config.analysis_prompt.format(job_description)
                
                # Appel de test
                response = client.chat.completions.create(
                    model=config.model_name,
                    messages=[
                        {"role": "system", "content": formatted_prompt},
                        {"role": "user", "content": test_text}
                    ],
                    max_tokens=config.max_tokens,
                    temperature=config.temperature
                )
                
                raw_response = response.choices[0].message.content.strip()
                
                # Tentative d'extraction du JSON
                try:
                    json_start = raw_response.find('{')
                    json_end = raw_response.rfind('}') + 1
                    
                    if json_start >= 0 and json_end > json_start:
                        json_str = raw_response[json_start:json_end]
                        response_data = json.loads(json_str)
                        
                        test_result = {
                            'success': True,
                            'response': response_data,
                            'raw_response': raw_response
                        }
                    else:
                        test_result = {
                            'success': False,
                            'error': 'JSON non trouvé dans la réponse',
                            'raw_response': raw_response
                        }
                except json.JSONDecodeError as e:
                    test_result = {
                        'success': False,
                        'error': f'Erreur JSON: {str(e)}',
                        'raw_response': raw_response
                    }
                    
            except Exception as e:
                test_result = {
                    'success': False,
                    'error': f'Erreur Together AI: {str(e)}'
                }
    
    return render(request, 'recruitment/ai_config/ai_config_test.html', {
        'form': form,
        'config': config,
        'test_result': test_result
    })


@login_required
@require_http_methods(["POST"])
def ai_configuration_toggle_default(request, config_id):
    """
    Vue pour définir une configuration comme par défaut
    """
    try:
        config = AIConfiguration.objects.get(id=config_id)
        
        # Retirer le flag par défaut de toutes les autres configs
        AIConfiguration.objects.exclude(id=config_id).update(is_default=False)
        
        # Définir cette config comme par défaut
        config.is_default = True
        config.save()
        
        messages.success(request, _("Configuration définie comme par défaut"))
        
    except AIConfiguration.DoesNotExist:
        messages.error(request, _("Configuration introuvable"))
    except Exception as e:
        messages.error(request, _("Erreur: {}").format(str(e)))
    
    return JsonResponse({'status': 'success' if not messages.get_messages(request) else 'error'})

@login_required
@permission_required('recruitment.view_privacypolicy')
def privacy_policy_view(request):
    """
    Vue pour afficher toutes les politiques de confidentialité
    """
    policies = PrivacyPolicy.objects.filter(is_active=True).order_by('-is_default', 'name')
    
    if policies.exists():
        template = "recruitment/privacy_policy/privacy_policy_view.html"
    else:
        template = "recruitment/privacy_policy/privacy_policy_empty.html"
    
    return render(request, template, {
        'policies': policies
    })


@login_required
@permission_required('recruitment.add_privacypolicy')
@hx_request_required
def privacy_policy_create(request):
    """
    Vue pour créer une nouvelle politique de confidentialité
    """
    form = PrivacyPolicyForm()
    
    if request.method == 'POST':
        form = PrivacyPolicyForm(request.POST, request.FILES)
        if form.is_valid():
            policy = form.save()
            messages.success(request, _("Politique de confidentialité créée avec succès"))
            return HttpResponse("<script>window.location.reload()</script>")
    
    return render(request, 'recruitment/privacy_policy/privacy_policy_form.html', {
        'form': form,
        'title': _("Créer une politique de confidentialité")
    })


@login_required
@permission_required('recruitment.change_privacypolicy')
@hx_request_required
def privacy_policy_update(request, policy_id):
    """
    Vue pour modifier une politique de confidentialité
    """
    policy = get_object_or_404(PrivacyPolicy, id=policy_id)
    form = PrivacyPolicyForm(instance=policy)
    
    if request.method == 'POST':
        form = PrivacyPolicyForm(request.POST, request.FILES, instance=policy)
        if form.is_valid():
            form.save()
            messages.success(request, _("Politique de confidentialité mise à jour avec succès"))
            return HttpResponse("<script>window.location.reload()</script>")
    
    return render(request, 'recruitment/privacy_policy/privacy_policy_form.html', {
        'form': form,
        'policy': policy,
        'title': _("Modifier la politique de confidentialité")
    })


@login_required
@permission_required('recruitment.delete_privacypolicy')
def privacy_policy_delete(request, policy_id):
    """
    Vue pour supprimer une politique de confidentialité
    """
    try:
        policy = PrivacyPolicy.objects.get(id=policy_id)
        if policy.is_default:
            messages.error(request, _("Impossible de supprimer la politique par défaut"))
        else:
            policy.delete()
            messages.success(request, _("Politique de confidentialité supprimée avec succès"))
    except PrivacyPolicy.DoesNotExist:
        messages.error(request, _("Politique de confidentialité introuvable"))
    except Exception as e:
        messages.error(request, _("Erreur lors de la suppression: {}").format(str(e)))
    
    return redirect('privacy-policy-view')


@login_required
@require_http_methods(["POST"])
def privacy_policy_toggle_default(request, policy_id):
    """
    Vue pour définir une politique comme par défaut
    """
    try:
        policy = PrivacyPolicy.objects.get(id=policy_id)
        
        # Retirer le flag par défaut de toutes les autres politiques
        PrivacyPolicy.objects.exclude(id=policy_id).update(is_default=False)
        
        # Définir cette politique comme par défaut
        policy.is_default = True
        policy.save()
        
        messages.success(request, _("Politique définie comme par défaut"))
        
    except PrivacyPolicy.DoesNotExist:
        messages.error(request, _("Politique introuvable"))
    except Exception as e:
        messages.error(request, _("Erreur: {}").format(str(e)))
    
    return redirect('privacy-policy-view')


def get_privacy_policy_content(request, recruitment_id):
    """
    Vue AJAX pour récupérer le contenu de la politique de confidentialité
    """
    try:
        recruitment = Recruitment.objects.get(id=recruitment_id)
        company = recruitment.company_id
        
        # Récupérer la politique appropriée
        policy = PrivacyPolicy.get_policy_for_company(company)
        
        if not policy:
            return JsonResponse({
                'status': 'error',
                'message': _("Aucune politique de confidentialité configurée")
            }, status=404)
        
        response_data = {
            'status': 'success',
            'policy_id': policy.id,
            'name': policy.name,
            'content_type': policy.content_type
        }
        
        if policy.content_type == 'text':
            response_data['content'] = policy.text_content
        else:  # PDF
            response_data['pdf_url'] = policy.pdf_file.url
        
        return JsonResponse(response_data)
        
    except Recruitment.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _("Recrutement introuvable")
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de la politique: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@permission_required("recruitment.add_skillzonecandidate")
@require_http_methods(["POST"])
def api_classify_candidate(request, candidate_id):
    """
    API pour classifier manuellement un candidat dans les zones de compétences
    """
    try:
        candidate = Candidate.objects.get(id=candidate_id)
        
        # Lancer la classification asynchrone
        classifier = get_skillzone_classifier()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            classifier.classify_candidate(candidate, source_tag='manual')
        )
        loop.close()
        
        if "error" in result:
            return JsonResponse({
                'status': 'error',
                'message': result['error']
            }, status=500)
        
        return JsonResponse({
            'status': 'success',
            'message': _("Candidat classifié avec succès"),
            'classifications': result.get('classifications', []),
            'new_zone_created': result.get('new_zone_created'),
            'extracted_skills': result.get('extracted_skills', [])
        })
        
    except Candidate.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _("Candidat introuvable")
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur classification API: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@permission_required("recruitment.change_skillzonecandidate")
@require_http_methods(["POST"])
def api_reclassify_candidate(request, sz_cand_id):
    """
    API pour reclassifier un candidat déjà dans une zone
    """
    try:
        sz_candidate = SkillZoneCandidate.objects.get(id=sz_cand_id)
        candidate = sz_candidate.candidate_id
        
        # Supprimer l'ancienne classification
        sz_candidate.delete()
        
        # Relancer la classification
        classifier = get_skillzone_classifier()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            classifier.classify_candidate(candidate, source_tag='manual')
        )
        loop.close()
        
        if "error" in result:
            return JsonResponse({
                'status': 'error',
                'message': result['error']
            }, status=500)
        
        return JsonResponse({
            'status': 'success',
            'message': _("Candidat reclassifié avec succès"),
            'classifications': result.get('classifications', [])
        })
        
    except SkillZoneCandidate.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _("Classification introuvable")
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur reclassification API: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@permission_required("recruitment.view_skillzone")
def api_skillzone_stats(request, sz_id):
    """
    API pour obtenir les statistiques d'une zone ou globales
    """
    try:
        company_id = request.user.employee_get.company_id
        
        if sz_id == 0 or request.path.endswith('/all/'):
            # Statistiques globales
            zones = SkillZone.objects.filter(
                company_id=company_id,
                is_active=True
            )
            
            total_candidates = SkillZoneCandidate.objects.filter(
                skill_zone_id__company_id=company_id,
                is_active=True
            ).count()
            
            auto_classified = SkillZoneCandidate.objects.filter(
                skill_zone_id__company_id=company_id,
                is_active=True,
                auto_classified=True
            ).count()
            
            avg_confidence = SkillZoneCandidate.objects.filter(
                skill_zone_id__company_id=company_id,
                is_active=True,
                confidence_score__isnull=False
            ).aggregate(avg=Avg('confidence_score'))['avg']
            
            stats = {
                'total_zones': zones.count(),
                'auto_generated_zones': zones.filter(auto_generated=True).count(),
                'total_candidates': total_candidates,
                'auto_classified': auto_classified,
                'manual_classified': total_candidates - auto_classified,
                'avg_confidence': round(avg_confidence * 100, 1) if avg_confidence else 0,
                'zones_breakdown': []
            }
            
            # Top 5 zones par nombre de candidats
            top_zones = zones.annotate(
                candidate_count=Count('skillzonecandidate_set', 
                                    filter=Q(skillzonecandidate_set__is_active=True))
            ).order_by('-candidate_count')[:5]
            
            for zone in top_zones:
                stats['zones_breakdown'].append({
                    'id': zone.id,
                    'name': zone.title,
                    'candidate_count': zone.candidate_count,
                    'is_auto': zone.auto_generated
                })
            
        elif request.path.endswith('/count/'):
            # Juste le compteur total
            total_candidates = SkillZoneCandidate.objects.filter(
                skill_zone_id__company_id=company_id,
                is_active=True
            ).count()
            
            return JsonResponse({'total_candidates': total_candidates})
            
        else:
            # Statistiques d'une zone spécifique
            zone = SkillZone.objects.get(id=sz_id, company_id=company_id)
            
            candidates = SkillZoneCandidate.objects.filter(
                skill_zone_id=zone,
                is_active=True
            )
            
            stats = {
                'zone_id': zone.id,
                'zone_name': zone.title,
                'is_auto_generated': zone.auto_generated,
                'total_candidates': candidates.count(),
                'auto_classified': candidates.filter(auto_classified=True).count(),
                'avg_confidence': 0,
                'confidence_distribution': {
                    'high': 0,    # > 0.8
                    'medium': 0,  # 0.6 - 0.8
                    'low': 0      # < 0.6
                },
                'sources': {},
                'recent_additions': []
            }
            
            # Score de confiance moyen
            avg_conf = candidates.filter(
                confidence_score__isnull=False
            ).aggregate(avg=Avg('confidence_score'))['avg']
            
            if avg_conf:
                stats['avg_confidence'] = round(avg_conf * 100, 1)
            
            # Distribution des scores
            stats['confidence_distribution']['high'] = candidates.filter(
                confidence_score__gt=0.8
            ).count()
            stats['confidence_distribution']['medium'] = candidates.filter(
                confidence_score__gte=0.6,
                confidence_score__lte=0.8
            ).count()
            stats['confidence_distribution']['low'] = candidates.filter(
                confidence_score__lt=0.6
            ).count()
            
            # Sources des candidats
            for source, label in SkillZoneCandidate.SOURCE_CHOICES:
                count = candidates.filter(source_tag=source).count()
                if count > 0:
                    stats['sources'][label] = count
            
            # 5 derniers ajouts
            recent = candidates.order_by('-added_on')[:5]
            for sz_cand in recent:
                stats['recent_additions'].append({
                    'candidate_name': sz_cand.candidate_id.name,
                    'added_on': sz_cand.added_on.strftime('%d/%m/%Y'),
                    'confidence': sz_cand.get_confidence_percentage(),
                    'is_auto': sz_cand.auto_classified
                })
        
        return JsonResponse(stats)
        
    except SkillZone.DoesNotExist:
        return JsonResponse({
            'status': 'error',
            'message': _("Zone introuvable")
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur stats API: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)


@login_required
@permission_required("recruitment.view_skillzoneimporthistory")
def skillzone_import_detail(request, import_id):
    """
    Vue détaillée d'un import avec les erreurs
    """
    try:
        import_history = SkillZoneImportHistory.objects.get(
            id=import_id,
            company_id=request.user.employee_get.company_id
        )
        
        # Récupérer les nouvelles zones créées
        new_zones = []
        if import_history.new_zones_created > 0:
            # Récupérer les zones créées pendant cet import
            # (basé sur la date de création proche)
            from django.utils import timezone
            import_time = import_history.import_date
            time_window = timezone.timedelta(hours=1)
            
            new_zones = SkillZone.objects.filter(
                company_id=import_history.company_id,
                auto_generated=True,
                created_at__gte=import_time - time_window,
                created_at__lte=import_time + time_window
            ).order_by('-created_at')[:import_history.new_zones_created]
        
        return render(request, 'skill_zone/import_detail.html', {
            'import': import_history,
            'new_zones': new_zones,
            'errors': import_history.error_log
        })
        
    except SkillZoneImportHistory.DoesNotExist:
        messages.error(request, _("Import introuvable"))
        return redirect('skillzone-import-history')