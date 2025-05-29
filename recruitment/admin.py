"""
admin.py

This page is used to register the model with admins site.
"""

from django.contrib import admin

from recruitment.models import (
    AIConfiguration,
    Candidate,
    CandidatePrivacyConsent,
    CandidateRating,
    CandidateValidation,
    InterviewSchedule,
    PrivacyPolicy,
    Recruitment,
    RecruitmentSurvey,
    RecruitmentSurveyAnswer,
    SkillZone,
    Stage,
)

# Register your models here.


admin.site.register(Stage)
admin.site.register(Recruitment)
admin.site.register(Candidate)
admin.site.register(RecruitmentSurveyAnswer)
admin.site.register(RecruitmentSurvey)
admin.site.register(CandidateRating)
admin.site.register(SkillZone)
admin.site.register(InterviewSchedule)

@admin.register(CandidateValidation)
class CandidateValidationAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'selector', 'stage', 'is_validated', 'validated_at']
    list_filter = ['is_validated', 'stage', 'selector']
    search_fields = ['candidate__name', 'selector__employee_first_name']
    date_hierarchy = 'validated_at'

@admin.register(AIConfiguration)
class AIConfigurationAdmin(admin.ModelAdmin):
    list_display = ['name', 'model_name', 'is_default', 'is_active', 'created_at']
    list_filter = ['is_default', 'is_active', 'model_name']
    search_fields = ['name', 'model_name']
    filter_horizontal = ['companies']
    fieldsets = (
        ('Configuration de base', {
            'fields': ('name', 'is_default', 'is_active')
        }),
        ('Paramètres IA', {
            'fields': ('api_key', 'model_name', 'max_tokens', 'temperature')
        }),
        ('Prompt d\'analyse', {
            'fields': ('analysis_prompt',),
            'classes': ('wide',)
        }),
        ('Filiales', {
            'fields': ('companies',),
            'description': 'Sélectionnez les filiales qui utiliseront cette configuration'
        }),
    )

@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ['name', 'content_type', 'is_default', 'is_active', 'created_at']
    list_filter = ['is_default', 'is_active', 'content_type']
    search_fields = ['name']
    filter_horizontal = ['companies']

@admin.register(CandidatePrivacyConsent) 
class CandidatePrivacyConsentAdmin(admin.ModelAdmin):
    list_display = ['candidate', 'policy', 'consented_at']
    list_filter = ['consented_at', 'policy']
    search_fields = ['candidate__name', 'candidate__email']