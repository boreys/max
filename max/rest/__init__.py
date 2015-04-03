# -*- coding: utf-8 -*-
from pyramid.response import Response

import json
import venusian


class endpoint(object):
    """
        Custom decorator for max oauth2 endpoints
        Stolen from pyramid.view.view_config
    """
    venusian = venusian  # for testing injection

    def __init__(self, **settings):
        if 'for_' in settings:
            if settings.get('context') is None:
                settings['context'] = settings['for_']
        self.__dict__.update(settings)

    def __call__(self, wrapped):
        settings = self.__dict__.copy()
        depth = settings.pop('_depth', 0)

        def callback(context, name, ob):

            config = context.config.with_package(info.module)
            config.add_view(view=ob, **settings)

        # def max_wrapper(func):
        #     def replacement(*args, **kwargs):
        #         return func(*args, **kwargs)
        #     return replacement

        # # pre-decorate original method before passing it to venusian
        # rewrapped = max_wrapper(wrapped)

        # # patch decorated info to preserver name and doc
        # rewrapped.__name__ = wrapped.__name__
        # rewrapped.__doc__ = wrapped.__doc__

        # effectively apply the @endpoint decorator
        info = self.venusian.attach(wrapped, callback, category='max',
                                    depth=depth + 1)

        # # Modify codeinfo to preserver original wrapper method name
        # info.codeinfo = info.codeinfo[:-1] + ('@endpoint.{}'.format(wrapped.__name__),)

        if info.scope == 'class':
            # if the decorator was attached to a method in a class, or
            # otherwise executed at class scope, we need to set an
            # 'attr' into the settings if one isn't already in there
            if settings.get('attr') is None:
                settings['attr'] = wrapped.__name__

        settings['_info'] = info.codeinfo  # fbo "action_method"
        return wrapped


class JSONResourceRoot(object):
    """
    """
    response_content_type = 'application/json'

    def __init__(self, data, status_code=200, stats=False, remaining=False):
        """
        """
        self.data = data
        self.status_code = status_code
        self.stats = stats
        self.remaining = remaining
        self.headers = {}

    def wrap(self):
        """
        """
        wrapper = self.data
        return wrapper

    def buildResponse(self, payload=None):
        """
            Translate to JSON object if any data. If data is not a list
            something went wrong
        """

        if self.stats:
            response_payload = ''
            self.headers['X-totalItems'] = str(self.data)
        else:
            response_payload = json.dumps(self.wrap())

        if self.remaining:
            self.headers['X-Has-Remaining-Items'] = '1'

        data = response_payload is None and self.data or response_payload
        response = Response(data, status_int=self.status_code)
        response.content_type = self.response_content_type
        for key, value in self.headers.items():
            response.headers.add(key, value)
        return response


class JSONResourceEntity(object):
    """
    """
    response_content_type = 'application/json'

    def __init__(self, data, status_code=200):
        """
        """
        self.data = data
        self.status_code = status_code

    def buildResponse(self, payload=None):
        """
            Translate to JSON object if any data. If data is not a dict,
            something went wrong
        """
        response_payload = json.dumps(self.data)
        data = response_payload is None and self.data or response_payload
        response = Response(data, status_int=self.status_code)
        response.content_type = self.response_content_type

        return response
