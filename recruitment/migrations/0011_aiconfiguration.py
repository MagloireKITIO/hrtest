# Generated by Django 5.1.6 on 2025-05-22 18:57

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0004_alter_announcement_is_active_and_more'),
        ('recruitment', '0010_alter_candidate_is_active_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AIConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, null=True, verbose_name='Created At')),
                ('is_active', models.BooleanField(default=True, verbose_name='Est actif')),
                ('name', models.CharField(help_text='Nom de la configuration IA', max_length=100, verbose_name='Configuration Name')),
                ('api_key', models.CharField(help_text="Clé API Hugging Face pour l'analyse des CV", max_length=255, verbose_name='Hugging Face API Key')),
                ('model_name', models.CharField(default='deepseek-ai/DeepSeek-R1', help_text='Nom du modèle IA à utiliser', max_length=100, verbose_name='Model Name')),
                ('analysis_prompt', models.TextField(default='IMPORTANT: Répondez uniquement avec un JSON valide sans texte additionnel.\n        Vous devez d\'abord vérifier si le CV correspond au poste décrit.\n        Si le CV ne correspond pas au domaine du poste, donner un score de 0.\n        1. Pertinence du domaine (30%) - Si le domaine ne correspond PAS DU TOUT au poste, score=0\n        2. Expérience professionnelle (25%) - Durée, postes similaires, responsabilités\n        3. Formation/Éducation (20%) - Diplômes pertinents, niveau d\'études\n        4. Compétences techniques (15%) - Adéquation avec les technologies requises\n        5. Certifications/Projets (10%) - Certifications spécifiques, projets pertinents\n        \n        Critères du poste:\n        {}\n        \n        Format JSON requis:\n        {{\n            "job_matching": {{\n                "is_relevant": true/false,\n                "reason": "Expliquer pourquoi le CV correspond ou non au poste(phrase courte)"\n            }},\n            "score": entier entre 0-100 (mettre 0 si job_matching.is_relevant est false),\n            "details": {{\n                "education": "texte",\n                "experience": "texte", \n                "technical_skills": "texte",\n                "certifications": "texte"\n            }},\n            "strengths": ["liste"],\n            "areas_for_improvement": ["liste"]\n        }}', help_text="Prompt utilisé pour l'analyse des CV", verbose_name='Analysis Prompt')),
                ('is_default', models.BooleanField(default=False, help_text="Configuration par défaut si aucune n'est assignée à la filiale", verbose_name='Default Configuration')),
                ('max_tokens', models.IntegerField(default=2500, help_text='Nombre maximum de tokens pour la réponse', verbose_name='Max Tokens')),
                ('temperature', models.FloatField(default=0.1, help_text='Température du modèle (0.0 = déterministe, 2.0 = créatif)', validators=[django.core.validators.MinValueValidator(0.0), django.core.validators.MaxValueValidator(2.0)], verbose_name='Temperature')),
                ('companies', models.ManyToManyField(blank=True, help_text='Filiales utilisant cette configuration', to='base.company', verbose_name='Companies')),
                ('created_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL, verbose_name='Créé par')),
                ('modified_by', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(class)s_modified_by', to=settings.AUTH_USER_MODEL, verbose_name='Modified By')),
            ],
            options={
                'verbose_name': 'AI Configuration',
                'verbose_name_plural': 'AI Configurations',
            },
        ),
    ]
