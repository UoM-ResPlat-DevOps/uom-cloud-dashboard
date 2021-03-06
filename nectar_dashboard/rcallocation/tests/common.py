from datetime import date, timedelta
from django.forms.models import model_to_dict
from factory import fuzzy

from nectar_dashboard.rcallocation import models
from nectar_dashboard.rcallocation import choices_for, choices

FOR_CHOICES = dict(choices_for.FOR_CHOICES)
DURATION_CHOICES = dict(choices.DURATION_CHOICE)
ALLOCATION_HOMES = dict(choices.ALLOC_HOME_CHOICE)
GRANT_TYPES = dict(choices.GRANT_TYPES)


def allocation_to_dict(model):
    allocation = model_to_dict(model)
    allocation['quota'] = [model_to_dict(quota)
                           for quota in model.quotas.all()]

    allocation['institution'] = [model_to_dict(institution)
                                 for institution in model.institutions.all()]

    allocation['publication'] = [model_to_dict(publication)
                                 for publication in model.publications.all()]

    allocation['grant'] = [model_to_dict(grant)
                           for grant in model.grants.all()]

    allocation['investigator'] = [model_to_dict(inv)
                                  for inv in model.investigators.all()]
    return allocation


def get_groups(service_type, allocation=None):
    quota_fuzz = fuzzy.FuzzyInteger(1, 100000)
    st = models.ServiceType.objects.get(catalog_name=service_type)
    resources = st.resource_set.filter(requestable=True)
    groups = []
    allocated_zones = []
    if allocation:
        service_type_groups = allocation.quotas.filter(
            service_type__catalog_name=service_type)
        for group in service_type_groups:
            quotas = []
            for quota in group.quota_set.filter(resource__requestable=True):
                quotas.append({'id': quota.id,
                               'requested_quota': quota.requested_quota,
                               'resource': quota.resource.id,
                               'group': group.id,
                               'quota': quota.quota})
            groups.append({'id': group.id,
                           'zone': group.zone.name,
                           'service_type': group.service_type.catalog_name,
                           'quotas': quotas})
            allocated_zones.append(group.zone.name)
    for zone in st.zones.all():
        if zone.name in allocated_zones:
            continue
        quotas = []
        for resource in resources:
            quotas.append(
                {'id': '',
                 'requested_quota': quota_fuzz.fuzz(),
                 'resource': resource.id,
                 'group': '',
                 'quota': 0})
        groups.append({'id': '',
                       'zone': zone.name,
                       'service_type': st.catalog_name,
                       'quotas': quotas})
    return groups


