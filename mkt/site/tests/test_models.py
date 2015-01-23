from django.conf import settings

import multidb.pinning
from mock import Mock
from nose import SkipTest
from nose.tools import eq_, ok_

from mkt.site import models
from mkt.site.models import manual_order
from mkt.site.tests import app_factory, TestCase
from mkt.webapps.models import Webapp


def test_ordering():
    """Given a specific set of primary keys, assure that we return addons
    in that order."""

    app1id = app_factory().id
    app2id = app_factory().id
    app3id = app_factory().id
    semi_arbitrary_order = [app2id, app3id, app1id]
    addons = manual_order(Webapp.objects.all(), semi_arbitrary_order)
    eq_(semi_arbitrary_order, [addon.id for addon in addons])


def test_skip_cache():
    ok_(hasattr(models._locals, 'skip_cache'))
    eq_(getattr(models._locals, 'skip_cache'),
        not settings.CACHE_MACHINE_ENABLED)
    models._locals.skip_cache = False
    with models.skip_cache():
        eq_(models._locals.skip_cache, True)
        with models.skip_cache():
            eq_(models._locals.skip_cache, True)
        eq_(models._locals.skip_cache, True)
    eq_(models._locals.skip_cache, False)


def test_use_master():
    multidb.pinning.unpin_this_thread()
    local = models.multidb.pinning._locals
    eq_(getattr(local, 'pinned', False), False)
    with models.use_master():
        eq_(local.pinned, True)
        with models.use_master():
            eq_(local.pinned, True)
        eq_(local.pinned, True)
    eq_(local.pinned, False)


class TestModelBase(TestCase):

    def setUp(self):
        self.saved_cb = models._on_change_callbacks.copy()
        models._on_change_callbacks.clear()
        self.cb = Mock()
        self.cb.__name__ = 'testing_mock_callback'
        Webapp.on_change(self.cb)
        self.testapp = app_factory(public_stats=True)

    def tearDown(self):
        models._on_change_callbacks = self.saved_cb

    def test_multiple_ignored(self):
        cb = Mock()
        cb.__name__ = 'something'
        old = len(models._on_change_callbacks[Webapp])
        Webapp.on_change(cb)
        eq_(len(models._on_change_callbacks[Webapp]), old + 1)
        Webapp.on_change(cb)
        eq_(len(models._on_change_callbacks[Webapp]), old + 1)

    def test_change_called_on_new_instance_save(self):
        # Broken by the extra update() in Webapp.save when creating.
        # When bug 1036900 is implemented remove SkipTest.
        raise SkipTest
        for create_addon in (Webapp, Webapp.objects.create):
            addon = create_addon(public_stats=False)
            addon.public_stats = True
            addon.save()
            assert self.cb.called
            kw = self.cb.call_args[1]
            eq_(kw['sender'], Webapp)
            eq_(kw['instance'].id, addon.id)
            eq_(kw['old_attr']['public_stats'], False)
            eq_(kw['new_attr']['public_stats'], True)

    def test_change_called_on_update(self):
        addon = self.testapp
        addon.update(public_stats=False)
        assert self.cb.called
        kw = self.cb.call_args[1]
        eq_(kw['old_attr']['public_stats'], True)
        eq_(kw['new_attr']['public_stats'], False)
        eq_(kw['instance'].id, addon.id)
        eq_(kw['sender'], Webapp)

    def test_change_called_on_save(self):
        addon = self.testapp
        addon.public_stats = False
        addon.save()
        assert self.cb.called
        kw = self.cb.call_args[1]
        eq_(kw['old_attr']['public_stats'], True)
        eq_(kw['new_attr']['public_stats'], False)
        eq_(kw['instance'].id, addon.id)
        eq_(kw['sender'], Webapp)

    def test_change_is_not_recursive(self):

        class fn:
            called = False

        def callback(old_attr=None, new_attr=None, instance=None,
                     sender=None, **kw):
            fn.called = True
            # Both save and update should be protected:
            instance.update(public_stats=False)
            instance.save()

        Webapp.on_change(callback)

        addon = self.testapp
        addon.save()
        assert fn.called
        # No exception = pass

    def test_safer_get_or_create(self):
        data = {'guid': '123'}
        a, c = Webapp.objects.safer_get_or_create(**data)
        assert c
        b, c = Webapp.objects.safer_get_or_create(**data)
        assert not c
        eq_(a, b)

    def test_deleted_updated(self):
        addon = self.testapp
        addon.delete()
        addon.update(public_stats=False)
        assert not addon.public_stats, 'addon.public_stats should be False now.'


def test_cache_key():
    # Test that we are not taking the db into account when building our
    # cache keys for django-cache-machine. See bug 928881.
    eq_(Webapp._cache_key(1, 'default'), Webapp._cache_key(1, 'slave'))
