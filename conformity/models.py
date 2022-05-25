"""
Conformity module manage all the manual declarative aspect of conformity management.
It's Organized around Organization, Policy, Measure and Conformity classes.
"""

from statistics import median
from collections import Counter
from django.db import models
from django.db.models.signals import post_init, pre_save, post_save
from django.core.validators import MaxValueValidator, MinValueValidator
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.http import Http404
import logging

User = get_user_model()


class Policy(models.Model):
    """
    Policy class represent the conformity policy you will apply on Organization.
    A Policy is simply a collections of Mesure with publication parameter.
    """

    class Type(models.TextChoices):
        """ List of the Type of policy """
        INTERNATIONAL = 'INT', _('International Standard')
        NATIONAL = 'NAT', _('National Standard')
        TECHNICAL = 'TECH', _('Technical Standard')
        RECOMANDATION = 'RECO', _('Technical Recomandation')
        POLICY = 'POL', _('Internal Policy')
        OTHER = 'OTHER', _('Other')

    name = models.CharField(max_length=256)
    version = models.IntegerField(default=0)
    publish_by = models.CharField(max_length=256)
    type = models.CharField(
        max_length=5,
        choices=Type.choices,
        default=Type.OTHER,
    )

    def __str__(self):
        return str(self.name)

    def get_type(self):
        """return the readable version of the Policy Type"""
        return self.Type(self.type).label

    def get_mesures(self):
        """return all Measure related to the Policy"""
        return Mesure.objects.filter(policy=self.id)

    def get_mesures_number(self):
        """return the number of leaf Measure related to the Policy"""
        return Mesure.objects.filter(policy=self.id).filter(mesure__is_parent=False).count()

    def get_root_mesures(self):
        """return the root Measure of the Policy"""
        return Mesure.objects.filter(policy=self.id).filter(level=0).order_by('order')


class Organization(models.Model):
    """
    Organization class is a representation of a company, a division of company, a administration...
    The Organization may answer to one or several Policy.
    """
    name = models.CharField(max_length=256)
    administrative_id = models.CharField(max_length=256, blank=True)
    description = models.CharField(max_length=256, blank=True)
    applicable_policies = models.ManyToManyField(Policy, blank=True)

    def __str__(self):
        return str(self.name)

    @staticmethod
    def get_absolute_url():
        """return the absolute URL for Forms, could probably do better"""
        return reverse('conformity:organization_index')

    def get_policies(self):
        """return all Policy applicable to the Organization"""
        return self.applicable_policies.all()

    def remove_policy(self, policy: Policy):
        """Unapply a policy to an Organization"""
        if self.applicable_policies.filter(id=policy.id).exists():
            self.applicable_policies.remove(policy)
            mesures = Mesure.objects.filter(policy=policy.id)
            for mes in mesures:
                Conformity.objects.filter(mesure=mes.id).delete()
        else:
            raise Http404("Policy not applied or non existing")

    def add_policy(self, policy: Policy):
        """Apply a Policy to an Organization"""
        pol_check = self.applicable_policies.filter(id=policy.id).exists()
        if not pol_check:
            self.applicable_policies.add(policy)
            mesures = Mesure.objects.filter(policy=policy.id)
            for mes in mesures:
                conformity = Conformity(organization=self, mesure=mes)
                conformity.save()
        else:
            raise Http404("Policy already applied")

    def get_policy_status(self, pid):
        """Return the conformity level of the Policy on the ORganisation"""
        confomitys = Conformity.objects.filter(policy=pid).filter(organization=self.id) \
            .filter(mesure__level=0)
        conf_stat = []
        for conf in confomitys:
            conf_stat.append(conf.status)
        return median(conf_stat)


class Mesure(models.Model):
    """
    A Measure is a precise requirement.
    Measure can be hierarchical in order to form a collection of Measure, aka Policy.
    A Measure is not representing the conformity level, see Conformity class.
    """
    code = models.CharField(max_length=5, blank=True)
    name = models.CharField(max_length=50, blank=True)
    level = models.IntegerField(default=0)
    order = models.IntegerField(default=1)
    policy = models.ForeignKey(Policy, on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=256, blank=True)
    description = models.CharField(max_length=4096, blank=True)
    is_parent = models.BooleanField(default=False)

    def __str__(self):
        return str(self.name)

    def get_childrens(self):
        """Return all children of the mesure"""
        return Mesure.objects.filter(parent=self.id).order_by('order')


class Conformity(models.Model):
    """
    Conformity represent the conformity of an Organization to a Measure.
    Value are automatically update for parent measure conformity
    """
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    mesure = models.ForeignKey(Mesure, on_delete=models.CASCADE)
    status = models.IntegerField(default=0,
                                 validators=[MinValueValidator(0), MaxValueValidator(100)])
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.CASCADE,
                                    null=True, blank=True)

    def __str__(self):
        return str(self.organization) + " | " + str(self.mesure)

    def get_absolute_url(self):
        """Return the absolute URL of the class for Form, probably not the best way to do it"""
        return reverse('conformity:conformity_orgpol_index', kwargs={'org': self.organization.id,
                                                                     'pol': self.mesure.policy.id})

    def get_children(self):
        """Return all children Conformity based on Measure hierarchy"""
        return Conformity.objects.filter(organization=self.organization) \
            .filter(mesure__parent=self.mesure.id).order_by('mesure__order')

    def get_parent(self):
        """Return the parent Conformity based on Measure hierarchy"""
        return Conformity.objects.filter(organization=self.organization) \
            .filter(mesure=self.mesure.parent).order_by('mesure__order')

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
            self.status = median(child_stat)
            self.save()

        if not self.mesure.level == 0:
            self.get_parent()[0].status_update()


"""
                                  Callback functions
"""

@receiver(post_init, sender=Mesure)
def post_init_callback(instance, **kwargs):
    """This function keep hierarchy of the Mesure working on each Mesure instantiation"""
    if instance.parent:
        instance.name = instance.parent.name + "-" + instance.code
        instance.level = instance.parent.level + 1
        instance.parent.is_parent = 1
    else:
        instance.name = instance.code

@receiver(post_save, sender=Organization)
def post_save_callback(sender, instance, *args, **kwargs):
    """ Callback function to instantiate or delete Conformity objects on Organization.applicable_policies update"""
    for pid in instance.applicable_policies.all():
        logging.exception(pid.id)
