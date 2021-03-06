# -*- coding: utf-8 -*-
from max.tests import test_default_security
from max.tests import test_manager
from max.tests.base import MaxTestApp
from max.tests.base import MaxTestBase
from max.tests.base import mock_post
from max.tests.base import oauth2Header

from functools import partial
from mock import patch
from paste.deploy import loadapp

import json
import os
import unittest


class FunctionalTests(unittest.TestCase, MaxTestBase):

    def setUp(self):
        conf_dir = os.path.dirname(__file__)
        self.app = loadapp('config:tests.ini', relative_to=conf_dir)
        self.reset_database(self.app)
        self.app.registry.max_store.security.insert(test_default_security)
        self.patched_post = patch('requests.post', new=partial(mock_post, self))
        self.patched_post.start()
        self.testapp = MaxTestApp(self)

        self.create_user(test_manager)

    def tearDown(self):
        import pyramid.testing
        pyramid.testing.tearDown()

    # BEGIN TESTS

    def test_add_device_token_ios(self):
        username = 'messi'
        token = {'platform': 'ios', 'token': '12345678901234567890123456789012'}
        self.create_user(username)
        res = self.testapp.post('/tokens', json.dumps(token), oauth2Header(username), status=201)
        result = json.loads(res.text)
        self.assertEqual(result.get('token', ''), token['token'])
        self.assertEqual(result.get('platform', ''), token['platform'])

    def test_add_device_token_android(self):
        username = 'messi'
        self.create_user(username)
        token = {'platform': 'android', 'token': '12345678901234567890123456789012klhsdflajshdfkjashdfoq'}
        res = self.testapp.post('/tokens', json.dumps(token), oauth2Header(username), status=201)
        result = json.loads(res.text)
        self.assertEqual(result.get('token', ''), token['token'])
        self.assertEqual(result.get('platform', ''), token['platform'])

    def test_add_device_invalid_platform(self):
        username = 'messi'
        token = {'platform': 'blackberry', 'token': '12345678901234567890123456789012klhsdflajshdfkjashdfoq'}
        self.create_user(username)
        self.testapp.post('/tokens', json.dumps(token), oauth2Header(username), status=400)

    def test_delete_device_token(self):
        username = 'messi'
        token = {'platform': 'ios', 'token': '12345678901234567890123456789012'}

        self.create_user(username)
        self.testapp.post('/tokens', json.dumps(token), oauth2Header(username), status=201)
        self.testapp.delete('/tokens/%s' % (token['token']), "", oauth2Header(username), status=204)

    def test_add_duplicated_token(self):
        """
            Given i'm a regular user

        """
        sender = 'messi'
        recipient = 'xavi'
        self.create_user(sender)
        self.create_user(recipient)

        token = {'platform': 'ios', 'token': '12345678901234567890123456789012'}

        self.testapp.post('/tokens', json.dumps(token), oauth2Header(sender), status=201)
        sender_tokens = self.testapp.get('/people/{}/tokens/platforms/{}'.format(sender, token['platform']), "", headers=oauth2Header(sender), status=200).json

        self.assertEqual(len(sender_tokens), 1)
        self.testapp.post('/tokens', json.dumps(token), oauth2Header(recipient), status=201)

        sender_tokens = self.testapp.get('/people/{}/tokens/platforms/{}'.format(sender, token['platform']), "", headers=oauth2Header(sender), status=200).json
        recipient_tokens = self.testapp.get('/people/{}/tokens/platforms/{}'.format(recipient, token['platform']), "", headers=oauth2Header(recipient), status=200).json

        self.assertEqual(len(sender_tokens), 0)
        self.assertEqual(len(recipient_tokens), 1)

    def test_get_pushtokens_for_given_conversations(self):
        """ doctest .. http:get:: /conversations/{id}/tokens """
        from .mockers import message
        sender = 'messi'
        recipient = 'xavi'
        self.create_user(sender)
        self.create_user(recipient)

        platform = 'ios'
        token_sender = '12345678901234567890123456789012'
        token_recipient = '12345678901234567890123456789013'
        self.testapp.post('/people/%s/device/%s/%s' % (sender, platform, token_sender), "", oauth2Header(sender), status=201)
        self.testapp.post('/people/%s/device/%s/%s' % (recipient, platform, token_recipient), "", oauth2Header(recipient), status=201)

        res = self.testapp.post('/conversations', json.dumps(message), oauth2Header(sender), status=201)
        conversation_id = res.json['contexts'][0]['id']

        res = self.testapp.get('/conversations/%s/tokens' % (conversation_id), '', oauth2Header(test_manager), status=200)
        self.assertEqual(res.json[0]['platform'], u'ios')
        self.assertEqual(res.json[0]['token'], u'12345678901234567890123456789013')
        self.assertEqual(res.json[0]['username'], u'xavi')

        self.assertEqual(res.json[1]['platform'], u'ios')
        self.assertEqual(res.json[1]['token'], u'12345678901234567890123456789012')
        self.assertEqual(res.json[1]['username'], u'messi')
        self.assertEqual(len(res.json), 2)

    def test_get_pushtokens_for_given_context(self):
        """
        """
        from .mockers import create_context, subscribe_context
        username = 'messi'
        username2 = 'xavi'
        self.create_user(username)
        self.create_user(username2)

        platform = 'ios'
        token_1 = '12345678901234567890123456789012'
        token_2 = '12345678901234567890123456789013'
        self.testapp.post('/people/%s/device/%s/%s' % (username, platform, token_1), "", oauth2Header(username), status=201)
        self.testapp.post('/people/%s/device/%s/%s' % (username2, platform, token_2), "", oauth2Header(username2), status=201)

        url_hash = self.create_context(create_context).json['hash']
        self.admin_subscribe_user_to_context(username, subscribe_context)

        res = self.testapp.get('/contexts/%s/tokens' % (url_hash), '', oauth2Header(test_manager), status=200)
        self.assertEqual(res.json[0]['platform'], u'ios')
        self.assertEqual(res.json[0]['token'], u'12345678901234567890123456789012')
        self.assertEqual(res.json[0]['username'], u'messi')
        self.assertEqual(len(res.json), 1)
