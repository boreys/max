from max.exceptions import Unauthorized
import requests


def oauth2(allowed_scopes=[]):
    def wrap(view_function):

        def new_function(*args, **kw):
            request = args[0]

            # Extract the username and token from request headers
            # It will be like:
            # headers = {"X-Oauth-Token":"jfa1sDF2SDF234", "X-Oauth-Username":"victor.fernandez", "X-Oauth-Scope"="widgetcli"}

            oauth_token = request.headers.get('X-Oauth-Token', '')
            username = request.headers.get('X-Oauth-Username', '')
            scope = request.headers.get('X-Oauth-Scope', '')

            if not oauth_token or not username:
                raise Unauthorized, 'No auth headers found.'

            if allowed_scopes:
                if scope not in allowed_scopes:
                    raise Unauthorized, 'The specified scope is not allowed for this resource.'

            # Validate access token
            payload = {"oauth_token": oauth_token,
                       "username": username,
                       }
            if scope:
                payload['scope'] = scope

            r = requests.post('https://oauth.upc.edu/checktoken', data=payload, verify=False)

            if r.status_code == 200:
                # Valid token, proceed.
                return view_function(*args, **kw)
            else:
                raise Unauthorized, 'Invalid token.'

        new_function.__doc__ = view_function.__doc__
        return new_function
    return wrap