# candidate_portal/urls.py
from django.urls import path
from . import views

app_name = 'candidate_portal'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/<uuid:token>/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('applications/', views.applications_view, name='applications'),
    path('applications/<int:application_id>/', views.application_detail_view, name='application_detail'),
    path('jobs/', views.jobs_view, name='jobs'),
    path('jobs/save/<int:job_id>/', views.toggle_save_job, name='toggle_save_job'),
    path('messages/', views.messages_view, name='messages'),
    path('messages/<int:thread_id>/', views.conversation_view, name='conversation'),
    path('profile/', views.profile_view, name='profile'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('reset-password/<uuid:token>/', views.reset_password, name='reset_password'),

    # Nouvelles URLs pour le profil complet
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/personal-info/update/', views.update_personal_info, name='update_personal_info'),
    path('profile/photo/update/', views.update_photo, name='update_photo'),
    
    # Expérience professionnelle
    path('profile/experience/add/', views.add_experience, name='add_experience'),
    path('profile/experience/<int:experience_id>/edit/', views.edit_experience, name='edit_experience'),
    path('profile/experience/<int:experience_id>/delete/', views.delete_experience, name='delete_experience'),
    path('profile/experience/<int:experience_id>/get/', views.get_experience, name='get_experience'),

    
    # Formation
    path('profile/education/add/', views.add_education, name='add_education'),
    path('profile/education/<int:education_id>/edit/', views.edit_education, name='edit_education'),
    path('profile/education/<int:education_id>/delete/', views.delete_education, name='delete_education'),
    path('profile/education/<int:education_id>/get/', views.get_education, name='get_education'),

    # Documents
    path('profile/document/add/', views.add_document, name='add_document'),
    path('profile/document/<int:document_id>/delete/', views.delete_document, name='delete_document'),
    
    # Compétences
    path('profile/skills/update/', views.update_skills, name='update_skills'),
    path('profile/skills/suggestions/', views.get_skill_suggestions, name='get_skill_suggestions'),
    path('profile/skills/create/', views.create_skill, name='create_skill'),

    path('settings/', views.settings_view, name='settings'),
    path('settings/update-password/', views.update_password, name='update_password'),
    path('settings/update-notifications/', views.update_notifications, name='update_notifications'),
    path('settings/update-privacy/', views.update_privacy, name='update_privacy'),
    path('settings/delete-account/', views.delete_account, name='delete_account'),
    path('applications/<int:application_id>/withdraw/', views.withdraw_application, name='withdraw_application'),

]