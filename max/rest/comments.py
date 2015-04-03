# -*- coding: utf-8 -*-
from max.models import Activity
from max.rest import JSONResourceEntity
from max.rest import JSONResourceRoot
from max.rest import endpoint
from max.rest.utils import flatten
from max.rest.utils import searchParams
from max.security.permissions import add_comment
from max.security.permissions import delete_comment
from max.security.permissions import list_comments

from pyramid.httpexceptions import HTTPNoContent


@endpoint(route_name='user_comments', request_method='GET', permission=list_comments, requires_actor=True)
def getUserComments(user, request):
    """
        Return the all the comments generated by a user
    """
    query = {
        'object.objectType': 'comment',
        'verb': 'comment',
        'actor.username': user.username
    }
    is_head = request.method == 'HEAD'
    comments = request.db.activity.search(
        query,
        sort="_id",
        keep_private_fields=False,
        squash=['deletable', 'favorited', 'favorites', 'faavoritesCount'],
        flatten=1,
        count=is_head,
        **searchParams(request))

    handler = JSONResourceRoot(comments, stats=is_head)
    return handler.buildResponse()


@endpoint(route_name='activity_comments', request_method='GET', permission=list_comments, requires_actor=True)
def getActivityComments(activity, request):
    """
        /activities/{activity}/comments

        Return the comments for an activity.
    """
    replies = activity.get('replies', {})
    items = replies
    result = flatten(items, keep_private_fields=False)
    handler = JSONResourceRoot(result)
    return handler.buildResponse()


@endpoint(route_name='context_comments', request_method='GET', permission=list_comments, requires_actor=True)
def getContextComments(context, request):
    """
    """
    is_head = request.method == 'HEAD'

    query = {
        'verb': 'comment',
        'object.inReplyTo.contexts': {
            '$in': [context['hash']]
        }
    }

    comments = request.db.activity.search(query, flatten=1, count=is_head, **searchParams(request))
    handler = JSONResourceRoot(comments, stats=is_head)
    return handler.buildResponse()


@endpoint(route_name='comments', request_method='GET', permission=list_comments, requires_actor=True)
def getGlobalComments(comments, request):
    """
    """
    is_head = request.method == 'HEAD'
    activities = request.db.activity.search({'verb': 'comment'}, flatten=1, count=is_head, **searchParams(request))
    handler = JSONResourceRoot(activities, stats=is_head)
    return handler.buildResponse()


@endpoint(route_name='activity_comments', request_method='POST', permission=add_comment, requires_actor=True)
def addActivityComment(activity, request):
    """
        /activities/{activity}/comments

        Post a comment to an activity.
    """

    # Prepare rest parameters to be merged with post data
    rest_params = {
        'verb': 'comment',
        'object': {
            'inReplyTo': [{
                '_id': activity['_id'],
                'objectType': activity.object['objectType'],
                'contexts': []
            }]
        }
    }

    # Initialize a Activity object from the request
    newactivity = Activity.from_request(request, rest_params=rest_params)

    refering_activity_contexts = activity.get('contexts', [])
    if len(refering_activity_contexts) > 0:
        context_hashes = [ctxt['hash'] for ctxt in refering_activity_contexts]
        newactivity['object']['inReplyTo'][0]['contexts'] = context_hashes

    code = 201
    newactivity_oid = newactivity.insert()
    newactivity['_id'] = newactivity_oid

    comment = dict(newactivity.object)
    comment['published'] = newactivity.published
    comment['actor'] = request.actor
    comment['id'] = newactivity._id
    del comment['inReplyTo']
    activity.addComment(comment)

    handler = JSONResourceEntity(newactivity.flatten(), status_code=code)
    return handler.buildResponse()


@endpoint(route_name='activity_comment', request_method='DELETE', permission=delete_comment, requires_actor=True)
def deleteActivityComment(comment, request):
    """
    """
    comment.delete()
    return HTTPNoContent()
