# -*- coding: utf-8 -*-
import os
import json
import unittest
from hashlib import sha1

from mock import patch
from paste.deploy import loadapp

from max.tests.base import MaxTestBase, oauth2Header
from max.tests import test_manager, test_default_security


class mock_post(object):

    def __init__(self, *args, **kwargs):
        pass

    text = ""
    status_code = 200


@patch('requests.post', new=mock_post)
class FunctionalTests(unittest.TestCase, MaxTestBase):

    def setUp(self):
        conf_dir = os.path.dirname(__file__)
        self.app = loadapp('config:tests.ini', relative_to=conf_dir)
        self.app.registry.max_store.drop_collection('users')
        self.app.registry.max_store.drop_collection('activity')
        self.app.registry.max_store.drop_collection('contexts')
        self.app.registry.max_store.drop_collection('security')
        self.app.registry.max_store.security.insert(test_default_security)
        from webtest import TestApp
        self.testapp = TestApp(self.app)

    # BEGIN TESTS

    def test_subscribe_user_to_context(self):
        from .mockers import create_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='public', write='restricted', subscribe='restricted', invite='restricted'))
        self.testapp.post('/admin/people/%s/subscriptions' % username, json.dumps(create_context), oauth2Header(test_manager), status=201)

    def test_subscribe_to_context(self):
        """ doctest .. http:post:: /people/{username}/subscriptions """
        from .mockers import subscribe_context
        from .mockers import user_status_context
        from .mockers import create_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context)
        self.admin_subscribe_user_to_context(username, subscribe_context)
        res = self.create_activity(username, user_status_context)
        result = json.loads(res.text)
        self.assertEqual(result.get('actor', None).get('username', None), 'messi')
        self.assertEqual(result.get('object', None).get('objectType', None), 'note')
        self.assertEqual(result.get('contexts', None)[0]['object'], subscribe_context['object'])

    def test_subscribe_to_context_already_subscribed(self):
        from .mockers import subscribe_context
        from .mockers import user_status_context
        from .mockers import create_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context)
        self.admin_subscribe_user_to_context(username, subscribe_context)
        self.admin_subscribe_user_to_context(username, subscribe_context, expect=200)
        res = self.create_activity(username, user_status_context)
        result = json.loads(res.text)
        self.assertEqual(result.get('actor', None).get('username', None), 'messi')
        self.assertEqual(result.get('object', None).get('objectType', None), 'note')
        self.assertEqual(result.get('contexts', None)[0]['object'], subscribe_context['object'])

    def test_subscribe_to_inexistent_context(self):
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        res = self.admin_subscribe_user_to_context(username, subscribe_context, expect=404)
        result = json.loads(res.text)
        self.assertEqual(result.get('error', None), 'ObjectNotFound')

    def test_get_all_subscribed_contexts_for_user(self):
        """ doctest .. http:get:: /people/{username}/subscriptions """
        from .mockers import create_context
        from .mockers import subscribe_contextA, create_contextA
        from .mockers import subscribe_contextB, create_contextB
        username = 'messi'
        username_not_me = 'xavi'
        self.create_user(username)
        self.create_user(username_not_me)
        self.create_context(create_context, permissions=dict(read='public', write='restricted', subscribe='restricted', invite='restricted'))
        self.create_context(create_contextA, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
        self.create_context(create_contextB, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
        self.admin_subscribe_user_to_context(username, subscribe_contextA)
        self.admin_subscribe_user_to_context(username_not_me, subscribe_contextA)
        self.admin_subscribe_user_to_context(username, subscribe_contextB)

        res = self.testapp.get('/people/%s/subscriptions' % username, "", oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result.get('totalItems'), 2)
        self.assertEqual(result.get('items')[0].get('object').get('url'), 'http://atenea.upc.edu/A')
        self.assertEqual(result.get('items')[1].get('object').get('url'), 'http://atenea.upc.edu/B')

    def test_get_subscriptions_from_another_user(self):
        """
            As a plain user
            When I try to get another user subscriptions list
            Then i get an authorization error
        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        username2 = 'xavi'
        self.create_user(username2)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
        self.admin_subscribe_user_to_context(username, subscribe_context, expect=201)
        self.testapp.get('/people/%s/subscriptions' % username, {}, oauth2Header(username2), status=401)

    def test_subcribe_to_restricted_context_as_plain_user(self):
        """
            As a plain user
            When I subscribe to a public subscription context
            Then i get an authorization error
        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
        self.user_subscribe_user_to_context(username, subscribe_context, expect=401)

    def test_subscribe_to_public_context_as_plain_user(self):
        """
            As a plain user
            When I subscribe to a public subscription context
            Then the subscription is created
            And I will be able to unsubscribe in the future
        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', join='public', invite='restricted'))
        self.user_subscribe_user_to_context(username, subscribe_context, expect=201)
        res = self.testapp.get('/people/%s/subscriptions' % username, {}, oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertIn('unsubscribe', result['items'][0]['permissions'])

    # def test_list_all_public_subcribtable_contexts(self):
    #     """
    #         Create one public context and a restricted one, then list the contexts filtered by join permission=public
    #     """
    #     from .mockers import create_context, create_contextA
    #     username = 'messi'
    #     self.create_user(username)
    #     self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', join='public', invite='restricted'))
    #     self.create_context(create_contextA, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
    #     res = self.testapp.get('/contexts/public' % username, {}, oauth2Header(username), status=200)
    #     result = json.loads(res.text)

    def test_unsubscribe_from_inexistent_subscription_as_plain_user(self):
        """
            As a plain user
            When I try to unsubscribe from a context
            And I'm not subscribed to that context
            Then I get a not found error
        """
        from .mockers import create_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='public', invite='restricted'))
        url_hash = sha1(create_context['object']['url']).hexdigest()
        self.testapp.delete('/people/%s/subscriptions/%s' % (username, url_hash), {}, oauth2Header(username), status=404)

    def test_unsubscribe_from_inexistent_subscription_as_admin(self):
        """
            As an admin user
            When I try to unsubscribe a user from a context
            And the user is not subscribed to that context
            Then I get a not found error
        """
        from .mockers import create_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='public', invite='restricted'))
        url_hash = sha1(create_context['object']['url']).hexdigest()
        self.testapp.delete('/admin//people/%s/subscriptions/%s' % (username, url_hash), {}, oauth2Header(test_manager), status=404)

    def test_unsubscribe_from_restricted_context_as_plain_user(self):
        """
            As a plain user
            When I try to unsubscribe from a restricted subscription context
            Then i get an authorization error
        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
        self.admin_subscribe_user_to_context(username, subscribe_context, expect=201)
        url_hash = sha1(create_context['object']['url']).hexdigest()
        self.testapp.delete('/people/%s/subscriptions/%s' % (username, url_hash), {}, oauth2Header(username), status=401)

    def test_unsubscribe_from_restricted_context_as_admin(self):
        """
            As a admin user
            When I try to unsubscribe a plain user from a restricted subscription context
            Then the user is not subscribed to the context anymore
        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
        self.admin_subscribe_user_to_context(username, subscribe_context, expect=201)
        url_hash = sha1(create_context['object']['url']).hexdigest()
        self.testapp.delete('/admin/people/%s/subscriptions/%s' % (username, url_hash), {}, oauth2Header(test_manager), status=204)
        res = self.testapp.get('/people/%s/subscriptions' % username, {}, oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result['totalItems'], 0)

    def test_unsubscribe_from_public_context_as_plain_user(self):
        """
            As a plain user
            When I try to unsubscribe from a public subscription context
            Then I am not subscribed to the context anymore

        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='public', invite='restricted'))
        self.user_subscribe_user_to_context(username, subscribe_context, expect=201)
        url_hash = sha1(create_context['object']['url']).hexdigest()
        self.user_unsubscribe_user_from_context(username, url_hash, expect=204)
        res = self.testapp.get('/people/%s/subscriptions' % username, {}, oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result['totalItems'], 0)

    def test_unsubscribe_from_public_context_as_admin(self):
        """
            As a admin user
            When I try to unsubscribe a plain user from a public subscription context
            Then I am not subscribed to the context anymore
        """
        from .mockers import create_context
        from .mockers import subscribe_context
        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='public', invite='restricted'))
        self.user_subscribe_user_to_context(username, subscribe_context, expect=201)
        url_hash = sha1(create_context['object']['url']).hexdigest()
        self.admin_unsubscribe_user_from_context(username, url_hash, expect=204)
        res = self.testapp.get('/people/%s/subscriptions' % username, {}, oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result['totalItems'], 0)

    # def test_change_public_context_to_restricted(self):
    #     """
    #         Create a public context, user subscribes to context.
    #         Change the context to join=restricted, and user fails to remove his subscription
    #     """
    #     from .mockers import create_context
    #     from .mockers import subscribe_context
    #     username = 'messi'
    #     self.create_user(username)
    #     self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', join='public', invite='restricted'))
    #     self.user_subscribe_user_to_context(username, subscribe_context, expect=200)
    #     self.user_unsubscribe_user_from_context(username, subscribe_context, expect=401)

    # def test_change_restricted_context_to_public(self):
    #     """
    #         Create a restricted context, admin subscribes the user to context.
    #         Change the context to join=public, and user successfully removes himself from context
    #     """
    #     from .mockers import create_context
    #     from .mockers import subscribe_context
    #     username = 'messi'
    #     self.create_user(username)
    #     self.create_context(create_context, permissions=dict(read='subscribed', write='subscribed', subscribe='restricted', invite='restricted'))
    #     self.admin_subscribe_user_to_context(username, subscribe_context, expect=200)
    #     self.user_unsubscribe_user_from_context(username, subscribe_context, expect=200)
