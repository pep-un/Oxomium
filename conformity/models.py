"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Policy, Measure and Conformity classes.
"""

import logging
from statistics import mean
from django.db import models
from django.db.models.signals import m2m_changed, pre_save
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.urls import reverse

User = get_user_model()


class PolicyManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Policy(models.Model):
    """
    Policy class represent the conformity policy you will apply on Organization.
    A Policy is simply a collections of Measure with publication parameter.
    """

    class Type(models.TextChoices):
        """ List of the Type of policy """
        INTERNATIONAL = 'INT', _('International Standard')
        NATIONAL = 'NAT', _('National Standard')
        TECHNICAL = 'TECH', _('Technical Standard')
        RECOMANDATION = 'RECO', _('Technical Recomandation')
        POLICY = 'POL', _('Internal Policy')
        OTHER = 'OTHER', _('Other')

    objects = PolicyManager()
    name = models.CharField(max_length=256, unique=True)
    version = models.IntegerField(default=0)
    publish_by = models.CharField(max_length=256)
    type = models.CharField(
        max_length=5,
        choices=Type.choices,
        default=Type.OTHER,
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Policy'
        verbose_name_plural = 'Policies'

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return (self.name,)

    def get_type(self):
        """return the readable version of the Policy Type"""
        return self.Type(self.type).label

    def get_measures(self):
        """return all Measure related to the Policy"""
        return Measure.objects.filter(policy=self.id)

    def get_measures_number(self):
        """return the number of leaf Measure related to the Policy"""
        return Measure.objects.filter(policy=self.id).filter(measure__is_parent=False).count()

    def get_root_measure(self):
        """return the root Measure of the Policy"""
        return Measure.objects.filter(policy=self.id).filter(level=0).order_by('order')

    def get_first_measures(self):
        """return the root Measure of the Policy"""
        return Measure.objects.filter(policy=self.id).filter(level=1).order_by('order')


class Organization(models.Model):
    """
    Organization class is a representation of a company, a division of company, a administration...
    The Organization may answer to one or several Policy.
    """
    name = models.CharField(max_length=256, unique=True)
    administrative_id = models.CharField(max_length=256, blank=True)
    description = models.CharField(max_length=256, blank=True)
    applicable_policies = models.ManyToManyField(Policy, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return (self.name,)

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:organization_index')

    def get_policies(self):
        """return all Policy applicable to the Organization"""
        return self.applicable_policies.all()

    def remove_conformity(self, pid):
        """Cascade deletion of conformity"""
        measure_set = Measure.objects.filter(policy=pid)
        for measure in measure_set:
            Conformity.objects.filter(measure=measure.id).filter(organization=self.id).delete()

    def add_conformity(self, pid):
        """Automatic creation of conformity"""
        measure_set = Measure.objects.filter(policy=pid)
        for measure in measure_set:
            conformity = Conformity(organization=self, measure=measure)
            conformity.save()

    def get_policy_status(self, pid):
        """Return the conformity level of the Policy on the ORganisation"""
        confomitys = Conformity.objects.filter(policy=pid).filter(organization=self.id) \
            .filter(measure__level=0)
        conf_stat = []
        for conf in confomitys:
            conf_stat.append(conf.status)
        return mean(conf_stat)


class MeasureManager(models.Manager):
    def get_by_natural_key(self, name):
        return self.get(name=name)


class Measure(models.Model):
    """
    A Measure is a precise requirement.
    Measure can be hierarchical in order to form a collection of Measure, aka Policy.
    A Measure is not representing the conformity level, see Conformity class.
    """
    objects = MeasureManager()
    code = models.CharField(max_length=5, blank=True)
    name = models.CharField(max_length=50, blank=True, unique=True)
    level = models.IntegerField(default=0)
    order = models.IntegerField(default=1)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)
    title = models.CharField(max_length=256, blank=True)
    description = models.TextField(blank=True)
    is_parent = models.BooleanField(default=False)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return str(self.name)

    def natural_key(self):
        return (self.name,)

    natural_key.dependencies = ['conformity.policy']

    def get_childrens(self):
        """Return all children of the measure"""
        return Measure.objects.filter(parent=self.id).order_by('order')


class Conformity(models.Model):
    """
    Conformity represent the conformity of an Organization to a Measure.
    Value are automatically update for parent measure conformity
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    measure = models.ForeignKey(Measure, on_delete=models.CASCADE)
    status = models.IntegerField(default=0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)])
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE,
                                    null=True, blank=True)
    comment = models.TextField(max_length=4096, blank=True)

    class Meta:
        ordering = ['organization','measure']
        verbose_name = 'Conformity'
        verbose_name_plural = 'Conformities'
        unique_together = (('organization','measure'),)

    def __str__(self):
        return str(self.organization) + " | " + str(self.measure)

    def natural_key(self):
        return (self.organization, self.measure)
    natural_key.dependencies = ['conformity.policy','conformity.measure','conformity.organization']

    def get_absolute_url(self):
        """Return the absolute URL of the class for Form, probably not the best way to do it"""
        return reverse('conformity:conformity_orgpol_index', kwargs={'org': self.organization.id,
                                                                     'pol': self.measure.policy.id})

    def get_children(self):
        """Return all children Conformity based on Measure hierarchy"""
        return Conformity.objects.filter(organization=self.organization) \
            .filter(measure__parent=self.measure.id).order_by('measure__order')

    def get_parent(self):
        """Return the parent Conformity based on Measure hierarchy"""
        return Conformity.objects.filter(organization=self.organization) \
            .filter(measure=self.measure.parent).order_by('measure__order')

    def set_status(self, i):
        """Update the status and call recursive update function"""
        self.status = i
        self.save()
        self.status_update()

    def set_responsible(self, resp):
        """Update the responsible and apply to child"""
        self.responsible = resp
        self.save()
        for child in self.get_children():
            child.set_responsible(resp)

    def status_update(self):
        """Recursive function to crawl up the Measure tree and update all status"""
        childrens = self.get_children()
        child_stat = []
        if childrens.exists():
            for child in childrens:
                child_stat.append(child.status)
            self.status = mean(child_stat)
            self.save()

        if not self.measure.level == 0:
            self.get_parent()[0].status_update()


# Callback functions


@receiver(pre_save, sender=Measure)
def post_init_callback(instance, **kwargs):
    """This function keep hierarchy of the Measure working on each Measure instantiation"""
    if instance.parent:
        instance.name = instance.parent.name + "-" + instance.code
        instance.level = instance.parent.level + 1
        instance.parent.is_parent = 1
    else:
        instance.name = instance.code


@receiver(m2m_changed, sender=Organization.applicable_policies.through)
def change_policy(instance, action, pk_set, *args, **kwargs):
    if action == "post_add":
        for pk in pk_set:
            instance.add_conformity(pk)

    if action == "post_remove":
        for pk in pk_set:
            instance.remove_conformity(pk)
