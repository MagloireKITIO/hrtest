"""
middleware.py
"""
from django.apps import apps
from django.db.models import Q
from django.http import HttpResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.urls import reverse

from base.context_processors import AllCompany
from base.horilla_company_manager import HorillaCompanyManager
from base.models import Company


class CompanyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérification de l'authentification et du middleware auth
        if hasattr(request, 'user') and request.user and request.user.is_authenticated:
            company_id = None
            try:
                employee = request.user.employee_get
                company_id = employee.company_id
            except AttributeError:
                pass

            # Gestion de la company sélectionnée en session
            if (
                request.session.get("selected_company")
                and request.session.get("selected_company") != "all"
            ):
                if not employee.has_all_company_access():
                    company_id = employee.company_id
                else:
                    company_id = Company.objects.filter(
                        id=request.session.get("selected_company")
                    ).first()
            
            elif company_id and request.session.get("selected_company") != "all":
                request.session["selected_company"] = company_id.id
                request.session["selected_company_instance"] = {
                    "company": company_id.company,
                    "icon": company_id.icon.url if company_id.icon else None,
                    "text": "My company",
                    "id": company_id.id,
                }
            elif not company_id or employee.has_all_company_access():
                request.session["selected_company"] = "all"
                all_company = AllCompany()
                request.session["selected_company_instance"] = {
                    "company": all_company.company,
                    "icon": all_company.icon.url,
                    "text": all_company.text,
                    "id": all_company.id,
                }

            # Application des filtres sur les modèles
            app_labels = [
                "recruitment",
                "employee",
                "onboarding",
                "attendance",
                "leave",
                "payroll",
                "asset",
                "pms",
                "base",
                "helpdesk",
                "offboarding",
                "horilla_documents",
            ]
            app_models = [
                model
                for model in apps.get_models()
                if model._meta.app_label in app_labels
            ]

            # Si l'employé est un sélecteur et qu'on est dans le module de recrutement
            if employee.is_selector and 'recruitment' in request.path:
                model = apps.get_model('recruitment', 'Recruitment')
                model.add_to_class(
                    "company_filter",
                    Q(selectors=employee)
                )
            # Sinon appliquer les filtres normaux par company
            elif company_id and not employee.has_all_company_access():
                for model in app_models:
                    if getattr(model, "company_id", None):
                        model.add_to_class(
                            "company_filter",
                            Q(company_id=company_id) | Q(company_id__isnull=True),
                        )
                    elif (
                        isinstance(model.objects, HorillaCompanyManager)
                        and model.objects.related_company_field
                    ):
                        model.add_to_class(
                            "company_filter",
                            Q(**{model.objects.related_company_field: company_id})
                            | Q(
                                **{
                                    f"{model.objects.related_company_field}__isnull": True
                                }
                            ),
                        )

        response = self.get_response(request)
        return response
    

class PasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        exempt_urls = [
            '/login/',
            '/logout/', 
            '/change-password/',
            '/static/',
            '/media/',
            '/admin/',
        ]
        
        # Vérification complète de l'authentification
        if hasattr(request, 'user') and request.user and request.user.is_authenticated:
            # Vérifie si l'utilisateur est un employé qui doit changer son mot de passe
            if hasattr(request.user, 'employee_get'):
                employee = request.user.employee_get
                
                # Vérifier expiration du mot de passe (90 jours)
                if employee.is_password_expired():
                    employee.needs_password_change = True
                    employee.save()
                
                if employee.needs_password_change:
                    # Vérifie si l'URL n'est pas déjà dans les exemptions
                    if not any(request.path.startswith(url) for url in exempt_urls):
                        return redirect('/change-password/')
                    
        return self.get_response(request)