# -*- coding: utf-8 -*-
from pyramid.view import view_config

from max.MADMax import MADMaxDB
from max.rest.ResourceHandlers import JSONResourceRoot
from max.decorators import MaxResponse, requirePersonActor
from max.oauth2 import oauth2
from max.rest.utils import searchParams


@view_config(route_name='timeline', request_method='GET')
@MaxResponse
@requirePersonActor
@oauth2(['widgetcli'])
def getUserTimeline(context, request):
    """
         /people/{username}/timeline

         Retorna totes les activitats d'un usuari
    """
    actor = request.actor
    is_context_resource = 'timeline/contexts' in request.path
    is_follows_resource = 'timeline/follows' in request.path

    mmdb = MADMaxDB(context.db)

    actor_query = {'actor.username': actor['username']}

    # Add the activity of the people that the user follows
    actors_followings = []
    for following in actor['following']['items']:
        followed_person = mmdb.users.getItemsByusername(following['username'])[0]
        if followed_person:
            actors_followings.append({'actor._id': followed_person['_id']})

    # Add the activity of the people that posts to a particular context
    contexts_followings = []
    for subscribed in actor['subscribedTo']['items']:
        # Don't show conversations in timeline
        if subscribed['object']['objectType'] not in ['conversation']:
            contexts_followings.append({'contexts.object.url': subscribed['object']['url']})

    query_items = []

    if not is_follows_resource and not is_context_resource:
        query_items.append(actor_query)
        query_items += actors_followings
        query_items += contexts_followings

    if is_context_resource:
        query_items += contexts_followings

    if is_follows_resource:
        query_items += contexts_followings

    if query_items:
        query = {'$or': query_items}
        query['verb'] = 'post'
        # Exclude messages from timeline
        query['object.objectType'] = {'$ne': 'message'}
        # Include only visible activity, this includes activity with visible=True
        # and activity WITHOUT the visible field
        query['visible'] = {'$ne': False}

        sortBy_fields = {
            'activities': '_id',
            'comments': 'commented',
        }
        sort_order = sortBy_fields[request.params.get('sortBy', 'activities')]
        activities = mmdb.activity.search(query, sort=sort_order, flatten=1, keep_private_fields=False, **searchParams(request))
    else:
        activities = []

    handler = JSONResourceRoot(activities)
    return handler.buildResponse()
