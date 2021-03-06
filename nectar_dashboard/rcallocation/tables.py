from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.core import urlresolvers

from horizon import tables

from nectar_dashboard.rcallocation import models
from nectar_dashboard.rcallocation import utils


# Actions
class EditRequest(tables.LinkAction):
    name = "edit"
    verbose_name = ("Edit request")
    url = "horizon:allocation:requests:edit_request"
    classes = ("btn-associate",)

    def allowed(self, request, instance):
        return instance.can_be_edited() or (
            instance.can_admin_edit() and
            utils.user_is_allocation_admin(request.user))


class ViewHistory(tables.LinkAction):
    name = "view_history"
    verbose_name = "View history"
    url = "horizon:allocation:requests:allocation_history"


def status_icon(allocation):
    css_style = 'alloc-icon-wip'
    title = allocation.get_status_display()
    text = allocation.get_status_display()
    if allocation.status == models.AllocationRequest.APPROVED:
        css_style = 'alloc-icon-ok'
    data = mark_safe('<p title="%s" class="alloc-icon %s">%s</p>'
                     % (title, css_style, text))
    return data


def allocation_title(allocation,
                     link='horizon:allocation:requests:allocation_view'):
    url = urlresolvers.reverse(link, args=(allocation.pk,))
    # Escape the data inside while allowing our HTML to render
    data = mark_safe('<a href="%s">%s</a>'
                     '<br/>'
                     '<small class="muted">%s</small>' %
                     (escape(url),
                      escape(unicode(allocation.project_name)),
                      escape(unicode(allocation.project_description))))
    return data

def provisioned_yesno(allocation):
    if allocation.provisioned:
        return "Yes"
    else:
        return "No"

class AllocationListTable(tables.DataTable):
    status = tables.Column(status_icon,
                           verbose_name="State")
    provisioned = tables.Column(provisioned_yesno, verbose_name="Provisioned")
    project = tables.Column(allocation_title,
                            verbose_name="Name")
    contact = tables.Column("contact_email", verbose_name="Contact Email")
    modified_time = tables.Column("modified_time",
                                  verbose_name="Last Updated",
                                  filters=[lambda d: d.date()])
    end_date = tables.Column("end_date",
                             verbose_name="Expiry Date")

    class Meta:
        verbose_name = "Requests"
        table_actions = (tables.NameFilterAction,)
        row_actions = (EditRequest, ViewHistory,)


def delta_quota(allocation, want, have):
    if allocation.status in ('X', 'J'):
        return "%+d" % (int(want) - int(have))
    elif allocation.status == 'A':
        return have or '-'
    elif allocation.status in ('E', 'R'):
        return want or '-'
    return "Requested %s, currently have %s" % (want, have)


def get_quota(wanted, actual=None):
    def quota(allocation):
        want = getattr(allocation, wanted)
        have = getattr(allocation, actual, want)
        return delta_quota(allocation, want, have)
    return quota


def get_quota_by_resource(resource):
    def quota(allocation):
        want = 0
        have = 0
        for quota in \
            models.Quota.objects.filter(group__allocation=allocation,
                                        resource__quota_name=resource):
            want += quota.requested_quota
            have += quota.quota
        return delta_quota(allocation, want, have)
    return quota


class AllocationHistoryTable(tables.DataTable):
    project = tables.Column("project_description", verbose_name="Project name",
                            link="horizon:allocation:requests:allocation_view")
    approver = tables.Column("approver_email", verbose_name="Approver")
    instances = tables.Column(
        get_quota_by_resource("instances"),
        verbose_name="Instances")
    cores = tables.Column(
        get_quota_by_resource("cores"),
        verbose_name="Cores")
    object_store = tables.Column(
        get_quota_by_resource("object"),
        verbose_name="Object Storage")
    volume_storage = tables.Column(
        get_quota_by_resource("gigabytes"),
        verbose_name="Volume Storage")
    status = tables.Column("get_status_display", verbose_name="Status")
    modified_time = tables.Column(
        "modified_time", verbose_name="Modification time")

    class Meta:
        verbose_name = "Request History"
