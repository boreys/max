# -*- coding: utf-8 -*-
from max import AUTHORS_SEARCH_MAX_QUERIES_LIMIT
from max import LAST_AUTHORS_LIMIT
from max.MADMax import MADMaxCollection
from max.MADMax import MADMaxDB
from max.decorators import MaxResponse
from max.exceptions import ObjectNotFound
from max.exceptions import Unauthorized
from max.exceptions import ValidationError
from max.models import Context
from max.oauth2 import oauth2
from max.rest.ResourceHandlers import JSONResourceEntity
from max.rest.ResourceHandlers import JSONResourceRoot
from max.rest.utils import extractPostData
from max.rest.utils import flatten
from max.rest.utils import searchParams
from max.rest.sorting import sorted_query
from max.security.permissions import add_context
from max.security.permissions import delete_context
from max.security.permissions import list_contexts
from max.security.permissions import list_public_contexts
from max.security.permissions import modify_context
from max.security.permissions import view_context
from max.security.permissions import view_context_activity

from pyramid.httpexceptions import HTTPNoContent
from max.rest import endpoint


@endpoint(route_name='contexts', request_method='GET', permission=list_contexts, user_required=True)
def getContexts(context, request):
    """
    """
    mmdb = MADMaxDB(context.db)
    found_contexts = mmdb.contexts.search({}, flatten=1, **searchParams(request))
    handler = JSONResourceRoot(found_contexts)
    return handler.buildResponse()


@endpoint(route_name='contexts', request_method='POST', permission=add_context, user_required=True)
def addContext(context, request):
    """
        /contexts

        Adds a context.
    """
    request.actor = None

    # Initialize a Context object from the request
    newcontext = Context()
    newcontext.fromRequest(request)

    # If we have the _id setted, then the object already existed in the DB,
    # otherwise, proceed to insert it into the DB
    # In both cases, respond with the JSON of the object and the appropiate
    # HTTP Status Code

    if newcontext.get('_id'):
        # Already Exists
        code = 200
    else:
        # New context
        code = 201
        contextid = newcontext.insert()
        newcontext['_id'] = contextid

    handler = JSONResourceEntity(newcontext.flatten(), status_code=code)
    return handler.buildResponse()


@endpoint(route_name='context', request_method='GET', permission=view_context, user_required=True)
def getContext(context, request):
    """
        /contexts/{hash}

        [RESTRICTED] Return a context by its hash.
    """
    mmdb = MADMaxDB(context.db)
    chash = request.matchdict.get('hash', None)
    found_context = mmdb.contexts.getItemsByhash(chash)

    if not found_context:
        raise ObjectNotFound("There's no context matching this url hash: %s" % chash)

    handler = JSONResourceEntity(found_context[0].getInfo())
    return handler.buildResponse()


@endpoint(route_name='context', request_method='PUT', permission=modify_context, user_required=True)
def ModifyContext(context, request):
    """
        /contexts/{hash}

        Modify the given context.
    """
    properties = context.getMutablePropertiesFromRequest(request)
    context.modifyContext(properties)
    context.updateUsersSubscriptions()
    context.updateContextActivities()
    handler = JSONResourceEntity(context.flatten())
    return handler.buildResponse()


@endpoint(route_name='context', request_method='DELETE', permission=delete_context, user_required=True)
def DeleteContext(context, request):
    """
    """
    mmdb = MADMaxDB(context.db)
    chash = request.matchdict.get('hash', None)
    found_contexts = mmdb.contexts.getItemsByhash(chash)

    if not found_contexts:
        raise ObjectNotFound("There's no context matching this url hash: %s" % chash)

    ctx = found_contexts[0]
    ctx.removeUserSubscriptions()
    ctx.removeActivities(logical=True)
    ctx.delete()
    return HTTPNoContent()


@endpoint(route_name='context_tags', request_method='GET', permission=view_context, user_required=True)
def getContextTags(context, request):
    """
    """
    chash = request.matchdict['hash']
    contexts = MADMaxCollection(context.db.contexts, query_key='hash')
    context = contexts[chash]
    handler = JSONResourceRoot(context.tags)
    return handler.buildResponse()


