# -*- coding: utf-8 -*-
import re
import json
from hashlib import sha1

people_resource_matcher = re.compile(r'/people/([^\/]+)$').search
people_subscriptions_resource_matcher = re.compile(r'/people/([^\/]+)/subscriptions$').search
people_subscription_resource_matcher = re.compile(r'/people/([^\/]+)/subscriptions/([^\/]+)$').search
people_activities_resource_matcher = re.compile(r'/people/([^\/]+)/activities$').search


def get_body(request, default=dict):
    """
        Extracts the request body, expecting a value of the same type
        as the default. If the default value doesn't match this requirement
        the default is returned.
    """
    try:
        replacement_body = json.loads(request.body)
    except:
        replacement_body = default()
    else:
        if not isinstance(replacement_body, default):
            replacement_body = default()

    return replacement_body


def fix_deprecated_create_user(request, match):
    """
        Adapts the deprecated way to create an user.

        Requests matching:

            POST /people/{user}

        will be transformed into:

            POST /people

        Username will be injected into the json body
        overwriting any username specified, but preserving
        any other user attribute
    """
    username = match.groups()[0]
    replacement_body = get_body(request)
    replacement_body['username'] = username
    request.body = json.dumps(replacement_body)
    request.path_info = '/people'

    # Force headers needed to avoid body content quoting on tests
    request.headers['Content-Type'] = 'application/json'


def fix_deprecated_subscribe_user(request, match):
    """
        Adapts the deprecated way to subscribe an user to a context

        Requests matching:

            POST /people/{user}/subscriptions

        will be transformed into:

            POST /contexts/{hash}/subscriptions

        Hash will be extracted from the url on the json body,
        and a actor parameter will be injected into the json body,
        using username found in the url.

        In the case that body doesn't contain a context to post to
        it will be interpretated as a regular user timeline post, and remain
        untouched
    """
    username = match.groups()[0]
    replacement_body = get_body(request)
    obj = replacement_body.pop('object', {})
    object_url = obj.get('url', None)
    url_hash = sha1(object_url).hexdigest() if object_url else ''
    new_path = '/contexts/{}/subscriptions'.format(url_hash)
    request.path_info = new_path

    replacement_body.update({
        "actor": {
            "objectType": "person",
            "username": username
        }
    })

    request.body = json.dumps(replacement_body)

    # Force headers needed to avoid body content quoting on tests
    request.headers['Content-Type'] = 'application/json'


def fix_deprecated_unsubscribe_user(request, match):
    """
        Adapts the deprecated way to unsubscribe an user to a context

        Requests matching:

            DELETE /people/{username}/subscriptions/{hash}

        will be transformed into:

            DELETE /contexts/{hash}/subscriptions/{username}

        There are no substancial changes, only a simple rewrite of the url.
    """
    username = match.groups()[0]
    chash = match.groups()[1]

    new_path = '/contexts/{}/subscriptions/{}'.format(chash, username)
    request.path_info = new_path

    # Force headers needed to avoid body content quoting on tests
    request.headers['Content-Type'] = 'application/json'


def fix_deprecated_create_context_activity(request, match):
    """

        Adapts the deprecated way to post an activity to a context,
        when the actor is a Person

        Requests matching:

            POST /people/{username}/activities

        will be transformed into:

            POST /contexts/{hash}/activities

        Hash will be extracted from the url on the json body,
        and a actor parameter will be injected into the json body,
        using username found in the url
    """
    username = match.groups()[0]
    replacement_body = get_body(request)
    contexts = replacement_body.pop('contexts', {})
    if contexts:
        context = contexts[0]
        context_url = context.get('url', None)
        url_hash = sha1(context_url).hexdigest() if context_url else ''
        new_path = '/contexts/{}/activities'.format(url_hash)
        request.path_info = new_path

        replacement_body.update({
            "actor": {
                "objectType": "person",
                "username": username
            }
        })

        request.body = json.dumps(replacement_body)

        # Force headers needed to avoid body content quoting on tests
        request.headers['Content-Type'] = 'application/json'


def check_deprecation(request, pattern, action):
    """
        Applies a deprecation fix
    """
    match = pattern(request.path_info)
    if match:
        action(request, match)
        return True

# PLEASE! Construct depreaction list sorted by matching frequency, so deprecations expected
# to happen more frequently that others go first. This is to minimize the number of deprecations tested

POST_DEPRECATIONS = [
    (people_activities_resource_matcher, fix_deprecated_create_context_activity),
    (people_subscriptions_resource_matcher, fix_deprecated_subscribe_user),
    (people_resource_matcher, fix_deprecated_create_user)
]

DELETE_DEPRECATIONS = [
    (people_subscription_resource_matcher, fix_deprecated_unsubscribe_user),
]