def request_allocation(user, model=None, compute_groups=None,
                       volume_groups=None, object_groups=None,
                       institutions=None, publications=None, grants=None,
                       investigators=None):

    _1_year = date.today() + timedelta(days=365)
    start_date = fuzzy.FuzzyDate(date.today(), _1_year).fuzz()
    duration = fuzzy.FuzzyChoice(DURATION_CHOICES.keys()).fuzz()
    forp_1 = fuzzy.FuzzyInteger(1, 8).fuzz()
    forp_2 = fuzzy.FuzzyInteger(1, 9 - forp_1).fuzz()
    forp_3 = 10 - (forp_1 + forp_2)
    for_code = fuzzy.FuzzyChoice(FOR_CHOICES.keys())
    quota = fuzzy.FuzzyInteger(1, 100000)
    alloc_home = fuzzy.FuzzyChoice(ALLOCATION_HOMES.keys())
    grant_type = fuzzy.FuzzyChoice(GRANT_TYPES.keys())

    model_dict = {'project_name': fuzzy.FuzzyText().fuzz(),
                  'project_description': fuzzy.FuzzyText().fuzz(),
                  'start_date': start_date,  # only used for asserting
                  'estimated_project_duration': duration,
                  'field_of_research_1': for_code.fuzz(),
                  'field_of_research_2': for_code.fuzz(),
                  'field_of_research_3': for_code.fuzz(),
                  'for_percentage_1': forp_1 * 10,
                  'for_percentage_2': forp_2 * 10,
                  'for_percentage_3': forp_3 * 10,
                  'usage_patterns': fuzzy.FuzzyText().fuzz(),
                  'use_case': fuzzy.FuzzyText().fuzz(),
                  'estimated_number_users': quota.fuzz(),
                  'geographic_requirements': fuzzy.FuzzyText().fuzz(),
                  'allocation_home': alloc_home.fuzz(),
                  'nectar_support': 'nectar supporting',
                  'ncris_support': 'ncris supporting',
                  }

    if model:
        compute_groups = get_groups('compute', model)
        volume_groups = get_groups('volume', model)
        object_groups = get_groups('object', model)

        institutions = [{'id': ins.id,
                         'name': ins.name}
                        for ins in model.institutions.all()]

        publications = [{'id': pub.id,
                         'publication': pub.publication}
                        for pub in model.publications.all()]

        grants = [{'id': grant.id,
                   'grant_type': grant_type.fuzz(),
                   'funding_body_scheme': grant.funding_body_scheme,
                   'grant_id': grant.grant_id,
                   'first_year_funded': 2015,
                   'last_year_funded': 2017,
                   'total_funding': quota.fuzz()
                   }
                  for grant in model.grants.all()]

        investigators = [{'id': inv.id,
                          'title': inv.title,
                          'given_name': inv.given_name,
                          'surname': inv.surname,
                          'email': inv.email,
                          'institution': inv.institution,
                          'additional_researchers': inv.additional_researchers
                          }
                         for inv in model.investigators.all()]

    else:
        if not volume_groups:
            volume_groups = get_groups('volume')

        if not object_groups:
            object_groups = get_groups('object')

        if not compute_groups:
            compute_groups = get_groups('compute')

        if not institutions:
            institutions = [
                {'id': '',
                 'name': 'Monash'}]

        if not publications:
            publications = [
                {'id': '',
                 'publication': 'publication testing'}]

        if not grants:
            grants = [{
                'id': '',
                'grant_type': grant_type.fuzz(),
                'funding_body_scheme': 'ARC funding scheme',
                'grant_id': 'arc-grant-0001',
                'first_year_funded': 2015,
                'last_year_funded': 2017,
                'total_funding': quota.fuzz()
            }]

        if not investigators:
            investigators = [{
                'id': '',
                'title': 'Prof.',
                'given_name': 'MeRC',
                'surname': 'Monash',
                'email': 'merc.monash@monash.edu',
                'institution': 'Monash University',
                'additional_researchers': 'None'
            }]

    def next_char(c):
        return chr(ord(c) + 1)

    form = model_dict.copy()
    all_quotas = []

    def add_quota_forms(service_type, groups, prefix_start='a'):
        new_prefix = prefix_start
        for group in groups:
            if group['id']:
                prefix = group['id']
            else:
                prefix = new_prefix
                new_prefix = next_char(new_prefix)

            quotas = group.pop('quotas')
            form['%s_%s-INITIAL_FORMS' %
                 (service_type, prefix)] = len(quotas) if group['id'] else 0
            resource_count = models.Resource.objects.filter(
                service_type__catalog_name=service_type,
                requestable=True).count()
            form['%s_%s-TOTAL_FORMS' % (service_type, prefix)] = resource_count
            form['%s_%s-MAX_NUM_FORMS' % (service_type, prefix)] = 1000

            for i, quota in enumerate(quotas):
                all_quotas.append({'resource': quota['resource'],
                                   'zone': group['zone'],
                                   'requested_quota': quota['requested_quota'],
                                   'quota': quota['quota']})
                for k, v in quota.items():
                    form['%s_%s-%s-%s' % (service_type, prefix, i, k)] = v

            for k, v in group.items():
                form['%s_%s-%s' % (service_type, prefix, k)] = v

    prefix_start = 'b' if model else 'a'
    add_quota_forms('compute', compute_groups, prefix_start)
    add_quota_forms('volume', volume_groups, prefix_start)
    add_quota_forms('object', object_groups, prefix_start)

    form['institutions-INITIAL_FORMS'] = model.institutions.count() \
        if model else 0
    form['institutions-TOTAL_FORMS'] = len(institutions)
    form['institutions-MAX_NUM_FORMS'] = 1000

    form['publications-INITIAL_FORMS'] = model.publications.count() \
        if model else 0
    form['publications-TOTAL_FORMS'] = len(publications)
    form['publications-MAX_NUM_FORMS'] = 1000

    form['grants-INITIAL_FORMS'] = model.grants.count() if model else 0
    form['grants-TOTAL_FORMS'] = len(grants)
    form['grants-MAX_NUM_FORMS'] = 1000

    form['investigators-INITIAL_FORMS'] = model.investigators.count() \
        if model else 0
    form['investigators-TOTAL_FORMS'] = len(investigators)
    form['investigators-MAX_NUM_FORMS'] = 1000

    for i, ins in enumerate(institutions):
        for k, v in ins.items():
            form['institutions-%s-%s' % (i, k)] = v

    for i, pub in enumerate(publications):
        for k, v in pub.items():
            form['publications-%s-%s' % (i, k)] = v

    for i, grant in enumerate(grants):
        for k, v in grant.items():
            form['grants-%s-%s' % (i, k)] = v

    for i, inv in enumerate(investigators):
        for k, v in inv.items():
            form['investigators-%s-%s' % (i, k)] = v

    model_dict['quotas'] = all_quotas
    model_dict['institutions'] = institutions
    model_dict['publications'] = publications
    model_dict['grants'] = grants
    model_dict['investigators'] = investigators
    return model_dict, form
