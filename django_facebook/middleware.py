from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth import authenticate, logout
from django.contrib.auth import BACKEND_SESSION_KEY

import facebook

from django_facebook.auth import login
from django_facebook.utils import get_access_token, is_fb_logged_in

auth = facebook.Auth(settings.FACEBOOK_APP_ID,
    settings.FACEBOOK_APP_SECRET, settings.FACEBOOK_REDIRECT_URI)

class FacebookAccessor(object):
    """ Simple accessor object for the Facebook user. Non-existing properties 
    will return None instead of raising a AttributeError."""

    def __init__(self, request):
        if is_fb_logged_in(request):
            self.user_id = request.user.username
        # lazy acces token, if if no user is logged is
        self.access_token = get_access_token(request)
        self.auth = auth
        self.graph = facebook.GraphAPI(self.access_token)
        
    def __getattr__(self, name):
        return None


class FacebookLoginMiddleware(object):
    """
    Transparently integrate Django accounts with Facebook. You need to add
    ``auth.FacebookModelBackend`` to ``AUTHENTICATION_BACKENDS`` for this to
    work.

    If the user presents with a valid facebook cookie, or there is a
    signed_request in request.POST (see ``auth.get_facebook_user``), then we
    want them to be automatically logged in as that user. We rely on the
    authentication backend to create the user if it does not exist.

    If you do not want to persist the facebook login, also enable
    FacebookLogOutMiddleware so that if they log out via a fb:login-button
    they are also logged out of Django.

    We also allow people to log in with other backends, so we only log someone
    in if their not already logged in.
    """

    def process_request(self, request):
        # AuthenticationMiddleware is required so that request.user exists.
        if not hasattr(request, 'user'):
            raise ImproperlyConfigured(
                "The FacebookCookieLoginMiddleware requires the"
                " authentication middleware to be installed. Edit your"
                " MIDDLEWARE_CLASSES setting to insert"
                " 'django.contrib.auth.middleware.AuthenticationMiddleware'"
                " before the FacebookCookieLoginMiddleware class.")
        if request.user.is_anonymous():
            user = authenticate(request=request)
            if user:
                login(request, user)


class FacebookLogOutMiddleware(object):
    """
    When a user logs out of facebook (on our page!), we won't get notified,
    but the fbsr_ cookie wil be cleared. So this middleware checks if that
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
        if request.user.is_authenticated() and request.session.get(
                BACKEND_SESSION_KEY) == \
                    'django_facebook.auth.FacebookModelBackend':
            try:
                cookie_data = auth.get_user_from_cookie(request.COOKIES)
            except facebook.AuthError:
                # TODO Log this
                return

            if not cookie_data:
               logout(request)
               return

            if not cookie_data.get('user_id') == request.user.username:
                logout(request)


class FacebookHelperMiddleware(object):
    """
    This middleware sets the ``facebook`` attribute on the request, which
    contains the user id and a graph accessor.
    """

    def process_request(self, request):
        request.facebook = FacebookAccessor(request)


class FacebookMiddleware(object):
    """
    This middleware implements the basic behaviour:

    - Log someone in if we can authenticate them (see ``auth``)
    - Log someone out if we can't authenticate them anymore
    - Add a ``facebook`` attribute to the request with a graph accessor.
    """
    def process_request(self, request):
        FacebookHelperMiddleware().process_request(request)
        FacebookLoginMiddleware().process_request(request)
        FacebookLogOutMiddleware().process_request(request)


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
