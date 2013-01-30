# -*- coding: utf-8 -*-
import os
import json

from paste.deploy import loadapp
from mock import patch

from max.tests.base import MaxTestBase, oauth2Header
from max.tests import test_manager, test_default_security


class mock_post(object):

    def __init__(self, *args, **kwargs):
        pass

    text = ""
    status_code = 200


@patch('requests.post', new=mock_post)
class FunctionalTests(MaxTestBase):

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

    def test_create_user(self):
        username = 'messi'
        self.testapp.post('/people/%s' % username, "", oauth2Header(test_manager), status=201)

    def test_create_user_not_manager(self):
        username = 'messi'
        self.testapp.post('/people/%s' % username, "", oauth2Header('imnotallowed'), status=401)

    def test_get_all_users_admin(self):
        username = 'messi'
        self.create_user(username)
        res = self.testapp.get('/admin/people', "", oauth2Header(test_manager))
        result = json.loads(res.text)
        self.assertEqual(result.get('totalItems', None), 1)
        self.assertEqual(result.get('items', None)[0].get('username'), 'messi')

    def test_user_exist(self):
        username = 'messi'
        self.create_user(username)
        res = self.testapp.post('/people/%s' % username, "", oauth2Header(test_manager), status=200)
        result = json.loads(res.text)
        self.assertEqual(result.get('username', None), 'messi')

    def test_get_user(self):
        username = 'messi'
        self.create_user(username)
        res = self.testapp.get('/people/%s' % username, "", oauth2Header(username))
        result = json.loads(res.text)
        self.assertEqual(result.get('username', None), 'messi')

    def test_get_user_not_me(self):
        username = 'messi'
        username_not_me = 'xavi'
        self.create_user(username)
        self.create_user(username_not_me)
        res = self.testapp.get('/people/%s' % username_not_me, "", oauth2Header(username), status=401)
        result = json.loads(res.text)
        self.assertEqual(result.get('error', None), 'Unauthorized')

    def test_get_non_existent_user(self):
        username = 'messi'
        res = self.testapp.get('/people/%s' % username, "", oauth2Header(username), status=400)
        result = json.loads(res.text)
        self.assertEqual(result.get('error', None), 'UnknownUserError')

    def test_modify_user_one_parameter(self):
        username = 'messi'
        self.create_user(username)
        res = self.testapp.put('/people/%s' % username, json.dumps({"displayName": "Lionel Messi"}), oauth2Header(username))
        result = json.loads(res.text)
        self.assertEqual(result.get('displayName', None), 'Lionel Messi')

    def test_modify_user_several_parameters(self):
        username = 'messi'
        self.create_user(username)
        res = self.testapp.put('/people/%s' % username, json.dumps({"displayName": "Lionel Messi", "twitterUsername": "leomessi"}), oauth2Header(username))
        result = json.loads(res.text)
        self.assertEqual(result.get('displayName', None), 'Lionel Messi')
        self.assertEqual(result.get('twitterUsername', None), 'leomessi')

    def test_modify_user_several_parameters_twice(self):
        username = 'messi'
        self.create_user(username)
        self.modify_user(username, {"displayName": "Lionel Messi"})
        res = self.testapp.put('/people/%s' % username, json.dumps({"twitterUsername": "leomessi"}), oauth2Header(username))
        result = json.loads(res.text)
        self.assertEqual(result.get('displayName', None), 'Lionel Messi')
        self.assertEqual(result.get('twitterUsername', None), 'leomessi')

    def test_modify_non_existent_user(self):
        username = 'messi'
        res = self.testapp.put('/people/%s' % username, json.dumps({"displayName": "Lionel Messi"}), oauth2Header(username), status=400)
        result = json.loads(res.text)
        self.assertEqual(result.get('error', None), 'UnknownUserError')

    def test_get_all_users(self):
        username = 'messi'
        self.create_user(username)
        res = self.testapp.get('/people', json.dumps({"username": username}), oauth2Header(username), status=200)
        result = json.loads(res.text)

        self.assertEqual(result.get('totalItems', ''), 1)
        self.assertEqual(result.get('items', '')[0].get('username', ''), username)
        self.assertEqual(len(result.get('items', '')[0].keys()), 2)

    def test_get_all_users_with_regex(self):
        username = 'usuarimoltllarg'
        self.create_user(username)
        query = {'username': 'usuarimoltll'}
        res = self.testapp.get('/people', json.dumps(query), oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result.get('items', '')[0].get('username', ''), username)

        query = {'username': 'usuarimo'}
        res = self.testapp.get('/people', json.dumps(query), oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result.get('items', '')[0].get('username', ''), username)

    def test_get_all_users_with_regex_weird(self):
        username1 = 'victor.fernandez'
        self.create_user(username1)
        username2 = 'victor.fernandez.altable'
        self.create_user(username2)

        query = {'username': username1}
        res = self.testapp.get('/people', query, oauth2Header(username1), status=200)
        result = json.loads(res.text)
        self.assertEqual(len(result.get('items', '')), 2)

        query = {'username': username2}
        res = self.testapp.get('/people', query, oauth2Header(username2), status=200)
        result = json.loads(res.text)
        self.assertEqual(len(result.get('items', '')), 1)