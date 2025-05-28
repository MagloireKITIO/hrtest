"""
Google Forms integration utilities
"""
import os

from responses import logger
from google.oauth2 import service_account
from googleapiclient.discovery import build
from django.conf import settings
import json

def get_google_service():
    """
    Get Google service using service account credentials
    """
    try:
        credentials_path = os.path.join(settings.BASE_DIR, 'service-account.json')
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path,
            scopes=['https://www.googleapis.com/auth/forms']
        )
        
        return build('forms', 'v1', credentials=credentials)
    except Exception as e:
        logger.error(f"Error creating Google service: {str(e)}")
        return None

def create_google_form(title, description=''):
    """
    Create a new Google Form using service account
    """
    try:
        service = get_google_service()
        if not service:
            return None

        form_body = {
            "info": {
                "title": title,
                "documentTitle": title
            },
            "settings": {
                "collectEmail": True
            }
        }

        if description:
            form_body["info"]["description"] = description

        # Create the form
        form = service.forms().create(body=form_body).execute()
        
        # Add default questions
        questions = [
            {
                "title": "Lettre de motivation",
                "questionItem": {
                    "question": {
                        "required": True,
                        "textQuestion": {
                            "paragraph": True
                        }
                    }
                }
            },
            {
                "title": "Expérience professionnelle",
                "questionItem": {
                    "question": {
                        "required": True,
                        "textQuestion": {
                            "paragraph": True
                        }
                    }
                }
            }
        ]

        for question in questions:
            service.forms().batchUpdate(
                formId=form['formId'],
                body={
                    "requests": [{
                        "createItem": {
                            "item": question,
                            "location": {"index": 0}
                        }
                    }]
                }
            ).execute()

        # Get the form URL
        form_url = f"https://docs.google.com/forms/d/{form['formId']}/viewform"
        return form_url

    except Exception as e:
        logger.error(f"Error creating Google Form: {str(e)}")
        return None