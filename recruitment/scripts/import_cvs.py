import os
import random
import shutil
import django
from datetime import datetime, timedelta
from faker import Faker
from django.conf import settings
from django.core.files import File
from django.core.files.storage import default_storage
from recruitment.models import Recruitment, Stage, Candidate
from employee.models import Employee

# Initialiser Faker pour générer des données fictives
fake = Faker(['fr_FR'])

# Chemins des dossiers
MEDIA_ROOT = settings.MEDIA_ROOT
CV_UPLOAD_PATH = 'recruitment/resume'
CV_STORAGE_PATH = os.path.join(MEDIA_ROOT, CV_UPLOAD_PATH)

def ensure_directory_exists(path):
    """S'assure que le répertoire existe"""
    if not os.path.exists(path):
        os.makedirs(path)

def get_random_phone():
    """Génère un numéro de téléphone camerounais fictif"""
    prefixes = ['237690', '237691', '237697', '237698', '237699']
    return f"+{random.choice(prefixes)}{random.randint(100000, 999999)}"

def import_cvs(cv_folder_path, recruitment_id):
    """
    Importe les CV depuis un dossier avec des informations fictives
    """
    try:
        # Vérifier que les dossiers nécessaires existent
        ensure_directory_exists(CV_STORAGE_PATH)
        
        # Récupérer le recrutement
        recruitment = Recruitment.objects.get(id=recruitment_id)
        print(f"\nTraitement du recrutement: {recruitment.title}")
        
        # Récupérer l'étape de présélection
        stage = Stage.objects.get(
            recruitment_id=recruitment,
            stage_type='applied'
        )
        print(f"Étape sélectionnée: {stage.stage}")

        # Liste pour stocker les candidats créés
        created_candidates = []
        errors = []
        
        # Parcourir les fichiers du dossier
        total_files = len([f for f in os.listdir(cv_folder_path) if f.endswith('.pdf')])
        print(f"\nTraitement de {total_files} fichiers PDF...")
        
        for index, filename in enumerate(os.listdir(cv_folder_path), 1):
            if filename.endswith('.pdf'):
                try:
                    # Générer des informations fictives
                    gender = random.choice(['male', 'female'])
                    first_name = fake.first_name_male() if gender == 'male' else fake.first_name_female()
                    last_name = fake.last_name()
                    full_name = f"{first_name} {last_name}"
                    
                    # Préparer le nom du fichier de destination
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    new_filename = f"{first_name.lower()}_{last_name.lower()}_{timestamp}.pdf"
                    relative_path = os.path.join(CV_UPLOAD_PATH, new_filename)
                    
                    # Créer le candidat
                    candidate = Candidate(
                        name=full_name,
                        recruitment_id=recruitment,
                        stage_id=stage,
                        email=f"{first_name.lower()}.{last_name.lower()}@{random.choice(['gmail.com', 'yahoo.fr', 'outlook.com'])}",
                        mobile=get_random_phone(),
                        gender=gender,
                        address=fake.address(),
                        country='Cameroon',
                        state=random.choice(['Littoral', 'Centre', 'Ouest', 'Nord']),
                        city=random.choice(['Douala', 'Yaoundé', 'Bafoussam', 'Garoua']),
                        zip=str(random.randint(10000, 99999)),
                        dob=fake.date_of_birth(minimum_age=25, maximum_age=45),
                        source='application'
                    )

                    # Copier le CV vers le dossier media
                    source_path = os.path.join(cv_folder_path, filename)
                    with open(source_path, 'rb') as source_file:
                        # Utiliser default_storage pour sauvegarder le fichier
                        saved_path = default_storage.save(relative_path, File(source_file))
                        candidate.resume = saved_path
                    
                    # Assigner le poste
                    if recruitment.job_position_id:
                        candidate.job_position_id = recruitment.job_position_id
                    elif recruitment.open_positions.exists():
                        candidate.job_position_id = random.choice(recruitment.open_positions.all())
                    
                    candidate.save()
                    created_candidates.append(candidate)
                    
                    print(f"[{index}/{total_files}] Créé: {candidate.name} - CV: {new_filename}")
                    
                except Exception as e:
                    error_msg = f"Erreur avec {filename}: {str(e)}"
                    print(f"[{index}/{total_files}] ERREUR: {error_msg}")
                    errors.append(error_msg)
                    continue

        # Rapport final
        print("\n=== Rapport d'importation ===")
        print(f"Total traité: {total_files}")
        print(f"Réussis: {len(created_candidates)}")
        print(f"Échecs: {len(errors)}")
        
        if errors:
            print("\nErreurs rencontrées:")
            for error in errors:
                print(f"- {error}")
                
        return {
            'success': len(created_candidates),
            'errors': len(errors),
            'error_details': errors,
            'candidates': created_candidates
        }

    except Recruitment.DoesNotExist:
        return {"error": "Recrutement non trouvé"}
    except Stage.DoesNotExist:
        return {"error": "Étape de présélection non trouvée"}
    except Exception as e:
        return {"error": f"Erreur inattendue: {str(e)}"}