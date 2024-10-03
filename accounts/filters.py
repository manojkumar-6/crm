import django_filters
from .models import *


class ConversationFilter(django_filters.FilterSet):
    date_from = django_filters.DateTimeFilter(field_name='date_queried', lookup_expr='gte', label='From')
    date_to = django_filters.DateTimeFilter(field_name='date_queried', lookup_expr='lte', label='To')

    class Meta:
        model = ConversationModel
        fields = ['date_from', 'date_to']
