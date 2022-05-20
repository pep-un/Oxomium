from django.db import models
from django.db.models.signals import post_init
from django.core.validators import MaxValueValidator, MinValueValidator 
from django.dispatch import receiver
from django.conf import settings
from statistics import median
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.urls import reverse, reverse_lazy
from django.http import Http404

User = get_user_model()

class Policy(models.Model):
    class Type(models.TextChoices):
        INTERNATIONAL = 'INT', _('International Standard')
        NATIONAL = 'NAT', _('National Standard')
        TECHNICAL = 'TECH', _('Technical Standard')
        RECOMANDATION = 'RECO' , _('Technical Recomandation')
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
        return self.Type(self.type).label

    def get_mesures(self):
        return Mesure.objects.filter(policy=self.id)

    # TODO Add a filter to get only the leaf of the tree
    def get_mesures_number(self):
        return Mesure.objects.filter(policy=self.id).filter(mesure__is_parent=False).count()

    def get_root_mesures(self):
        return Mesure.objects.filter(policy=self.id).filter(level=0).order_by('order')

class Organization(models.Model):
    name = models.CharField(max_length=256)
    administrative_id = models.CharField(max_length=256, blank=True)
    description = models.CharField(max_length=256, blank=True)
    applicable_policies = models.ManyToManyField(Policy, blank=True)

    def __str__(self):
        return str(self.name)

    def get_absolute_url(self):
        return reverse('conformity:organization_index')

    def get_policies(self):
        return self.applicable_policies.all()

    def remove_policy(self, policy: Policy):
        if self.applicable_policies.filter(id=policy.id).exists():
            self.applicable_policies.remove(policy)
            mesures=Mesure.objects.filter(policy=policy.id)
            for m in mesures:
                Conformity.objects.filter(mesure=m.id).delete()
        else:
            raise Http404("Policy not applied or non existing")

    def add_policy(self, policy: Policy):
        pol_check = self.applicable_policies.filter(id=policy.id).exists()
        if not pol_check:
            self.applicable_policies.add(policy)
            mesures = Mesure.objects.filter(policy=policy.id)
            for m in mesures:
                conformity = Conformity(organization=self, mesure=m)
                conformity.save()
        else:
            raise Http404("Policy already applied")

    def get_policy_status(self, pid):
        confomitys = Conformity.objects.filter(policy=pid).filter(organization=self.id).filter(mesure__level=0)
        conf_stat = []
        for conf in confomitys:
            conf_stat.append(conf.status)
        return median(conf_stat)

class Mesure(models.Model):
    code = models.CharField(max_length=5, blank=True)
    name = models.CharField(max_length=50, blank=True)
    level = models.IntegerField(default=0)
    order = models.IntegerField(default=1)
    policy = models.ForeignKey(Policy,on_delete=models.CASCADE)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=256, blank=True)
    description = models.CharField(max_length=4096, blank=True)
    is_parent = models.BooleanField(default=False)

    def __str__(self):
        return str(self.policy + " | " + self.name)

    def get_childrens(self):
        return Mesure.objects.filter(parent=self.id).order_by('order')

# Receiver for the Mesure Class
@receiver(post_init, sender=Mesure)
def post_init_callback(sender, instance, **kwargs):
    if instance.parent:
        instance.name = instance.parent.name + "-" + instance.code
        instance.level = instance.parent.level + 1
        instance.parent.is_parent = 1
    else:
        instance.name = instance.code

class Conformity(models.Model):
    organization = models.ForeignKey(Organization,on_delete=models.CASCADE)
    mesure = models.ForeignKey(Mesure,on_delete=models.CASCADE)
    status = models.IntegerField(default=0, validators=[MinValueValidator(0),MaxValueValidator(100)])
    responsible = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return str(self.organization) + " | " + str(self.mesure)

    def get_absolute_url(self):
        return reverse('conformity:conformity_orgpol_index', kwargs={'org': self.organization.id, 'pol': self.mesure.policy.id})

    def get_children(self):
        return Conformity.objects.filter(organization = self.organization).filter(mesure__parent = self.mesure.id).order_by('mesure__order')

    def get_parent(self):
        return Conformity.objects.filter(organization = self.organization).filter(mesure = self.mesure.parent).order_by('mesure__order')

    def set_status(self,i):
        self.status = i
        self.save()
        self.status_update()

    def set_responsible(self, resp):
        self.responsible = resp
        self.save()
        for child in self.get_children():
            child.set_responsible(resp)

    def status_update(self):
        childrens = self.get_children()
        child_stat = []
        if childrens.exists():
            for child in childrens:
                child_stat.append(child.status)
            self.status = median(child_stat)
            self.save()
        
        if not self.mesure.level == 0:
            self.get_parent()[0].status_update()
