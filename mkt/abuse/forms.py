from django import forms
from django.forms.models import modelformset_factory

import happyforms
from quieter_formset.formset import BaseModelFormSet

import mkt
from mkt.abuse.models import AbuseReport
from mkt.reviewers.models import ReviewerScore


class BaseAbuseViewFormSet(BaseModelFormSet):

    def __init__(self, *args, **kwargs):
        self.form = AbuseViewForm
        self.request = kwargs.pop('request', None)
        super(BaseAbuseViewFormSet, self).__init__(*args, **kwargs)

    def save(self):
        for form in self.forms:
            if form.cleaned_data:
                mark_read = form.cleaned_data.get('action', False)
                report = form.instance
                if mark_read:
                    report.read = True
                    report.save()
                    if report.addon:
                        mkt.log(mkt.LOG.APP_ABUSE_MARKREAD, report.addon,
                                report,
                                details=dict(
                                    body=unicode(report.message),
                                    addon_id=report.addon.id,
                                    addon_title=unicode(report.addon.name)))
                    elif report.user:
                        # Not possible on Marketplace currently.
                        pass
                    elif report.website:
                        # Not possible on Marketplace currently.
                        pass
                    if self.request:
                        ReviewerScore.award_abusereport_points(
                            self.request.user, report.id)


class AbuseViewForm(happyforms.ModelForm):

    action = forms.BooleanField(required=False, initial=False,
                                widget=forms.CheckboxInput(
                                    attrs={'hidden': 'true'}))

    class Meta:
        model = AbuseReport
        fields = ('action',)


AbuseViewFormSet = modelformset_factory(AbuseReport, extra=0,
                                        form=AbuseViewForm,
                                        formset=BaseAbuseViewFormSet)
