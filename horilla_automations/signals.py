"""
horilla_automation/signals.py

"""

import copy
import logging
import threading
import types

from django import template
from django.core.mail import EmailMessage
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from horilla.horilla_middlewares import _thread_locals
from horilla.signals import post_bulk_update, pre_bulk_update

logger = logging.getLogger(__name__)


@classmethod
def from_list(cls, object_list):
    # Create a queryset-like object from the list
    queryset_like_object = cls(model=object_list[0].__class__)
    queryset_like_object._result_cache = list(object_list)
    queryset_like_object._prefetch_related_lookups = ()
    return queryset_like_object


setattr(QuerySet, "from_list", from_list)

SIGNAL_HANDLERS = []
INSTANCE_HANDLERS = []


def start_automation():
    """
    Automation signals
    """
    from horilla_automations.methods.methods import get_model_class, split_query_string
    from horilla_automations.models import MailAutomation

    @receiver(post_delete, sender=MailAutomation)
    @receiver(post_save, sender=MailAutomation)
    def automation_pre_create(sender, instance, **kwargs):
        """
        signal method to handle automation post save
        """
        start_connection()
        track_previous_instance()

    def clear_connection():
        """
        Method to clear signals handlers
        """
        for handler in SIGNAL_HANDLERS:
            post_save.disconnect(handler, sender=handler.model_class)
            post_bulk_update.disconnect(handler, sender=handler.model_class)
        SIGNAL_HANDLERS.clear()

    def create_post_bulk_update_handler(automation, model_class, query_strings):
        def post_bulk_update_handler(sender, queryset, *args, **kwargs):
            def _bulk_update_thread_handler(
                queryset, previous_queryset_copy, automation
            ):
                request = getattr(queryset, "request", None)

                if request:
                    for index, instance in enumerate(queryset):
                        previous_instance = previous_queryset_copy[index]
                        send_automated_mail(
                            request,
                            False,
                            automation,
                            query_strings,
                            instance,
                            previous_instance,
                        )

            previous_bulk_record = getattr(_thread_locals, "previous_bulk_record", None)
            previous_queryset = None
            if previous_bulk_record:
                previous_queryset = previous_bulk_record["queryset"]
                previous_queryset_copy = previous_bulk_record["queryset_copy"]

            bulk_thread = threading.Thread(
                target=_bulk_update_thread_handler,
                args=(queryset, previous_queryset_copy, automation),
            )
            bulk_thread.start()

        func_name = f"{automation.method_title}_post_bulk_signal_handler"

        # Dynamically create a function with a unique name
        handler = types.FunctionType(
            post_bulk_update_handler.__code__,
            globals(),
            name=func_name,
            argdefs=post_bulk_update_handler.__defaults__,
            closure=post_bulk_update_handler.__closure__,
        )

        # Set additional attributes on the function
        handler.model_class = model_class
        handler.automation = automation

        return handler

    def start_connection():
        """
        Method to start signal connection accordingly to the automation
        """
        clear_connection()
        automations = MailAutomation.objects.filter(is_active=True)
        for automation in automations:

            condition_querystring = automation.condition_querystring.replace(
                "automation_multiple_", ""
            )

            query_strings = split_query_string(condition_querystring)

            model_path = automation.model
            model_class = get_model_class(model_path)

            handler = create_post_bulk_update_handler(
                automation, model_class, query_strings
            )
            SIGNAL_HANDLERS.append(handler)

            post_bulk_update.connect(handler, sender=model_class)

            def create_signal_handler(name, automation, query_strings):
                def signal_handler(sender, instance, created, **kwargs):
                    """
                    Signal handler for post-save events of the model instances.
                    """
                    request = getattr(_thread_locals, "request", None)
                    previous_record = getattr(_thread_locals, "previous_record", None)
                    previous_instance = None
                    if previous_record:
                        previous_instance = previous_record["instance"]

                    args = (
                        request,
                        created,
                        automation,
                        query_strings,
                        instance,
                        previous_instance,
                    )
                    thread = threading.Thread(
                        target=lambda: send_automated_mail(*args),
                    )
                    thread.start()

                signal_handler.__name__ = name
                signal_handler.model_class = model_class
                signal_handler.automation = automation
                return signal_handler

            # Create and connect the signal handler
            handler_name = f"{automation.method_title}_signal_handler"
            dynamic_signal_handler = create_signal_handler(
                handler_name, automation, query_strings
            )
            SIGNAL_HANDLERS.append(dynamic_signal_handler)
            post_save.connect(
                dynamic_signal_handler, sender=dynamic_signal_handler.model_class
            )

    def create_pre_bulk_update_handler(automation, model_class):
        def pre_bulk_update_handler(sender, queryset, *args, **kwargs):
            request = getattr(_thread_locals, "request", None)
            if request:
                queryset_copy = queryset.none()
                if queryset.count():
                    queryset_copy = QuerySet.from_list(copy.deepcopy(list(queryset)))
                _thread_locals.previous_bulk_record = {
                    "automation": automation,
                    "queryset": queryset,
                    "queryset_copy": queryset_copy,
                }

        func_name = f"{automation.method_title}_pre_bulk_signal_handler"

        # Dynamically create a function with a unique name
        handler = types.FunctionType(
            pre_bulk_update_handler.__code__,
            globals(),
            name=func_name,
            argdefs=pre_bulk_update_handler.__defaults__,
            closure=pre_bulk_update_handler.__closure__,
        )

        # Set additional attributes on the function
        handler.model_class = model_class
        handler.automation = automation

        return handler

    def track_previous_instance():
        """
        method to add signal to track the automations model previous instances
        """

        def clear_instance_signal_connection():
            """
            Method to clear instance handler signals
            """
            for handler in INSTANCE_HANDLERS:
                pre_save.disconnect(handler, sender=handler.model_class)
                pre_bulk_update.disconnect(handler, sender=handler.model_class)
            INSTANCE_HANDLERS.clear()

        clear_instance_signal_connection()
        automations = MailAutomation.objects.filter(is_active=True)
        for automation in automations:
            model_class = get_model_class(automation.model)

            handler = create_pre_bulk_update_handler(automation, model_class)
            INSTANCE_HANDLERS.append(handler)
            pre_bulk_update.connect(handler, sender=model_class)

            @receiver(pre_save, sender=model_class)
            def instance_handler(sender, instance, **kwargs):
                """
                Signal handler for pres-save events of the model instances.
                """
                # prevented storing the scheduled activities
                request = getattr(_thread_locals, "request", None)
                if instance.pk:
                    # to get the previous instance
                    instance = model_class.objects.filter(id=instance.pk).first()
                if request:
                    _thread_locals.previous_record = {
                        "automation": automation,
                        "instance": instance,
                    }
                instance_handler.__name__ = (
                    f"{automation.method_title}_instance_handler"
                )
                return instance_handler

            instance_handler.model_class = model_class
            instance_handler.automation = automation

            INSTANCE_HANDLERS.append(instance_handler)

    track_previous_instance()
    start_connection()


