# -*- coding: utf-8 -*-
from max.MADMax import MADMaxDB
from max.exceptions import Forbidden
from max.exceptions import ObjectNotFound
from max.models import Activity
from max.rest.ResourceHandlers import JSONResourceEntity
from max.rest.ResourceHandlers import JSONResourceRoot
from max.rest.utils import searchParams
from max.rest.sorting import sorted_query

from pyramid.httpexceptions import HTTPGone
from pyramid.httpexceptions import HTTPNoContent
from pyramid.httpexceptions import HTTPNotImplemented
from pyramid.response import Response
from pyramid.security import ACLAllowed
from max.rest import endpoint
from max.security.permissions import view_activities_unsubscribed, view_activities, add_activity, view_activity, modify_activity, delete_activity
from base64 import b64encode
from bson import ObjectId
from datetime import timedelta
import re


@endpoint(route_name='user_activities', request_method='GET', requires_actor=True, permission=view_activities)
def getUserActivities(user, request):
    """
         Return all activities generated by a user.
    """
    mmdb = MADMaxDB(request.db)
    query = {}
    query['actor.username'] = request.actor['username']
    query['verb'] = 'post'
    chash = request.params.get('context', None)
    if chash:
        query['contexts.hash'] = chash

    is_head = request.method == 'HEAD'
    activities = mmdb.activity.search(query, keep_private_fields=False, flatten=1, count=is_head, **searchParams(request))

    handler = JSONResourceRoot(activities, stats=is_head)
    return handler.buildResponse()


@endpoint(route_name='activities', request_method='GET', requires_actor=True, permission=view_activities)
def getGlobalActivities(context, request):
    """
    """
    mmdb = MADMaxDB(request.db)
    is_head = request.method == 'HEAD'
    activities = mmdb.activity.search({'verb': 'post'}, flatten=1, count=is_head, **searchParams(request))
    handler = JSONResourceRoot(activities, stats=is_head)
    return handler.buildResponse()


@endpoint(route_name='context_activities', request_method='GET', requires_actor=True, permission=view_activities)
def getContextActivities(context, request):
    """
         Returns all the activities posted on a context

         :rest hash The hash of the context url where the activties where posted
    """
    mmdb = MADMaxDB(request.db)
    url = context['url']

    # regex query to find all contexts within url
    escaped = re.escape(url)
    url_regex = {'$regex': '^%s' % escaped}

    # Search posts associated with contexts that have this context's
    # url as prefix a.k.a "recursive contexts"
    query = {}                                                     # Search
    query.update({'verb': 'post'})                                 # 'post' activities
    query.update({'contexts.url': url_regex})                      # equal or child of url

    contexts_query = []

    # Check if we have permission to unrestrictely view activities from recursive contexts:
    can_view_activities_unsubscribed = isinstance(request.has_permission(view_activities_unsubscribed), ACLAllowed)

    # If we can't view unsubcribed, filter from which contexts we get activities by listing
    # the contexts that the user has read permission on his subscriptions. Public contexts
    # will be added if this condition is met, as if we're unrestricted, main query already includes them all
    if not can_view_activities_unsubscribed:
        # XXX Filter subscriptions by url prefix PLEASE
        subscribed_uris = [ctxt['url'] for ctxt in request.actor.subscribedTo if 'read' in ctxt.get('permissions', []) and ctxt['objectType'] == 'context']
        if subscribed_uris:
            subscribed_query = {'contexts.url': {'$in': subscribed_uris}}
            contexts_query.append(subscribed_query)

        # We'll include also all contexts that are public whitin the url
        public_query = {'permissions.read': 'public', 'url': url_regex}
        public_contexts = [result.url for result in mmdb.contexts.search(public_query, show_fields=['url'])]

        if public_contexts:
            contexts_query.append({'contexts.url': {'$in': public_contexts}})

    if contexts_query:
        query.update({'$or': contexts_query})

    activities = sorted_query(request, mmdb.activity, query, flatten=1)

    if contexts_query or can_view_activities_unsubscribed:
        activities = sorted_query(request, mmdb.activity, query, flatten=1)
    else:
        # XXX Check in coverage as this probably don't raises ever, as the case of not having any subscription
        # is covered now by the permission in the view

        # Empty contexts_query means that we don't have any subsriptions to any recursive context
        # included the root one, so we really are not meant to see anything here
        raise Forbidden("You don't have permission to see anyting in this context and it's child")

    is_head = request.method == 'HEAD'
    handler = JSONResourceRoot(activities, stats=is_head)
    return handler.buildResponse()


