# -*- coding: utf-8 -*-

from zope.interface import implementer

from max.exceptions import Unauthorized
from max.resources import getMAXSettings
from max.security import Owner, is_owner, get_user_roles

from pyramid.interfaces import IAuthenticationPolicy
from pyramid.security import Authenticated
from pyramid.security import Everyone
from pyramid.settings import asbool

from beaker.cache import cache_region

import requests


@cache_region('oauth_token')
def check_token(url, username, token, scope, oauth_standard):
    """
        Checks if a user matches the given token.
    """
    payload = {"access_token": token, "username": username}
    payload['scope'] = scope if scope else 'widgetcli'
    return requests.post(url, data=payload, verify=False).status_code == 200


@implementer(IAuthenticationPolicy)
class MaxAuthenticationPolicy(object):
    """
        Pyramid authentication policy against OAuth2 provided on headers
        and principals stored on database.
    """
    def __init__(self, allowed_scopes):
        self.allowed_scopes = allowed_scopes
        self._authenticated_userid = ''
        self._effective_principals = []

    # Helper methods

    def _validate_user(self, request):
        """
            Extracts and validates user from the request.

            Performs several checks that will result on Unauthorized
            exceptions if failed. At the end the successfully authenticated
            username is returned.

        """
        oauth_token, username, scope = request.auth_headers

        if scope not in self.allowed_scopes:
            raise Unauthorized('The specified scope is not allowed for this resource.')

        settings = getMAXSettings(request)
        valid = check_token(
            settings['max_oauth_check_endpoint'],
            username, oauth_token, scope,
            asbool(settings.get('max_oauth_standard', True)))

        if not valid:
            raise Unauthorized('Invalid token.')

        request.__authenticated_userid__ = username
        return username

    def _get_principals(self, request):
        """
            Calculates the identities that can be used
            when authorizing the user
        """
        principals = [Everyone, Authenticated, request.authenticated_userid]
        if is_owner(request.context, request.authenticated_userid):
            principals.append(Owner)

        principals.extend(get_user_roles(request, request.authenticated_userid))
        request.__effective_principals__ = principals
        return principals

    # IAuthenticationPolicy Implementation

    def authenticated_userid(self, request):
        """
            Returns the oauth2 authenticated user.

            On first acces, user is extracted from Oauth headers and validated. Extracted
            user id is cached to future accesses to the property
        """
        try:
            return request.__authenticated_userid__
        except AttributeError:
            return self._validate_user(request)

    def unauthenticated_userid(self, request):
        """
            DUP of authenticated_userid
        """
        return self.authenticated_userid   # pragma: no cover

    def effective_principals(self, request):
        """
            Returns
        """
        try:
            return request.__effective_principals__
        except AttributeError:
            return self._get_principals(request)

    def remember(self, request, principal, **kw):
        """ Not used neither needed """
        return []  # pragma: no cover

    def forget(self, request):
        """ Not used neither needed"""
        return []  # pragma: no cover
