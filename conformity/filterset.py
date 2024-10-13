from django_filters import FilterSet, CharFilter
from .models import Action, Control, ControlPoint, Attachment


class ActionFilter(FilterSet):
    class Meta:
        model = Action
        fields = ['status', 'organization', 'owner', 'associated_conformity__id', 'associated_findings__id',
                  'associated_controlPoints__id']


class ControlFilter(FilterSet):
    class Meta:
        model = Control
        fields = ['level', 'organization', 'conformity__id', 'frequency']


class ControlPointFilter(FilterSet):
    class Meta:
        model = ControlPoint
        fields = [ 'control__id', 'control__frequency', 'status' ]

