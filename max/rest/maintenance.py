# -*- coding: utf-8 -*-
from max.models import Context
from max.models import Conversation
from max.exceptions import ObjectNotFound
from max.rest.ResourceHandlers import JSONResourceEntity
from max.rest.ResourceHandlers import JSONResourceRoot
from max.rest import endpoint
from max.security.permissions import do_maintenance
from bson import ObjectId

import logging
import re


logger = logging.getLogger('exceptions')


@endpoint(route_name='maintenance_keywords', request_method='POST', requires_actor=False, permission=do_maintenance)
def rebuildKeywords(context, request):
    """
         /maintenance/keywords

         Rebuild keywords of all activities

    """
    activities = request.db.activity.search({'verb': 'post'})
    for activity in activities:
        activity.object.setKeywords()
        activity.setKeywords()
        activity.save()

    handler = JSONResourceRoot([])
    return handler.buildResponse()


@endpoint(route_name='maintenance_dates', request_method='POST', requires_actor=False, permission=do_maintenance)
def rebuildDates(context, request):
    """
         /maintenance/dates

         Rebuild dates of activities
         Now currently sets the lastComment id field

    """
    activities = request.db.activity.search({'verb': 'post'})
    for activity in activities:
        # Remove ancient commented field
        if 'commented' in activity:
            del activity['commented']
        if activity.get('replies', []):
            activity['lastComment'] = ObjectId(activity['replies'][-1]['id'])
        activity.save()

    handler = JSONResourceRoot([])
    return handler.buildResponse()


@endpoint(route_name='maintenance_subscriptions', request_method='POST', requires_actor=False, permission=do_maintenance)
def rebuildSubscriptions(context, request):
    """
         /maintenance/subscriptions

         Rebuild subscriptions performing sanity checks

    """
    existing_contexts = {}
    contexts = request.db.contexts.dump()
    for context in contexts:
        context.updateUsersSubscriptions(force_update=True)
        context.updateContextActivities(force_update=True)
        existing_contexts[context['hash']] = context

    users = request.db.users.search({'subscribedTo.0': {'$exists': True}})
    for user in users:
        for subscription in user.get('subscribedTo', []):
            if subscription['hash'] not in existing_contexts:
                print user.username, subscription["displayName"]
                fake_deleted_context = Context.from_object(request, subscription)
                user.removeSubscription(fake_deleted_context)
            else:
                subscription.pop('vetos', None)
                subscription.pop('grants', None)
        user.save()
    handler = JSONResourceRoot([])
    return handler.buildResponse()


@endpoint(route_name='maintenance_conversations', request_method='POST', requires_actor=False, permission=do_maintenance)
def rebuildConversationSubscriptions(context, request):
    """
         /maintenance/conversations

         Rebuild conversation subscriptions performing sanity checks

    """
    existing_conversations = {}
    conversations = request.db.conversations.dump()
    for conversation in conversations:

        # if we found an ancient plain username list, we migrate it
        if True not in [isinstance(a, dict) for a in conversation['participants']]:
            conversation['participants'] = [{'username': a, 'displayName': a, 'objectType': 'person'} for a in conversation['participants']]

        conversation['tags'] = []
        # If we have less than two participants, we'll treat this conversation
        # as an archived group conversation
        if len(conversation['participants']) < 2:
            conversation['tags'].append('archive')
            conversation['tags'].append('group')
        # Conversations od 2+ get the group tag
        if len(conversation['participants']) > 2:
            conversation['tags'].append('group')

        # all the other conversations of 2, get no tag so will be
        # treated as two people conversations

        conversation.save()

        conversation.updateUsersSubscriptions(force_update=True)
        conversation.updateContextActivities(force_update=True)

        existing_conversations[str(conversation['_id'])] = conversation

    users = request.db.users.search({'talkingIn.0': {'$exists': True}})
    for user in users:
        for subscription in user.get('talkingIn', []):
            if subscription['id'] not in existing_conversations:
                fake_deleted_conversation = Conversation.from_object(request, subscription)
                user.removeSubscription(fake_deleted_conversation)
                user['talkingIn'] = [a for a in user['talkingIn'] if a['id'] != subscription['id']]
            else:
                # if subscription has an ancient plain username list, update and save it
                if True not in [isinstance(a, dict) for a in subscription['participants']]:
                    subscription['participants'] = existing_conversations[subscription['id']]['participants']
        user.updateConversationParticipants(force_update=True)
        user.save()
    handler = JSONResourceRoot([])
    return handler.buildResponse()


@endpoint(route_name='maintenance_users', request_method='POST', requires_actor=False, permission=do_maintenance)
def rebuildUser(context, request):
    """
         Rebuilds user objects with defaults and consistency checks.
         Currently checks that owner of the object must be the same user:
    """
    users = request.db.users.dump()
    for user in users:
        if user._owner != user.username:
            user._owner = user.username
            user.save()

    handler = JSONResourceRoot([])
    return handler.buildResponse()


@endpoint(route_name='maintenance_exception', request_method='GET', requires_actor=False, permission=do_maintenance)
def getException(context, request):
    """
         /maintenance/exceptions/{hash}

         Get an exception from the log
    """
    ehash = request.matchdict['hash']
    logfile = logger.handlers[0].baseFilename
    regex = r'BEGIN EXCEPTION REPORT: %s\nDATE: (.*?)\nREQUEST:\n\n(.*?)\n\nTRACEBACK:\n\n(.*?)\nEND EXCEPTION REPORT' % (ehash)
    match = re.search(regex, open(logfile).read(), re.DOTALL)
    if not match:
        raise ObjectNotFound("There is no logged exception with this hash")

    date, http_request, traceback = match.groups()

    result = {
        'date': date,
        'request': http_request,
        'traceback': traceback
    }
    handler = JSONResourceEntity(result)
    return handler.buildResponse()


@endpoint(route_name='maintenance_exceptions', request_method='GET', requires_actor=False, permission=do_maintenance)
def getExceptions(context, request):
    """
         /maintenance/exceptions

         Get exceptions list from the log
    """
    logfile = logger.handlers[0].baseFilename
    regex = r'BEGIN EXCEPTION REPORT: (\w+)\nDATE: (.*?)\n'
    matches = re.findall(regex, open(logfile).read(), re.DOTALL)
    exceptions = [{'id': exception_id, 'date': exception_date} for exception_id, exception_date in matches]

    handler = JSONResourceRoot(exceptions)
    return handler.buildResponse()
