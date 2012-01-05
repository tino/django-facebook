import time

from django.utils.functional import SimpleLazyObject
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY
from django.core.cache import cache

import facebook

ACCESS_TOKEN_SESSION_KEY = '_fb_access_token'
ACCESS_TOKEN_EXPIRES_SESSION_KEY = '_fb_access_token_expires'

auth = facebook.Auth(settings.FACEBOOK_APP_ID, settings.FACEBOOK_APP_SECRET,
    settings.FACEBOOK_REDIRECT_URI)

FB_DATA_CACHE_KEY = '_fb_data_%s'


def get_access_token(request):
    def get_lazy():
        access_token = request.session.get(ACCESS_TOKEN_SESSION_KEY)
        expires = request.session.get(ACCESS_TOKEN_EXPIRES_SESSION_KEY)

        # two seconds buffer so we can actually do something with the token
        if expires < time.time() + 2:
            access_token, expires_in = get_fresh_access_token(request)
            request.session[ACCESS_TOKEN_SESSION_KEY] = access_token
            expires = time.time() + int(expires_in)
            request.session[ACCESS_TOKEN_EXPIRES_SESSION_KEY] = expires

        return access_token
    return SimpleLazyObject(get_lazy)


def get_fresh_access_token(request):
    """
    To get an access_token, we need a code. We can only get that from the
    fbsr_ cookie, or from the GET parameters that are returned in the server
    side flow.

    Raise an AuthError if we can get that code, or can't get an access_token.
    """
    code = None
    if 'code' in request.GET:
        code = request.GET['code']
        no_redirect_uri = False
    elif 'code' in get_fb_cookie_data(request):
        code = get_fb_cookie_data(request)['code']
        no_redirect_uri = True

    if not code:
        raise facebook.AuthError('OAuthException', 'Their is no code to get an'
            'access_token with. Reauthenticate the user')

    try:
        # freaking facebook doesn't want a redirect_uri is somebody is logged
        # in throught the client-side...
        kwargs = {'redirect_uri': ''} if no_redirect_uri else {}
        data = auth.get_access_token(code, **kwargs)
    except facebook.AuthError:
        raise

    return data['access_token'], data['expires']


def cache_access_token(request, access_token, expires_in):
    """Cache the access_token in the session"""
    request.session[ACCESS_TOKEN_SESSION_KEY] = access_token
    expires = time.time() + int(expires_in)
    request.session[ACCESS_TOKEN_EXPIRES_SESSION_KEY] = expires


def get_fb_cookie_data(request):
    """Cache parsed cookie data, so we only do it once per request."""
    if not hasattr(request, '_fb_cookie_data'):
        try:
            data = auth.get_user_from_cookie(request.COOKIES)
        except facebook.AuthError:
            data = {}
        request._fb_cookie_data = data
    return request._fb_cookie_data


def is_fb_logged_in(request):
    backendstr = 'django_facebook.auth.FacebookModelBackend'
    return request.user.is_authenticated() and \
        request.session.get(BACKEND_SESSION_KEY) == backendstr


class FacebookRequiredMixin(object):
    """CBV view mixin to display a facebook login template when the user is
    not logged in.
    """
    facebook_required_template = "facebook_required.html"

    def dispatch(self, request, *args, **kwargs):
        if not is_fb_logged_in(request):
            self.template_name = self.facebook_required_template
            self.request = request
            self.object = None
            return self.render_to_response({})
        return super(FacebookRequiredMixin, self).dispatch(request, *args, **kwargs)

def cache_fb_user_data(user_id, data):
    cache.set(FB_DATA_CACHE_KEY % user_id, data)
    
def get_cached_fb_user_data(user_id, default=None):
    return cache.get(FB_DATA_CACHE_KEY % user_id, default)