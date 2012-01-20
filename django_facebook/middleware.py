from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import authenticate
from django.contrib.auth import BACKEND_SESSION_KEY
from django.core.cache import cache

import logging
log = logging.getLogger('django_facebook.middleware')

import facebook

from django_facebook.auth import login, logout
from django_facebook.utils import (get_lazy_access_token, is_fb_logged_in, 
    FB_DATA_CACHE_KEY)

auth = facebook.Auth(settings.FACEBOOK_APP_ID,
    settings.FACEBOOK_APP_SECRET, settings.FACEBOOK_REDIRECT_URI)

class FacebookAccessor(object):
    """ Simple accessor object for the Facebook user. Non-existing properties 
    will return None instead of raising a AttributeError."""

    def __init__(self, request):
        if is_fb_logged_in(request):
            self.user_id = request.user.username

        self.access_token = get_lazy_access_token(request)
        self.auth = auth
        self.graph = facebook.GraphAPI(self.access_token)
        
    def __getattr__(self, name):
        return None


class FacebookLoginMiddleware(object):
    """
    Transparently integrate Django accounts with Facebook. You need to add
    ``auth.FacebookModelBackend`` to ``AUTHENTICATION_BACKENDS`` for this to
    work.

    If the djfb_ cookies are set on the client side by our javascript, we
    want them to be automatically be logged in as that user. We rely on the
    authentication backend to create the user if it does not exist.

    If you do not want to persist the facebook login, also enable
    FacebookLogOutMiddleware so that if they log out log out on the client-side
    they will also be logged out in the backend.

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
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the FacebookLoginMiddleware class.")

        if request.user.is_anonymous():
            user = authenticate(request=request,
                                force_validate=self.force_validate)
            if user:
                login(request, user)


class FacebookLogOutMiddleware(object):
    """
    When a user logs out of facebook (on our page!), we won't get notified,
    but the djfb_ cookies wil be cleared. So this middleware checks if that
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
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the FacebookLogOutMiddleware class.")

        if is_fb_logged_in(request):

            if not request.COOKIES.get('djfb_access_token'):
                logout(request)
                log.debug('User logged out, no djfb_access_token cookie found')
                return
              
            # Also logout if the user changes
            if not request.COOKIES.get('djfb_user_id') == request.user.username:
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
        request.POST['signed_request'] = settings.FACEBOOK_DEBUG_SIGNEDREQ
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
        cookie_name = "fbs_" + settings.FACEBOOK_APP_ID
        request.COOKIES[cookie_name] = settings.FACEBOOK_DEBUG_COOKIE
        return None


class FacebookDebugTokenMiddleware(object):
    """
    Forces a specific access token to be used.

    This should be used instead of FacebookMiddleware. Make sure you have
    FACEBOOK_DEBUG_UID and FACEBOOK_DEBUG_TOKEN set in your configuration.

    """

    def process_request(self, request):
        request.facebook = FacebookAccessor(request)
        request.facebook.user_id = settings.FACEBOOK_DEBUG_UID
        request.facebook.access_token = settings.FACEBOOK_DEBUG_TOKEN
        return None
