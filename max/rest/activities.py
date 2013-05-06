# -*- coding: utf-8 -*-
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotImplemented

from max.MADMax import MADMaxDB
from max.models import Activity
from max.decorators import MaxResponse, requirePersonActor
from max.oauth2 import oauth2
from max.exceptions import MissingField, ObjectNotFound

from max.rest.ResourceHandlers import JSONResourceRoot, JSONResourceEntity
from max.rest.utils import searchParams
import re


@view_config(route_name='user_activities', request_method='GET')
@MaxResponse
@oauth2(['widgetcli'])
@requirePersonActor
def getUserActivities(context, request):
    """
         /people/{username}/activities

         Return all activities generated by a user.
    """
    mmdb = MADMaxDB(context.db)
    query = {}
    query['actor.username'] = request.actor['username']
    query['verb'] = 'post'
    chash = request.params.get('context', None)
    if chash:
        query['contexts.hash'] = chash

    is_head = request.method == 'HEAD'
    activities = mmdb.activity.search(query, sort="_id", keep_private_fields=False, flatten=1, count=is_head, **searchParams(request))

    handler = JSONResourceRoot(activities, stats=is_head)
    return handler.buildResponse()


@view_config(route_name='user_activities', request_method='POST')
@MaxResponse
@oauth2(['widgetcli'])
@requirePersonActor
def addUserActivity(context, request):
    """
         /users/{username}/activities

         Adds an activity.
    """
    rest_params = {'actor': request.actor,
                   'verb': 'post'}

    # Initialize a Activity object from the request
    newactivity = Activity()
    newactivity.fromRequest(request, rest_params=rest_params)

    # New activity
    code = 201
    activity_oid = newactivity.insert()
    newactivity['_id'] = activity_oid

    handler = JSONResourceEntity(newactivity.flatten(), status_code=code)
    return handler.buildResponse()


@view_config(route_name='activities', request_method='GET')
@MaxResponse
@oauth2(['widgetcli'])
@requirePersonActor
def getActivities(context, request):
    """
         /activities

         Return all activities, filtered by context.
    """
    chash = request.params.get('context', None)
    if not chash:
        raise MissingField('You have to specify one context')

    mmdb = MADMaxDB(context.db)

    # subscribed Uri contexts with read permission
    subscribed_uris = [ctxt['url'] for ctxt in request.actor.subscribedTo.get('items', []) if 'read' in ctxt.get('permissions', []) and ctxt['objectType'] == 'context']

    # get the defined read context
    result_contexts = mmdb.contexts.getItemsByhash(chash)
    if result_contexts:
        rcontext = result_contexts[0]
    else:
        raise ObjectNotFound("Context with hash %s not found inside contexts" % (chash))
    url = rcontext['url']

    # regex query to find all contexts within url
    escaped = re.escape(url)
    url_regex = {'$regex': '^%s' % escaped}

    # search all contexts with public read permissions within url
    query = {'permissions.read': 'public', 'url': url_regex}
    public = [result.url for result in mmdb.contexts.search(query, show_fields=['url'])]

    query = {}                                                     # Search
    query.update({'verb': 'post'})                                 # 'post' activities
    query.update({'contexts.url': url_regex})                      # equal or child of url

    contexts_query = []
    if subscribed_uris:
        subscribed_query = {'contexts.url': {'$in': subscribed_uris}}  # that are subscribed contexts
        contexts_query.append(subscribed_query)                    # with read permission

    if public:                                                     # OR
        public_query = {'contexts.url': {'$in': public}}
        contexts_query.append(public_query)                        # pubic contexts

    if contexts_query:
        query.update({'$or': contexts_query})

        sortBy_fields = {
            'activities': '_id',
            'comments': 'commented',
        }
        sort_order = sortBy_fields[request.params.get('sortBy', 'activities')]
        activities = mmdb.activity.search(query, sort=sort_order, flatten=1, keep_private_fields=False, **searchParams(request))
    else:
        # we have no public contexts and we are not subscribed to any context, so we
        # won't get anything
        activities = []

    # pass the read context as a extension to the resource
    handler = JSONResourceRoot(activities, extension=dict(context=rcontext.flatten()))
    return handler.buildResponse()


@view_config(route_name='activity', request_method='GET')
@MaxResponse
@oauth2(['widgetcli'])
@requirePersonActor
def getActivity(context, request):
    """
         /activities/{activity}

         Returns an activity.
    """

    mmdb = MADMaxDB(context.db)
    activity_oid = request.matchdict['activity']
    activity = mmdb.activity[activity_oid].flatten()

    handler = JSONResourceEntity(activity)
    return handler.buildResponse()


@view_config(route_name='activity', request_method='DELETE')
def deleteActivity(context, request):
    """
    """
    return HTTPNotImplemented()


@view_config(route_name='activity', request_method='PUT')
def modifyActivity(context, request):
    """
    """
    return HTTPNotImplemented()
