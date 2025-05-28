# candidate_portal/forms.py
from django import forms
from django.utils.translation import gettext_lazy as _
from .models import CandidateAuth, CandidateProfile, VerificationToken
from base.models import Company
from recruitment.models import Candidate

class CandidateLoginForm(forms.Form):
    """Formulaire de connexion pour les candidats"""
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Votre adresse email")
        })
    )
    
    password = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Votre mot de passe")
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            try:
                candidate_auth = CandidateAuth.objects.get(email=email)
                if not candidate_auth.check_password(password):
                    raise forms.ValidationError(_("Email ou mot de passe incorrect."))
                if not candidate_auth.is_active:
                    raise forms.ValidationError(_("Ce compte est désactivé."))
                cleaned_data['candidate_auth'] = candidate_auth
            except CandidateAuth.DoesNotExist:
                raise forms.ValidationError(_("Email ou mot de passe incorrect."))
        
        return cleaned_data


class CandidateRegistrationForm(forms.Form):
    """Formulaire d'inscription pour les candidats"""
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Votre adresse email"),
            'readonly': True
        })
    )
    
    first_name = forms.CharField(
        label=_("Prénom"),
        widget=forms.TextInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Votre prénom")
        })
    )
    
    last_name = forms.CharField(
        label=_("Nom"),
        widget=forms.TextInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Votre nom")
        })
    )
    
    password1 = forms.CharField(
        label=_("Mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Choisir un mot de passe")
        })
    )
    
    password2 = forms.CharField(
        label=_("Confirmation du mot de passe"),
        widget=forms.PasswordInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Confirmer votre mot de passe")
        })
    )
    
    company = forms.ModelChoiceField(
        queryset=Company.objects.all(),
        label=_("Entreprise"),
        widget=forms.Select(attrs={
            'class': 'oh-select oh-select-2 w-100',
        })
    )
    
    phone = forms.CharField(
        required=False,
        label=_("Téléphone"),
        widget=forms.TextInput(attrs={
            'class': 'oh-input w-100',
            'placeholder': _("Votre numéro de téléphone")
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.token = kwargs.pop('token', None)
        super().__init__(*args, **kwargs)
        
        if self.token and self.token.email:
            self.fields['email'].initial = self.token.email
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CandidateAuth.objects.filter(email=email).exists():
            raise forms.ValidationError(_("Un compte existe déjà avec cette adresse email."))
        return email
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(_("Les mots de passe ne correspondent pas."))
        
        return password2
    
    def save(self):
        email = self.cleaned_data['email']
        password = self.cleaned_data['password1']
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        company = self.cleaned_data['company']
        phone = self.cleaned_data.get('phone', '')
        
        # Créer le candidat_auth
        candidate_auth = CandidateAuth.objects.create(
            email=email,
            password=password,  # Le modèle va hasher le mot de passe
            first_name=first_name,
            last_name=last_name
        )
        
        # Créer le profil
        CandidateProfile.objects.create(
            candidate_auth=candidate_auth,
            company=company,
            phone=phone
        )
        
        # Marquer le token comme utilisé
        if self.token:
            self.token.is_used = True
            self.token.save()
            
            # Associer les candidatures existantes
            if self.token.candidate_id:
                try:
                    candidate = Candidate.objects.get(id=self.token.candidate_id)
                    # Mise à jour du nom du candidat si nécessaire
                    if not candidate.name or len(candidate.name.strip()) == 0:
                        full_name = f"{first_name} {last_name}"
                        candidate.name = full_name
                        candidate.save()
                except Candidate.DoesNotExist:
                    pass
        
        return candidate_auth