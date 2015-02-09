import hashlib
import logging

import facebook
from django.contrib.auth import authenticate
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured

import conf
from .auth import login, logout
from .utils import (FB_DATA_CACHE_KEY, get_lazy_access_token,
                    get_signed_request_data, is_fb_logged_in)

log = logging.getLogger('django_facebook.middleware')


class FacebookAccessor(object):
    """
    Simple accessor object for the Facebook user. Non-existing properties
    will return None instead of raising a AttributeError.
    """

    def __init__(self, request):
        self.auth = conf.auth
        if is_fb_logged_in(request):
            self.user_id = request.user.get_username()
            self.access_token = get_lazy_access_token(request)
            self.graph = facebook.GraphAPI(self.access_token)

    def __getattr__(self, name):
        return None


class FacebookLoginMiddleware(object):
    """
    Transparently integrate Django accounts with Facebook. You need to add
    ``auth.FacebookModelBackend`` to ``AUTHENTICATION_BACKENDS`` for this to
    work.

    Logging in works only if ``{cookie: true}`` is passed to ``FB.init`` (by
    default when using the ``facebook_init`` template tag.

    We also allow people to log in with other backends, so we only log someone
    in if they are not already logged in.
    """
    def __init__(self, force_validate=False):
        self.force_validate = force_validate

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The FacebookCookieLoginMiddleware requires the"
                " authentication middleware to be installed. Edit your"
                " MIDDLEWARE_CLASSES setting and insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the FacebookLoginMiddleware class.")

        if request.user.is_anonymous() and conf.COOKIE_NAME in request.COOKIES:
            user = authenticate(request=request,
                                force_validate=self.force_validate)
            if user:
                login(request, user)


class FacebookLogOutMiddleware(object):
    """
    When a user logs out of facebook (on our page!), we won't get notified,
    but the fbsr_ cookies wil be cleared. So this middleware checks if that
    cookie is still present, and if not, logs the user out.

    This works only if the user is logged in with the
    ``auth.FacebookModelBackend``.
    """

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The FacebookLogOutMiddleware requires the"
                " authentication middleware to be installed. Edit your"
                " MIDDLEWARE_CLASSES setting and insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the FacebookLogOutMiddleware class.")

        if is_fb_logged_in(request):

            if not request.COOKIES.get(conf.COOKIE_NAME):
                logout(request)
                log.debug('User logged out, no fbsr_ cookie found')
                return

            data = get_signed_request_data(request)
            if data and data['user_id'] != request.user.username:
                # Also logout if the fb session changes
                logout(request)
                log.debug('User logged out. User_id on server differs from client side')


class FacebookHelperMiddleware(object):
    """
    This middleware sets the ``facebook`` attribute on the request, which
    contains the user id and a graph accessor.
    """

    def process_request(self, request):
        request.facebook = FacebookAccessor(request)


class FacebookCacheMiddleware(object):
    """
    This middleware loads tries to load user data from the cache. If found, it
    populates request.facebook with it.

    This middleware MUST come after the FacebookHelperMiddleware!
    """

    def process_request(self, request):
        if request.facebook.user_id:
            fb_data = cache.get(FB_DATA_CACHE_KEY % request.facebook.user_id)
            if fb_data:
                for k, v in fb_data.iteritems():
                    setattr(request.facebook, k, v)


class FacebookMiddleware(object):
    """
    This middleware implements the basic behaviour:

    - Log someone in if we can authenticate them (see ``auth``)
    - Log someone out if we can't authenticate them anymore
    - Add a ``facebook`` attribute to the request with a graph accessor.
    """
    def process_request(self, request):
        FacebookHelperMiddleware().process_request(request)
        FacebookLogOutMiddleware().process_request(request)
        FacebookLoginMiddleware().process_request(request)


class FacebookDebugCanvasMiddleware(object):
    """
    Emulates signed_request behaviour to test your applications embedding.

    This should be a raw string as is sent from facebook to the server in the
    POST data, obtained by LiveHeaders, Firebug or similar. This should be
    initialised before FacebookMiddleware.

    """

    def process_request(self, request):
        cp = request.POST.copy()
        request.POST = cp
        request.POST['signed_request'] = conf.DEBUG_SIGNEDREQ
        return None


class FacebookDebugCookieMiddleware(object):
    """
    Sets an imaginary cookie to make it easy to work from a development
    environment.

    This should be a raw string as is sent from a browser to the server,
    obtained by LiveHeaders, Firebug or similar. The middleware takes care of
    naming the cookie correctly. This should initialised before
    FacebookCookieLoginMiddleware.

    """

    def process_request(self, request):
        request.COOKIES[conf.COOKIE_NAME] = conf.DEBUG_COOKIE
        return None


class FacebookDebugTokenMiddleware(object):
    """
    Forces a specific access token to be used.

    This should be used instead of FacebookMiddleware. Make sure you have
    FACEBOOK_DEBUG_UID and FACEBOOK_DEBUG_TOKEN set in your configuration.

    """

    def process_request(self, request):
        request.facebook = FacebookAccessor(request)
        request.facebook.user_id = conf.DEBUG_UID
        request.facebook.access_token = conf.DEBUG_TOKEN
        return None
