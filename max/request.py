# -*- coding: utf-8 -*-
from max.MADMax import MADMaxDB
import json
from bson import json_util
from hashlib import sha1


def extract_post_data(request):
    """
        Try to extract json encoded post data, dealing with the different situations that we can
        encounter.

        1. Requests may come as multipart/form-data, in which case we will lookup the json payload
           on a "json_data" post parameter. When on this situation, we could find image/file uploads
           that will be injected on json data to normalize the processing in other layers.

        2. Requests on any other format, that contains a body, will be tried to decode as json. Json
           payloads may contain a dict {} or a list{}.

        All other situations or errors during extraction will return an empty dict {}.
    """
    json_data = {}

    if 'multipart/form-data' in request.content_type:
        try:
            json_data = json.loads(request.params.get('json_data'), object_hook=json_util.object_hook)
            if json_data.get('object', {}).get('objectType', '') in ['file', 'image']:
                json_data['object']['file'] = request.params.get('file')
        except:
            pass

    elif 'multipart/form-data' not in request.content_type and request.body:
        # Usually look for JSON encoded body, catch the case it does not contain
        # valid JSON data, e.g when uploading a file
        try:
            json_data = json.loads(request.body, object_hook=json_util.object_hook)
        except:
            pass

    return json_data


# Methods used to extract username from different parts of the request

def get_username_in_oauth(request):
    """
        Extracts the username from the Oauth authentication headers.

        Returns None if no headers found
    """
    return request.headers.get('X-Oauth-Username', None)


def get_username_in_uri(request):
    """
        Extracts a lowercased username from the REST uri parameter {username}.

        Returns None if parameter not found
    """
    username = request.matchdict.get('username', '')
    return username.lower() if username else None


def get_username_in_body(request):
    """
        Extracts username from request body on POST and PUT requests.

        Username may be in the form of {'username': 'value'} or as a actor actions
        {'actor': {'username': 'value'}}. The latter will be choosen if the two are found.

        Returns None if any user found on body
    """
    if request.method in ['POST', 'PUT']:
        decoded_data = extract_post_data(request)
        if not isinstance(decoded_data, dict):
            return None

        plain_username = decoded_data.get('username', None)
        actor_username = decoded_data.get('actor', {}).get('username', None)
        return actor_username if actor_username else plain_username
    return None


# Methods used to create cached request properties

def get_request_actor_username(request):
    """
        Determine and return the actor of the request.

        The actor MAY not be the same as the authenticated user. Actor in fact, is the user
        that gets registered as the one that has performed an activity, so specifying a different
        actor than the authenticated user is usefull to perform actions as other user, but mantaining
        the real authorship, that will remain immutable in the creator property.

        To determine it, username is looked up in different locations, and the effective
        username will be the last found in the following chain

        1. Username found in oauth headers
        2. Username found in the URI
        3. Username found in the POST/PUT body
    """

    def set_username(username, source):
        """
            Changes the username for the one in source method, avoiding variable references
        """
        new_username = source(request)
        if new_username:
            return str(new_username)
        else:
            return username

    username = set_username('', get_username_in_oauth)
    username = set_username(username, get_username_in_uri)
    username = set_username(username, get_username_in_body)

    return username


def get_context_author_url(request):
    """
        Determine and return the url of the context specified as actor
    """

    actor = extract_post_data(request).get('actor', {})
    return actor.get('url', '')


def get_request_actor(request):
    """
        Retrieves the User object or the Context from the database matching the actor
        found in the request. If a context author is found, will override any person
        actor
    """
    context_actor_url = get_context_author_url(request)
    if context_actor_url:
        try:
            url_hash = sha1(context_actor_url).hexdigest()
            mmdb = MADMaxDB(request.registry.max_store)
            actor = mmdb.contexts.getItemsByhash(url_hash)[0]
            actor.setdefault('displayName', actor['username'])
            return actor
        except:
            return None

    username = get_request_actor_username(request)
    try:
        mmdb = MADMaxDB(request.registry.max_store)
        actor = mmdb.users.getItemsByusername(username)[0]
        actor.setdefault('displayName', actor['username'])
        return actor
    except:
        return None


def get_request_creator(request):
    """
        Returns the authenticated user, to be used as the creator of objects
    """
    return get_username_in_oauth(request)


def get_authenticated_user_roles(request):
    """
        Gets the roles owned by the current authenticated user
    """
    username = get_username_in_oauth(request)
    security = request.registry.max_security
    user_roles = [role for role, users in security.get("roles", {}).items() if username in users]
    return user_roles + ['Authenticated']


def get_database(request):
    """
        Returns the global database object
    """
    return request.registry.max_store