def send_automated_mail(
    request,
    created,
    automation,
    query_strings,
    instance,
    previous_instance,
):
    from horilla_automations.methods.methods import evaluate_condition, operator_map
    from horilla_views.templatetags.generic_template_filters import getattribute

    # Si pas de conditions définies, envoyer l'email directement
    if not query_strings or len(query_strings) == 0:
        if created and automation.trigger == "on_create":
            send_mail(request, automation, instance)
        elif automation.trigger == "on_update":
            send_mail(request, automation, instance)
        return

    applicable = False
    and_exists = False
    false_exists = False
    instance_values = []
    previous_instance_values = []
    
    for condition in query_strings:
        try:
            condition_list = condition.getlist("condition")
            
            # Vérifier que la condition a au moins 3 éléments [attr, operator, value]
            if len(condition_list) < 3:
                print(f"DEBUG: Condition malformée ignorée: {condition_list}")
                continue
                
            attr = condition_list[0]
            operator = condition_list[1] 
            value = condition_list[2]

            if value == "on":
                value = True
            elif value == "off":
                value = False
                
            instance_value = getattribute(instance, attr)
            previous_instance_value = getattribute(previous_instance, attr) if previous_instance else None

            # Gestion des modèles et QuerySets
            if getattr(instance_value, "pk", None) and hasattr(instance_value, '_meta'):
                instance_value = str(getattr(instance_value, "pk", None))
                previous_instance_value = str(getattr(previous_instance_value, "pk", None)) if previous_instance_value else None
            elif hasattr(instance_value, 'values_list'):  # QuerySet
                instance_value = list(instance_value.values_list("pk", flat=True))
                previous_instance_value = list(previous_instance_value.values_list("pk", flat=True)) if previous_instance_value else []

            instance_values.append(instance_value)
            previous_instance_values.append(previous_instance_value)

            # Évaluer la condition
            condition_result = evaluate_condition(instance_value, operator, value)
            
            logic = condition.get("logic")
            if not logic:
                applicable = condition_result
            else:
                applicable = operator_map[logic](applicable, condition_result)
                
            if not applicable:
                false_exists = True
            if logic == "and":
                and_exists = True
            if false_exists and and_exists:
                applicable = False
                break
                
        except Exception as e:
            print(f"DEBUG: Erreur dans la condition: {e}")
            # En cas d'erreur dans une condition, on continue avec les autres
            continue
    
    # Si aucune condition valide, envoyer l'email par défaut
    if len(query_strings) == 0 or not any(condition.getlist("condition") for condition in query_strings):
        applicable = True
    
    # Décider d'envoyer l'email
    if applicable:
        if created and automation.trigger == "on_create":
            send_mail(request, automation, instance)
        elif (automation.trigger == "on_update") and (
            set(previous_instance_values) != set(instance_values)
        ):
            send_mail(request, automation, instance)


