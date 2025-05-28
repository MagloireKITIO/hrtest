# candidate_portal/admin.py
from django.contrib import admin
from .models import (
    CandidateAuth, CandidateProfile, VerificationToken, 
    SavedJob, ConversationThread, Message, CandidateSession
)

@admin.register(CandidateAuth)
class CandidateAuthAdmin(admin.ModelAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'created_at', 'last_login')
    search_fields = ('email', 'first_name', 'last_name')
    list_filter = ('is_active', 'created_at', 'last_login')
    readonly_fields = ('password', 'created_at', 'last_login')
    fieldsets = (
        (None, {'fields': ('email', 'password', 'is_active')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name')}),
        ('Dates importantes', {'fields': ('created_at', 'last_login')}),
    )

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('candidate_auth', 'company', 'phone', 'created_at')
    search_fields = ('candidate_auth__email', 'phone')
    list_filter = ('company', 'created_at')

@admin.register(VerificationToken)
class VerificationTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'token', 'is_used', 'created_at', 'expires_at')
    search_fields = ('email', 'token')
    list_filter = ('is_used', 'created_at')
    readonly_fields = ('token', 'created_at')

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ('candidate_auth', 'recruitment', 'date_saved')
    search_fields = ('candidate_auth__email', 'recruitment__title')
    list_filter = ('date_saved',)

@admin.register(ConversationThread)
class ConversationThreadAdmin(admin.ModelAdmin):
    list_display = ('candidate_auth', 'recruitment', 'created_at', 'is_active')
    search_fields = ('candidate_auth__email', 'recruitment__title')
    list_filter = ('is_active', 'created_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('thread', 'sender_type', 'timestamp', 'is_read')
    search_fields = ('content', 'thread__candidate_auth__email')
    list_filter = ('sender_type', 'is_read', 'timestamp')
    readonly_fields = ('timestamp',)

@admin.register(CandidateSession)
class CandidateSessionAdmin(admin.ModelAdmin):
    list_display = ('candidate_auth', 'created_at', 'expires_at')
    search_fields = ('candidate_auth__email',)
    list_filter = ('created_at',)
    readonly_fields = ('session_key', 'created_at')