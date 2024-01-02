from django_filters import FilterSet, CharFilter
from .models import Action, ControlPoint


class ActionFilter(FilterSet):
    class Meta:
        model = Action
        fields = ['status', 'organization', 'owner', 'associated_conformity__id', 'associated_findings__id',
                  'associated_controlPoints__id']


class ControlFilter(FilterSet):
    class Meta:
        model = ControlPoint
        fields = ['control__level', 'control__organization', 'control__conformity__id', 'control__control__id', 'control__frequency', 'control__level']
