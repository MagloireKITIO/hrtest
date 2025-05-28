from django.utils import translation

class PublicAreaLanguageMiddleware:
    """Middleware pour gérer la langue des zones publiques"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Zones publiques
        public_paths = ['/recruitment/open-recruitments', '/recruitment/recruitment-details', '/recruitment/application-form']
        
        # Si on est dans une zone publique
        if any(request.path.startswith(path) for path in public_paths):
            # Utiliser la langue stockée dans la session
            lang_code = request.session.get('public_language')
            if lang_code:
                translation.activate(lang_code)
                request.LANGUAGE_CODE = lang_code

        response = self.get_response(request)
        return response