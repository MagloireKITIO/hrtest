from uuid import uuid4

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from employee.models import Employee


class Command(BaseCommand):
    help = "Creates a new user"

    def add_arguments(self, parser):
        parser.add_argument("--first_name", type=str, help="First name of the new user")
        parser.add_argument("--last_name", type=str, help="Last name of the new user")
        parser.add_argument("--username", type=str, help="Username of the new user")
        parser.add_argument("--password", type=str, help="Password for the new user")
        parser.add_argument("--email", type=str, help="Email of the new user")
        parser.add_argument("--phone", type=str, help="Phone number of the new user")

    def handle(self, *args, **options):
        try:
            if not options["first_name"]:
                first_name = input("Enter first name: ")
                last_name = input("Enter last name: ")
                username = input("Enter username: ")
                password = input("Enter password: ")
                email = input("Enter email: ")
                phone = input("Enter phone number: ")
            else:
                first_name = options["first_name"]
                last_name = options["last_name"]
                username = options["username"]
                password = options["password"]
                email = options["email"]
                phone = options["phone"]

            # Vérifier si l'utilisateur existe déjà
            existing_user = User.objects.filter(username=username).first()
            if existing_user is not None:
                self.stdout.write(
                    self.style.WARNING(f'User "{username}" already exists - skipping creation')
                )
                return

            # Créer le super utilisateur
            created_user = User.objects.create_superuser(
                username=username, email=email, password=password
            )
            
            # Créer le profil employé
            employee = Employee()
            employee.employee_user_id = created_user
            employee.employee_first_name = first_name
            employee.employee_last_name = last_name
            employee.email = email
            employee.phone = phone
            employee.save()

            # Créer ou vérifier le bot Activa HR
            bot = User.objects.filter(username="Activa HR").first()
            if bot is None:
                User.objects.create_user(
                    username="Activa HR",
                    password=str(uuid4()),
                )

            self.stdout.write(
                self.style.SUCCESS(f'Employee "{employee}" created successfully')
            )
            
        except Exception as e:
            # Log l'erreur mais continue l'exécution
            self.stdout.write(
                self.style.WARNING(f'Warning during user creation for "{username}": {str(e)}')
            )
            # Si un utilisateur a été partiellement créé, on le supprime
            if 'created_user' in locals() and created_user:
                try:
                    created_user.delete()
                except Exception:
                    pass  # Ignore les erreurs de suppression