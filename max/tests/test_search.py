# -*- coding: utf-8 -*-
import os
import json

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

    def test_activities_keyword_generation(self):
        """
                Tests that all words passing regex are included in _keywords
                Tests that username that creates the activity is included in keywords
                Tests that a keyword of a comment is included in keywords
        """
        from .mockers import create_context
        from .mockers import subscribe_context, user_status_context, user_comment

        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='public', write='subscribed', join='restricted', invite='restricted'))
        self.subscribe_user_to_context(username, subscribe_context)
        res = self.create_activity(username, user_status_context)
        activity = json.loads(res.text)
        res = self.testapp.post('/activities/%s/comments' % str(activity.get('id')), json.dumps(user_comment), oauth2Header(username), status=201)
        res = self.testapp.get('/activities/%s' % str(activity.get('id')), json.dumps({}), oauth2Header(username), status=200)
        result = json.loads(res.text)
        expected_keywords = [u'comentari', u'messi', u'creaci\xf3', u'testejant', u'canvi', u'una', u'nou', u'activitat']
        self.assertListEqual(result['object']['_keywords'], expected_keywords)

    def test_activities_hashtag_generation(self):
        """
                Tests that all hashtags passing regex are included in _hashtags
                Tests that a hashtag of a comment is included in hashtags
        """
        from .mockers import create_context
        from .mockers import subscribe_context, user_status_context_with_hashtag, user_comment_with_hashtag

        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='public', write='subscribed', join='restricted', invite='restricted'))
        self.subscribe_user_to_context(username, subscribe_context)
        res = self.create_activity(username, user_status_context_with_hashtag)
        activity = json.loads(res.text)
        res = self.testapp.post('/activities/%s/comments' % str(activity.get('id')), json.dumps(user_comment_with_hashtag), oauth2Header(username), status=201)
        res = self.testapp.get('/activities/%s' % str(activity.get('id')), json.dumps({}), oauth2Header(username), status=200)
        result = json.loads(res.text)
        expected_hashtags = [u'canvi', u'comentari', u'nou']
        self.assertListEqual(result['object']['_hashtags'], expected_hashtags)

    def test_context_activities_keyword_search(self):
        """
        """
        from .mockers import context_query_kw_search
        from .mockers import create_context
        from .mockers import subscribe_context, user_status_context

        username = 'messi'
        self.create_user(username)
        self.create_context(create_context, permissions=dict(read='public', write='subscribed', join='restricted', invite='restricted'))
        self.subscribe_user_to_context(username, subscribe_context)
        self.create_activity(username, user_status_context)

        res = self.testapp.get('/activities', context_query_kw_search, oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result.get('totalItems', None), 1)

    def test_context_activities_author_search(self):
        """
        """
        from .mockers import context_query_author_search
        from .mockers import create_context
        from .mockers import subscribe_context, user_status_context

        username = 'messi'
        self.create_user(username)
        username2 = 'xavi'
        self.create_user(username2)
        self.create_context(create_context, permissions=dict(read='public', write='subscribed', join='restricted', invite='restricted'))
        self.subscribe_user_to_context(username, subscribe_context)
        self.subscribe_user_to_context(username2, subscribe_context)
        self.create_activity(username, user_status_context)
        self.create_activity(username, user_status_context)
        self.create_activity(username2, user_status_context)

        res = self.testapp.get('/activities', context_query_author_search, oauth2Header(username), status=200)
        result = json.loads(res.text)
        self.assertEqual(result.get('totalItems', None), 2)
        self.assertEqual(result.get('items', None)[0].get('actor', None).get('username'), 'messi')
        self.assertEqual(result.get('items', None)[1].get('actor', None).get('username'), 'messi')