def send_mail(request, automation, instance):
    """
    Mail sending method for candidate application
    """
    from base.backends import ConfiguredEmailBackend
    from base.methods import generate_pdf
    from horilla_automations.methods.methods import (
        get_model_class,
        get_related_field_model,
    )
    from horilla_views.templatetags.generic_template_filters import getattribute

    # Utiliser la configuration email du système
    email_backend = ConfiguredEmailBackend()
    from_email = email_backend.dynamic_from_email_with_display_name
    reply_to = [from_email]

    mail_template = automation.mail_template
    pk = getattribute(instance, automation.mail_details)
    model_class = get_model_class(automation.model)
    model_class = get_related_field_model(model_class, automation.mail_details)
    mail_to_instance = model_class.objects.filter(pk=pk).first()

    # Déterminer si c'est un candidat en vérifiant les attributs plutôt que le type
    is_candidate = hasattr(instance, 'email') and hasattr(instance, 'recruitment_id')
    
    if is_candidate:
        # Si c'est un candidat qui postule, on envoie à son email
        to = [instance.email]
        cc = []
    else:
        # Pour les autres cas, utiliser la logique existante
        tos = []
        for mapping in eval(automation.mail_to):
            result = getattribute(mail_to_instance, mapping)
            if isinstance(result, list):
                tos.extend(result)
                continue
            tos.append(result)
        tos = list(filter(None, tos))
        to = tos[:1]
        cc = tos[1:]

    if mail_to_instance and to:
        attachments = []
        sender = None
            
        # Process attachments
        for template_attachment in automation.template_attachments.all():
            template_bdy = template.Template(template_attachment.body)
            context = template.Context({"instance": mail_to_instance, "self": sender})
            render_bdy = template_bdy.render(context)
            attachments.append(
                (
                    "Document",
                    generate_pdf(render_bdy, {}, path=False, title="Document").content,
                    "application/pdf",
                )
            )

        # Render email body and title
        template_bdy = template.Template(mail_template.body)
        title_template = template.Template(automation.title)
        
        context = template.Context({"instance": mail_to_instance, "self": sender})
        title_context = template.Context({"instance": instance, "self": sender})
        
        render_bdy = template_bdy.render(context)
        render_title = title_template.render(title_context)

        # Créer l'email avec le backend configuré
        email = EmailMessage(
            subject=render_title,
            body=render_bdy,
            to=to,
            cc=cc,
            from_email=from_email,
            reply_to=reply_to,
            connection=email_backend,
        )
        email.content_subtype = "html"
        email.attachments = attachments

        def _send_mail(email):
            try:
                email.send()
                logger.info(f"Email sent successfully to {to}")
            except Exception as e:
                logger.error(f"Failed to send email to {to}: {e}")

        thread = threading.Thread(
            target=lambda: _send_mail(email),
        )
        thread.start()