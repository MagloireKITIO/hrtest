
import os 
from .settings import *
from .settings import BASE_DIR

from azure.storage.blob import BlobServiceClient
from storages.backends.azure_storage import AzureStorage




SECRET_KEY = os.environ['SECRET']
ALLOWED_HOSTS = ['*']

CSRF_TRUSTED_ORIGINS = ['https://' + os.environ['WEBSITE_HOSTNAME']]

DEBUG = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",  
    "django.middleware.common.CommonMiddleware",  
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "horilla.horilla_middlewares.ThreadLocalMiddleware",
    "base.middleware.CompanyMiddleware",
    "base.middleware.PasswordChangeMiddleware",
]


AZURE_ACCOUNT_NAME = "accountstorageapprdc"
AZURE_ACCOUNT_KEY = os.environ['BLOBSECRET']
AZURE_STATIC_CONTAINER = "static"
AZURE_MEDIA_CONTAINER = "media"
AZURE_CUSTOM_DOMAIN = f"{AZURE_ACCOUNT_NAME}.blob.core.windows.net"


# Azure Storage configuration classes with overwrite settings
class AzureStaticStorage(AzureStorage):
    account_name = AZURE_ACCOUNT_NAME
    account_key = AZURE_ACCOUNT_KEY
    azure_container = AZURE_STATIC_CONTAINER
    expiration_secs = None
    custom_domain = AZURE_CUSTOM_DOMAIN
    overwrite_files = True  # Allow overwriting existing files

class AzureMediaStorage(AzureStorage):
    account_name = AZURE_ACCOUNT_NAME
    account_key = AZURE_ACCOUNT_KEY
    azure_container = AZURE_MEDIA_CONTAINER
    expiration_secs = None
    custom_domain = AZURE_CUSTOM_DOMAIN
    overwrite_files = True  # Allow overwriting existing files

# Update the blob service client configuration
blob_service_client = BlobServiceClient(
    account_url=f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net",
    credential=AZURE_ACCOUNT_KEY
)

# Configure container clients with overwrite settings
def get_blob_client(container_name, blob_name):
    container_client = blob_service_client.get_container_client(container_name)
    return container_client.get_blob_client(blob_name)

# Récupération des clients des conteneurs
static_container_client = blob_service_client.get_container_client(AZURE_STATIC_CONTAINER)
media_container_client = blob_service_client.get_container_client(AZURE_MEDIA_CONTAINER)



STATICFILES_DIRS = [
    BASE_DIR / "static",
]

# Configuration Django pour les fichiers statiques
STATICFILES_STORAGE = 'horilla.deployment.AzureStaticStorage'
STATIC_URL = f"https://{AZURE_CUSTOM_DOMAIN}/{AZURE_STATIC_CONTAINER}/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Configuration Django pour les fichiers média
DEFAULT_FILE_STORAGE = 'horilla.deployment.AzureMediaStorage'
MEDIA_URL = f"https://{AZURE_CUSTOM_DOMAIN}/{AZURE_MEDIA_CONTAINER}/"
MEDIA_ROOT = BASE_DIR / "media"


conn_str = os.environ['AZURE_POSTGRESQL_CONNECTIONSTRING']
conn_str_params = {pair.split('=')[0]: pair.split('=')[1] for pair in conn_str.split(' ')}
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': conn_str_params['dbname'],
        'HOST': conn_str_params['host'],
        'USER': conn_str_params['user'],
        'PASSWORD': conn_str_params['password'],
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-cache-key',
    }
}

# Google Calendar Configuration
GOOGLE_CALENDAR_CREDENTIALS = {
    "web": {
        "client_id": os.environ['GOOGLE_CLIENT_ID'],
        "project_id": os.environ['GOOGLE_PROJECT_ID'],
        "auth_uri": os.environ['GOOGLE_AUTH_URI'],
        "token_uri": os.environ['GOOGLE_TOKEN_URI'],
        "auth_provider_x509_cert_url": os.environ['GOOGLE_AUTH_PROVIDER_CERT_URL'],
        "client_secret": os.environ['GOOGLE_CLIENT_SECRET'],
        "redirect_uri": [os.environ['GOOGLE_REDIRECT_URI']]
    }
}


GOOGLE_OAUTH_CALLBACK_URL = os.environ['GOOGLE_OAUTH_CALLBACK_URL']

# Ai analysis
USE_AZURE_STORAGE = True