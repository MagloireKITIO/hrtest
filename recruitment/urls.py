"""
urls.py

This module is used to map url path with view methods.
"""

from django.urls import path

import recruitment.views.actions
import recruitment.views.dashboard
import recruitment.views.search
import recruitment.views.surveys
from base.views import add_remove_dynamic_fields, object_duplicate
from recruitment.forms import QuestionForm, RecruitmentCreationForm, StageCreationForm
from recruitment.models import Candidate, Recruitment, RecruitmentSurvey, Stage
from recruitment.views import skillzone_import, skillzone_search, views
from recruitment.views.actions import get_template



urlpatterns = [
    path("recruitment-create", views.recruitment, name="recruitment-create"),
    path("recruitment-view", views.recruitment_view, name="recruitment-view"),
    path(
        "recruitment-search",
        recruitment.views.search.recruitment_search,
        name="recruitment-search",
    ),
    path(
        "recruitment-update/<int:rec_id>/",
        views.recruitment_update,
        name="recruitment-update",
    ),
    path(
        "recruitment-duplicate/<int:obj_id>/",
        object_duplicate,
        name="recruitment-duplicate",
        kwargs={
            "model": Recruitment,
            "form": RecruitmentCreationForm,
            "template": "recruitment/recruitment_form.html",
        },
    ),
    path(
        "recruitment-update-pipeline/<int:rec_id>/",
        views.recruitment_update_pipeline,
        name="recruitment-update-pipeline",
    ),
    path(
        "recruitment-update-delete/<int:rec_id>/",
        recruitment.views.actions.recruitment_delete_pipeline,
        name="recruitment-delete-pipeline",
    ),
    path(
        "recruitment-delete/<int:rec_id>/",
        recruitment.views.actions.recruitment_delete,
        name="recruitment-delete",
    ),
    # Shortlisting
    path('shortlist-candidates/<int:stage_id>/', 
        views.shortlist_candidates, 
        name='shortlist-candidates'),
    path(
        "recruitment-close-pipeline/<int:rec_id>/",
        views.recruitment_close_pipeline,
        name="recruitment-close-pipeline",
    ),
    path(
        "recruitment-reopen-pipeline/<int:rec_id>/",
        views.recruitment_reopen_pipeline,
        name="recruitment-reopen-pipeline",
    ),
    path("pipeline/", views.recruitment_pipeline, name="pipeline"),
    path("pipeline-search/", views.filter_pipeline, name="pipeline-search"),
    path(
        "pipeline-stages-component/<str:view>/",
        views.stage_component,
        name="pipeline-stages-component",
    ),
    path("get-stage-count", views.get_stage_badge_count, name="get-stage-count"),
    path(
        "update-candidate-stage-and-sequence",
        views.update_candidate_stage_and_sequence,
        name="update-candidate-stage-and-sequence",
    ),
    path(
        "update-candidate-sequence",
        views.update_candidate_sequence,
        name="update-candidate-sequence",
    ),
    # path(
    #     "update-candidate-stage",
    #     views.update_candidate_stage,
    #     name="update-candidate-stage",
    # ),
    path(
        "candidate-stage-component",
        views.candidate_component,
        name="candidate-stage-component",
    ),
    path(
        "candidate-stage-change",
        views.change_candidate_stage,
        name="candidate-stage-change",
    ),
    path("pipeline-card", views.recruitment_pipeline_card, name="pipeline-card"),
    path(
        "recruitment-archive/<int:rec_id>",
        views.recruitment_archive,
        name="recruitment-archive",
    ),
    path(
        "candidate-schedule-date-update",
        views.candidate_schedule_date_update,
        name="candidate-schedule-date-update",
    ),
    path("stage-create", views.stage, name="rec-stage-create"),
    path("stage-view", views.stage_view, name="rec-stage-view"),
    path("stage-data/<int:rec_id>/", views.stage_data, name="stage-data"),
    path("stage-search", recruitment.views.search.stage_search, name="stage-search"),
    path("stage-update/<int:stage_id>/", views.stage_update, name="rec-stage-update"),
    path(
        "rec-stage-duplicate/<int:obj_id>/",
        object_duplicate,
        name="rec-stage-duplicate",
        kwargs={
            "model": Stage,
            "form": StageCreationForm,
            "template": "stage/stage_form.html",
        },
    ),
    path("add-candidate-to-stage", views.add_candidate, name="add-candidate-to-stage"),
    path(
        "stage-update-pipeline/<int:stage_id>/",
        views.stage_update_pipeline,
        name="stage-update-pipeline",
    ),
    path(
        "stage-title-update/<int:stage_id>/",
        views.stage_title_update,
        name="stage-title-update",
    ),
    path(
        "stage-delete/<int:stage_id>/",
        recruitment.views.actions.stage_delete,
        name="rec-stage-delete",
    ),
    path(
        "remove-stage-manager/<int:mid>/<int:sid>/",
        recruitment.views.actions.remove_stage_manager,
        name="rec-remove-stage-manager",
    ),
    path(
        "remove-recruitment-manager/<int:mid>/<int:rid>/",
        recruitment.views.actions.remove_recruitment_manager,
        name="remove-recruitment-manager",
    ),
    path("candidate-create", views.candidate, name="candidate-create"),
    path(
        "recruitment-stage-get/<int:rec_id>/",
        views.recruitment_stage_get,
        name="recruitment-stage-get",
    ),
    path(
        "candidate-stage-update/<int:cand_id>/",
        views.candidate_stage_update,
        name="candidate-stage-update",
    ),
    path("view-note/<int:cand_id>/", views.view_note, name="view-note"),
    path("add-note/<int:cand_id>/", views.add_note, name="add-note"),
    path("add-note", views.add_note, name="add-note-post"),
    path("create-note/<int:cand_id>/", views.create_note, name="create-note"),
    path("create-note", views.create_note, name="create-note-post"),
    path("note-update/<int:note_id>/", views.note_update, name="note-update"),
    path(
        "note-update-individual/<int:note_id>/",
        views.note_update_individual,
        name="note-update-individual",
    ),
    path(
        "note-delete/<int:note_id>/",
        recruitment.views.actions.note_delete,
        name="note-delete",
    ),
    path(
        "note-delete-individual/<int:note_id>/",
        recruitment.views.actions.note_delete_individual,
        name="note-delete-individual",
    ),
    path("send-mail/<int:cand_id>/", views.form_send_mail, name="send-mail"),
    path("send-mail/", views.form_send_mail, name="send-mail"),
    path(
        "interview-schedule/<int:cand_id>/",
        views.interview_schedule,
        name="interview-schedule",
    ),
    path(
        "create-interview-schedule",
        views.create_interview_schedule,
        name="create-interview-schedule",
    ),
    path(
        "edit-interview/<int:interview_id>/",
        views.interview_edit,
        name="edit-interview",
    ),
    path(
        "delete-interview/<int:interview_id>/",
        views.interview_delete,
        name="delete-interview",
    ),
    path("get_managers", views.get_managers, name="get_managers"),
    path("candidate-view/", views.candidate_view, name="candidate-view"),
    path("interview-view/", views.interview_view, name="interview-view"),
    path(
        "interview-filter-view/",
        views.interview_filter_view,
        name="interview-filter-view",
    ),
    path(
        "interview-employee-remove/<int:interview_id>/<int:employee_id>",
        views.interview_employee_remove,
        name="interview-employee-remove",
    ),
    path(
        "candidate-filter-view",
        recruitment.views.search.candidate_filter_view,
        name="candidate-filter-view",
    ),
    path(
        "search-candidate",
        recruitment.views.search.candidate_search,
        name="search-candidate",
    ),
    path("candidate-view-list", views.candidate_view_list, name="candidate-view-list"),
    path("candidate-view-card", views.candidate_view_card, name="candidate-view-card"),
    path("candidate-info-export", views.candidate_export, name="candidate-info-export"),
    path(
        "candidate-view/<int:cand_id>/",
        views.candidate_view_individual,
        name="candidate-view-individual",
        kwargs={"model": Candidate},
    ),
    path(
        "candidate-update/<int:cand_id>/",
        views.candidate_update,
        name="rec-candidate-update",
        kwargs={"model": Candidate},
    ),
    path(
        "candidate-conversion/<int:cand_id>/",
        views.candidate_conversion,
        name="candidate-conversion",
        kwargs={"model": Candidate},
    ),
    path(
        "delete-profile-image/<int:obj_id>/",
        views.delete_profile_image,
        name="delete-profile-image",
    ),
    path(
        "candidate-delete/<int:cand_id>/",
        recruitment.views.actions.candidate_delete,
        name="rec-candidate-delete",
    ),
    path(
        "candidate-archive/<int:cand_id>/",
        recruitment.views.actions.candidate_archive,
        name="rec-candidate-archive",
    ),
    path(
        "candidate-bulk-delete",
        recruitment.views.actions.candidate_bulk_delete,
        name="candidate-bulk-delete",
    ),
    path(
        "candidate-bulk-archive",
        recruitment.views.actions.candidate_bulk_archive,
        name="candidate-bulk-archive",
    ),
    path(
        "candidate-history/<int:cand_id>/",
        views.candidate_history,
        name="candidate-history",
    ),
    path(
        "application-form",
        recruitment.views.surveys.application_form,
        name="application-form",
    ),
    path(
        "send-acknowledgement", views.send_acknowledgement, name="send-acknowledgement"
    ),
    path(
        "dashboard", recruitment.views.dashboard.dashboard, name="recruitment-dashboard"
    ),
    path(
        "dashboard-pipeline",
        recruitment.views.dashboard.dashboard_pipeline,
        name="recruitment-pipeline",
    ),
    path(
        "get-open-positions",
        recruitment.views.dashboard.get_open_position,
        name="get-open-position",
    ),
    path(
        "dashboard-hiring",
        recruitment.views.dashboard.dashboard_hiring,
        name="dashboard-hiring",
    ),
    path(
        "dashboard-vacancy",
        recruitment.views.dashboard.dashboard_vacancy,
        name="dashboard-vacancy",
    ),
    path(
        "candidate-status",
        recruitment.views.dashboard.candidate_status,
        name="candidate-status",
    ),
    path(
        "candidate-sequence-update",
        views.candidate_sequence_update,
        name="candidate-sequence-update",
    ),
    path(
        "stage-sequence-update",
        views.stage_sequence_update,
        name="stage-sequence-update",
    ),
    path(
        "survey-template-preview/<str:title>/",
        recruitment.views.surveys.survey_preview,
        name="survey-template-preview",
    ),
    path(
        "update-question-order",
        recruitment.views.surveys.question_order_update,
        name="update-question-order",
    ),
    path(
        "recruitment-application-survey",
        recruitment.views.surveys.survey_form,
        name="recruitment-application-survey",
    ),
    path(
        "recruitment-survey-question-template-view/",
        recruitment.views.surveys.view_question_template,
        name="recruitment-survey-question-template-view",
    ),
    path(
        "recruitment-survey-question-template-create",
        recruitment.views.surveys.create_question_template,
        name="recruitment-survey-question-template-create",
    ),
    path(
        "add-remove-options-field",
        add_remove_dynamic_fields,
        name="add-remove-options-field",
        kwargs={
            "model": RecruitmentSurvey,
            "form_class": QuestionForm,
            "template": "survey/add_more_options.html",
            "field_type": "character",
            "field_name_pre": "options",
        },
    ),
    path(
        "recruitment-survey-question-template-edit/<int:survey_id>/",
        recruitment.views.surveys.update_question_template,
        name="recruitment-survey-question-template-edit",
    ),
    path(
        "recruitment-survey-question-template-duplicate/<int:obj_id>/",
        object_duplicate,
        name="recruitment-survey-question-template-duplicate",
        kwargs={
            "model": RecruitmentSurvey,
            "form": QuestionForm,
            "template": "survey/template_form.html",
        },
    ),
    path(
        "recruitment-survey-question-template-delete/<int:survey_id>/",
        recruitment.views.surveys.delete_survey_question,
        name="recruitment-survey-question-template-delete",
    ),
    path(
        "candidate-survey",
        recruitment.views.surveys.candidate_survey,
        name="candidate-survey",
    ),
    path(
        "filter-survey",
        recruitment.views.search.filter_survey,
        name="rec-filter-survey",
    ),
    path(
        "single-survey-view/<int:survey_id>/",
        recruitment.views.surveys.single_survey,
        name="single-survey-view",
    ),
    path(
        "survey-template-create",
        recruitment.views.surveys.create_template,
        name="survey-template-create",
    ),
    path(
        "survey-template-delete",
        recruitment.views.surveys.delete_template,
        name="survey-template-delete",
    ),
    path(
        "survey-template-question-add",
        recruitment.views.surveys.question_add,
        name="survey-template-question-add",
    ),
    path("candidate-select/", views.candidate_select, name="candidate-select"),
    path(
        "candidate-select-filter/",
        views.candidate_select_filter,
        name="candidate-select-filter",
    ),
    path("skill-zone-view/", views.skill_zone_view, name="skill-zone-view"),
    path("skill-zone-create", views.skill_zone_create, name="skill-zone-create"),
    path(
        "skill-zone-update/<int:sz_id>",
        views.skill_zone_update,
        name="skill-zone-update",
    ),
    path(
        "skill-zone-delete/<int:sz_id>",
        views.skill_zone_delete,
        name="skill-zone-delete",
    ),
    path(
        "skill-zone-archive/<int:sz_id>",
        views.skill_zone_archive,
        name="skill-zone-archive",
    ),
    path("skill-zone-filter", views.skill_zone_filter, name="skill-zone-filter"),
    path(
        "skill-zone-cand-create/<int:sz_id>",
        views.skill_zone_candidate_create,
        name="skill-zone-cand-create",
    ),
    path(
        "skill-zone-cand-card-view/<int:sz_id>/",
        views.skill_zone_cand_card_view,
        name="skill-zone-cand-card-view",
    ),
    path(
        "skill-zone-cand-edit/<int:sz_cand_id>/",
        views.skill_zone_cand_edit,
        name="skill-zone-cand-edit",
    ),
    path(
        "skill-zone-cand-filter",
        views.skill_zone_cand_filter,
        name="skill-zone-cand-filter",
    ),
    path(
        "skill-zone-cand-archive/<int:sz_cand_id>/",
        views.skill_zone_cand_archive,
        name="skill-zone-cand-archive",
    ),
    path("to-skill-zone/<int:cand_id>", views.to_skill_zone, name="to-skill-zone"),
    path(
        "skill-zone-cand-delete/<int:sz_cand_id>",
        views.skill_zone_cand_delete,
        name="skill-zone-cand-delete",
    ),
    path("get-template/<int:obj_id>/", get_template, name="get-template"),
    path("get-template-hint/", get_template, name="get-template-hint"),
    path(
        "create-candidate-rating/<int:cand_id>/",
        views.create_candidate_rating,
        name="create-candidate-rating",
    ),
    path(
        "update-candidate-rating/<int:cand_id>/",
        views.update_candidate_rating,
        name="update-candidate-rating",
    ),
    path(
        "open-recruitments",
        views.open_recruitments,
        name="open-recruitments",
    ),
    path(
        "recruitment-details/<int:id>/",
        views.recruitment_details,
        name="recruitment-details",
    ),
    path(
        "add-more-files/<int:id>/",
        views.add_more_files,
        name="add-more-files",
    ),
    path(
        "add-more-files-individual/<int:id>/",
        views.add_more_individual_files,
        name="add-more-files-individual",
    ),
    path(
        "delete-stage-note-file/<int:id>/",
        views.delete_stage_note_file,
        name="delete-stage-note-file",
    ),
    path(
        "delete-individual-note-file/<int:id>/",
        views.delete_individual_note_file,
        name="delete-individual-note-file",
    ),
    path("get-mail-log-rec", views.get_mail_log, name="get-mail-log-rec"),
    path(
        "candidate-self-tracking",
        views.candidate_self_tracking,
        name="candidate-self-tracking",
    ),
    path(
        "candidate-self-tracking-rating-option",
        views.candidate_self_tracking_rating_option,
        name="candidate-self-tracking-rating-option",
    ),
    path(
        "candidate-self-status-tracking",
        views.candidate_self_status_tracking,
        name="candidate-self-status-tracking",
    ),
    path(
        "create-reject-reason", views.create_reject_reason, name="create-reject-reason"
    ),
    path(
        "delete-reject-reasons",
        views.delete_reject_reason,
        name="delete-reject-reasons",
    ),
    path(
        "resume-completion",
        views.resume_completion,
        name="resume-completion",
    ),
    path(
        "check-vaccancy",
        views.check_vaccancy,
        name="check-vaccancy",
    ),
    path(
        "skills-view/",
        views.skills_view,
        name="skills-view",
    ),
    path(
        "create-skills/",
        views.create_skills,
        name="create-skills",
    ),
    path(
        "delete-skills/",
        views.delete_skills,
        name="delete-skills",
    ),
    path(
        "add-bulk-resume/",
        views.add_bulk_resumes,
        name="add-bulk-resume",
    ),
    path(
        "view-bulk-resume/",
        views.view_bulk_resumes,
        name="view-bulk-resume",
    ),
    path(
        "delete-resume-file/",
        views.delete_resume_file,
        name="delete-resume-file",
    ),
    
    # # ajout motivation 
    # path(
    #     "delete-motivation-file/",
    #     views.delete_motivation_file,
    #     name="delete-motivation-file",
    # ),

    path(
        "matching-resumes/<int:rec_id>",
        views.matching_resumes,
        name="matching-resumes",
    ),
    path(
        "matching-resume-completion",
        views.matching_resume_completion,
        name="matching-resume-completion",
    ),
    path(
        "candidate-reject-reasons/",
        views.candidate_reject_reasons,
        name="candidate-reject-reasons",
    ),
    path(
        "hired-candidate-chart",
        views.hired_candidate_chart,
        name="hired-candidate-chart",
    ),
    path(
        "self-tracking-feature/",
        views.self_tracking_feature,
        name="self-tracking-feature",
    ),

    path('get-selectors/', views.get_selectors, name='get-selectors'),
    path('get-all-employees/', views.get_all_employees, name='get-all-employees'),  

    path(
    'stage-managers-options/',
    views.stage_managers_options,
    name='stage-managers-options'
    ),
    path('validate-selected-candidates/', views.validate_selected_candidates, name='validate-selected-candidates'),
    path('toggle-candidate-validation/', views.toggle_candidate_validation, name='toggle-candidate-validation'),
    
    path('import-skills/', views.import_skills, name='import-skills'),

    path(
        'google-form-callback/',
        views.google_form_callback,
        name='google-form-callback'
    ),

    path(
        'get-unsuccessful-candidates/', 
        views.get_unsuccessful_candidates, 
        name='get-unsuccessful-candidates'
    ),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
    path('interviews/json/', views.get_interviews_json, name='get-interviews-json'),
    path('interview/<int:interview_id>/details/', views.interview_detail, name='interview-detail'),

    path(
        'start-analysis/<int:stage_id>/',
        views.start_ai_analysis,
        name='start_ai_analysis'
    ),
    path(
        'analysis-details/<int:candidate_id>/',
        views.get_analysis_details,
        name='get_analysis_details'
    ),
    path(
        'retry-analysis/<int:candidate_id>/',
        views.retry_analysis,
        name='retry_analysis'
    ),
    path('stage-analysis-status/<int:stage_id>/', views.get_stage_analysis_status, name='stage-analysis-status'),

    path('set-public-language/<str:language_code>/', views.set_public_language, name='set_public_language'),

    path('ai-configuration/', views.ai_configuration_view, name='ai-configuration-view'),
    path('ai-configuration/create/', views.ai_configuration_create, name='ai-configuration-create'),
    path('ai-configuration/<int:config_id>/update/', views.ai_configuration_update, name='ai-configuration-update'),
    path('ai-configuration/<int:config_id>/delete/', views.ai_configuration_delete, name='ai-configuration-delete'),
    path('ai-configuration/<int:config_id>/test/', views.ai_configuration_test, name='ai-configuration-test'),
    path('ai-configuration/<int:config_id>/toggle-default/', views.ai_configuration_toggle_default, name='ai-configuration-toggle-default'),

    path('get-company-selectors/', views.get_company_selectors, name='get-company-selectors'),
    path('get-company-managers/', views.get_company_managers, name='get-company-managers'),
    path('get-company-positions/', views.get_company_positions, name='get-company-positions'),
    
    path('privacy-policy/', views.privacy_policy_view, name='privacy-policy-view'),
    path('privacy-policy/create/', views.privacy_policy_create, name='privacy-policy-create'),
    path('privacy-policy/update/<int:policy_id>/', views.privacy_policy_update, name='privacy-policy-update'),
    path('privacy-policy/delete/<int:policy_id>/', views.privacy_policy_delete, name='privacy-policy-delete'),
    path('privacy-policy/toggle-default/<int:policy_id>/', views.privacy_policy_toggle_default, name='privacy-policy-toggle-default'),
    path('get-privacy-policy/<int:recruitment_id>/', views.get_privacy_policy_content, name='get-privacy-policy-content'),

    # NOUVELLES URLs pour l'import en masse
    path("skill-zone/import/", skillzone_import.skillzone_bulk_import, name="skillzone-bulk-import"),
    path("skill-zone/import/history/", skillzone_import.skillzone_import_history, name="skillzone-import-history"),
    path("skill-zone/import/status/<int:import_id>/", skillzone_import.skillzone_import_status, name="skillzone-import-status"),
    path("skill-zone/import/detail/<int:import_id>/", views.skillzone_import_detail, name="skillzone-import-detail"),

    path("skill-zone/import/create-zone/", skillzone_import.create_skillzone_for_import, name="skillzone-create-for-import"),
    
    # NOUVELLES URLs pour la recherche intelligente
    path("skill-zone/search/", skillzone_search.skillzone_smart_search, name="skillzone-search"),
    path("skill-zone/search/autocomplete/", skillzone_search.skillzone_search_autocomplete, name="skillzone-search-autocomplete"),
    
    # API endpoints pour les fonctionnalités avancées
    path("api/skill-zone/classify/<int:candidate_id>/", views.api_classify_candidate, name="api-classify-candidate"),
    path("api/skill-zone/reclassify/<int:sz_cand_id>/", views.api_reclassify_candidate, name="api-reclassify-candidate"),
    
    path("api/skill-zone/stats/count/", views.api_skillzone_stats, {'sz_id': 0}, name="api-skillzone-stats-count"),
    path("api/skill-zone/stats/all/", views.api_skillzone_stats, {'sz_id': 0}, name="api-skillzone-stats-all"),
    path("api/skill-zone/stats/<int:sz_id>/", views.api_skillzone_stats, name="api-skillzone-stats"),   

]
