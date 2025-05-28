
# installation

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py compilemessages : pour la compilation des fichiers de traduction
python manage.py createhorillauser
python manage.py runserver




# configuration de la BD  horilla/settings.py

pip install psycopg2

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': '',
        'USER': '',
        'PASSWORD': '',
        'HOST': '',
        'PORT': '',
    }
}
python manage.py makemigrations
python manage.py migrate