@endpoint(route_name='context_tags', request_method='DELETE', permission=modify_context, user_required=True)
def clearContextTags(context, request):
    """
    """
    chash = request.matchdict['hash']
    contexts = MADMaxCollection(context.db.contexts, query_key='hash')
    context = contexts[chash]
    context.tags = []
    context.save()
    context.updateContextActivities(force_update=True)
    context.updateUsersSubscriptions(force_update=True)
    handler = JSONResourceRoot([])
    return handler.buildResponse()


@endpoint(route_name='context_tags', request_method='PUT', permission=modify_context, user_required=True)
def updateContextTags(context, request):
    """
    """
    chash = request.matchdict['hash']
    tags = extractPostData(request)

    # Validate tags is a list of strings
    valid_tags = isinstance(tags, list)
    if valid_tags:
        valid_tags = False not in [isinstance(tag, (str, unicode)) for tag in tags]
    if not valid_tags:
        raise ValidationError("Sorry, We're expecting a list of strings...")

    contexts = MADMaxCollection(context.db.contexts, query_key='hash')
    context = contexts[chash]
    context.tags.extend(tags)
    context.tags = list(set(context.tags))
    context.save()
    context.updateContextActivities(force_update=True)
    context.updateUsersSubscriptions(force_update=True)
    handler = JSONResourceRoot(context.tags)
    return handler.buildResponse()


@endpoint(route_name='context_tag', request_method='DELETE', permission=modify_context, user_required=True)
@MaxResponse
@oauth2(['widgetcli'])
def removeContextTag(context, request):
    """
    """
    chash = request.matchdict['hash']
    tag = request.matchdict['tag']
    contexts = MADMaxCollection(context.db.contexts, query_key='hash')
    context = contexts[chash]

    try:
        context.tags.remove(tag)
    except ValueError:
        raise ObjectNotFound('This context has no tag "{}"'.format(tag))

    context.save()
    context.updateContextActivities(force_update=True)
    context.updateUsersSubscriptions(force_update=True)
    return HTTPNoContent()


@endpoint(route_name='public_contexts', request_method='GET', permission=list_public_contexts, user_required=True)
def getPublicContexts(context, request):
    """
        /contexts/public

        Return a list of public-subscribable contexts
    """
    mmdb = MADMaxDB(context.db)
    found_contexts = mmdb.contexts.search({'permissions.subscribe': 'public'}, **searchParams(request))

    handler = JSONResourceRoot(flatten(found_contexts, squash=['owner', 'creator', 'published']))
    return handler.buildResponse()


@endpoint(route_name='context_activities_authors', request_method='GET', permission=view_context_activity, user_required=True)
def getContextAuthors(context, request):
    """
        /contexts/{hash}/activities/authors
    """
    chash = request.matchdict['hash']
    mmdb = MADMaxDB(context.db)
    actor = request.actor
    author_limit = int(request.params.get('limit', LAST_AUTHORS_LIMIT))

    is_subscribed = chash in [subscription['hash'] for subscription in actor.subscribedTo]

    is_manager = 'Manager' in request.roles
    if not is_subscribed and not is_manager:
        raise Unauthorized("You're not allowed to access this context")

    query = {}
    query['contexts.hash'] = chash
    query['verb'] = 'post'
    # Include only visible activity, this includes activity with visible=True
    # and activity WITHOUT the visible field
    query['visible'] = {'$ne': False}

    still_has_activities = True

    # Save full author object to construct de response
    # and a separate username field to make the uniquefication easier
    distinct_authors = []
    distinct_usernames = []

    activities = []
    before = None
    queries = 0

    while len(distinct_usernames) < author_limit and still_has_activities and queries <= AUTHORS_SEARCH_MAX_QUERIES_LIMIT:
        if not activities:
            extra = {'before': before} if before else {}
            activities = sorted_query(request, mmdb.activity, query, **extra)
            activities_count = activities if isinstance(activities, int) else len(activities)
            queries += 1
            still_has_activities = activities_count > 0
        if still_has_activities:
            activity = activities.pop(0)
            before = activity._id
            if activity.actor['username'] not in distinct_usernames:
                distinct_authors.append(activity.actor)
                distinct_usernames.append(activity.actor['username'])
    handler = JSONResourceRoot(distinct_authors)
    return handler.buildResponse()