@endpoint(route_name='context_activities', request_method='POST', requires_actor=True, permission=add_activity)
def addContextActivity(context, request):
    """
         /contexts/{hash}/activities

         Adds an activity associated with a context.

         If an actor is found on the request body it will be taken as the ownership of the activity, either
         the actor being a Person or a Context. If no actor specified on json payload, the current authenticated
         user will be taken as request.actor.
    """
    rest_params = {
        'verb': 'post',
        'contexts': [
            context
        ]
    }
    # Initialize a Activity object from the request
    newactivity = Activity()
    newactivity.fromRequest(request, rest_params=rest_params)

    # Search if there's any activity from the same user with
    # the same actor in the last minute

    actor_id_key = 'actor.{}'.format(request.actor.unique)
    actor_id_value = request.actor.get(request.actor.unique)

    query = {
        actor_id_key: actor_id_value,
        'object.content': newactivity['object']['content'],
        'published': {'$gt': newactivity.published - timedelta(minutes=1)},
        'contexts.hash': context.hash
    }

    mmdb = MADMaxDB(request.db)
    duplicated = mmdb.activity.search(query)

    if duplicated:
        code = 200
        newactivity = duplicated[0]
    else:
        # New activity
        code = 201
        if newactivity['object']['objectType'] == u'image' or \
           newactivity['object']['objectType'] == u'file':
            # Extract the file before saving object
            activity_file = newactivity.extract_file_from_activity()
            activity_oid = newactivity.insert()
            newactivity['_id'] = ObjectId(activity_oid)
            newactivity.process_file(request, activity_file)
            newactivity.save()
        else:
            activity_oid = newactivity.insert()
            newactivity['_id'] = activity_oid

    handler = JSONResourceEntity(newactivity.flatten(squash=['keywords']), status_code=code)
    return handler.buildResponse()


@endpoint(route_name='user_activities', request_method='POST', requires_actor=True, permission=add_activity)
def addUserActivity(user, request):
    """
         /people/{username}/activities

         Add activity posted as {username}. User in url will be taken as the actor that will own
         the activity. When url {username} and authenticated user don't match, user must have special
         permissions to be able to impersoate the activity.

    """
    rest_params = {'actor': request.actor,
                   'verb': 'post'}

    # Initialize a Activity object from the request
    newactivity = Activity()
    newactivity.fromRequest(request, rest_params=rest_params)

    # Search if there's any activity from the same user with
    # the same actor and without context
    mmdb = MADMaxDB(request.db)
    query = {
        'actor.username': request.actor.username,
        'object.content': newactivity['object'].get('content', ''),
        'published': {'$gt': newactivity.published - timedelta(minutes=1)},
        'contexts': {'$exists': False}
    }

    duplicated = mmdb.activity.search(query)

    if duplicated:
        code = 200
        newactivity = duplicated[0]
    else:
        # New activity
        code = 201
        if newactivity['object']['objectType'] == u'image' or \
           newactivity['object']['objectType'] == u'file':
            # Extract the file before saving object
            activity_file = newactivity.extract_file_from_activity()
            activity_oid = newactivity.insert()
            newactivity['_id'] = ObjectId(activity_oid)
            newactivity.process_file(request, activity_file)
            newactivity.save()
        else:
            activity_oid = newactivity.insert()
            newactivity['_id'] = activity_oid

    handler = JSONResourceEntity(newactivity.flatten(squash=['keywords']), status_code=code)
    return handler.buildResponse()


@endpoint(route_name='activity', request_method='GET', requires_actor=True, permission=view_activity)
def getActivity(activity, request):
    """
         Returns a single activity

         :rest activity The id of the activity
    """
    handler = JSONResourceEntity(activity.flatten())
    return handler.buildResponse()


@endpoint(route_name='activity', request_method='PUT', requires_actor=True, permission=modify_activity)
def modifyActivity(activity, request):
    """
    """
    return HTTPNotImplemented()  # pragma: no cover


@endpoint(route_name='activity', request_method='DELETE', requires_actor=True, permission=delete_activity)
def deleteActivity(activity, request):
    """
         Deletes a single activity

         :rest activity The id of the activity
    """
    activity.delete()
    return HTTPNoContent()


@endpoint(route_name='activity_image', request_method='GET', requires_actor=True, permission=view_activity)
@endpoint(route_name='activity_image_sizes', request_method='GET', requires_actor=True, permission=view_activity)
def getActivityImageAttachment(activity, request):
    """
        Returns an image from the local repository.

        :rest activity The id of the activity
        :rest size The named size of the activity, defaults to large
    """

    file_size = request.matchdict.get('size', 'full')
    image, mimetype = activity.getImage(size=file_size)

    if image is not None:
        if request.headers.get('content-type', '') == 'application/base64':
            image = b64encode(image)
            mimetype = 'application/base64'

        response = Response(image, status_int=200)
        response.content_type = mimetype
    else:
        response = HTTPGone()

    return response


@endpoint(route_name='activity_file_download', request_method='GET', requires_actor=True, permission=view_activity)
def getActivityFileAttachment(activity, request):
    """
        Returns a file from the local repository.

        :rest activity The id of the activity
    """
    file_data, mimetype = activity.getFile()

    if file_data is not None:
        response = Response(file_data, status_int=200)
        response.content_type = mimetype
        filename = activity['object'].get('filename', activity['_id'])
        response.headers.add('Content-Disposition', 'attachment; filename={}'.format(filename))
    else:
        response = HTTPGone()

    return response
