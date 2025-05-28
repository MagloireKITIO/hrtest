"""
paginator_qry.py

This module is used for pagination.
"""

from django.core.paginator import Paginator
from base.methods import get_pagination
from django.db.models.query import QuerySet  # To check if the object is a QuerySet


def paginator_qry(qryset, page_number):
    """
    This method is used to generate common paginator limit.
    """
    # Check if the qryset is a QuerySet and not already ordered
    if isinstance(qryset, QuerySet) and not qryset.ordered:
        qryset = qryset.order_by('created_at')  # Replace 'created_at' with an appropriate field if needed

    paginator = Paginator(qryset, get_pagination())
    qryset = paginator.get_page(page_number)
    return qryset
