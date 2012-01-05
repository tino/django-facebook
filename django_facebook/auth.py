from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY

import facebook

from django_facebook.utils import get_fb_cookie_data
from django_facebook.signals import facebook_user_created

auth = facebook.Auth(settings.FACEBOOK_APP_ID,
    settings.FACEBOOK_APP_SECRET, settings.FACEBOOK_REDIRECT_URI)


def get_facebook_user(request, force_validate=False):
    """
    Tries to get the facebook user from either de fsbr_ cookie or a canvas
    request.

    Return a dict containing the facebook user details, if found.

    The dict contains at least the auth method and user_id, it may also contain
    the access_token and any other info made available by the authentication
    method.
    
    If ``force_validate`` is True and the user is being logged in by cookie, a
    call to facebook will be made to validate the freshness of the cookie.
    """

    def get_fb_user_client_side(request):
        """Get the user_id from the fbsr cookie."""
        data = auth.get_user_from_cookie(request.COOKIES,
            validate=force_validate)
        if not data or not data.get('user_id'):
            return None

        fb_user = dict(user_id=data['user_id'],
                       access_token=data.get('access_token', ''),
                       method='cookie')
        return fb_user
        
    def get_fb_user_canvas(request):
        """Attempt to find a user using a signed_request (canvas)."""
        # TODO Fix get_fb_user_canvas method, there will not be any uid nor user_id in data
        # See http://developers.facebook.com/docs/appsonfacebook/tutorial/#auth
        # for the workings of oauth 2 canvas login
        fb_user = None
        if request.POST.get('signed_request'):
            signed_request = request.POST["signed_request"]
            data = facebook.parse_signed_request(signed_request,
                                                 settings.FACEBOOK_APP_SECRET)
            
            if data and data.get('user_id'):
                fb_user = data['user']
                fb_user['method'] = 'canvas'
                fb_user['user_id'] = data['uid']
                fb_user['access_token'] = data['oauth_token']
        return fb_user


    fb_user = {}
    functions = [get_fb_user_client_side, get_fb_user_canvas]
    for func in functions:
        fb_user = func(request)
        if fb_user:
            break

    return fb_user or None


def login(request, user):
    """
    Persist the facebook user_id and the backend in the request. This way a
    user doesn't have to reauthenticate on every request.
    """
    if user is None:
        user = request.user
    if SESSION_KEY in request.session:
        if request.session[SESSION_KEY] != user.username:
            # To avoid reusing another user's session, create a new, empty
            # session if the existing session corresponds to a different
            # authenticated user.
            request.session.flush()
    else:
        request.session.cycle_key()
    request.session[SESSION_KEY] = user.username
    request.session[BACKEND_SESSION_KEY] = user.backend
    if hasattr(request, 'user'):
        request.user = user
    if hasattr(request, 'facebook'):
        request.facebook.user_id = user.username
    user_logged_in.send(sender=user.__class__, request=request, user=user)


class FacebookModelBackend(ModelBackend):

    def authenticate(self, request=None, fb_user_id=None, access_token=None,
            force_validate=False):
        if request:
            user_data = get_facebook_user(request, force_validate=force_validate)
            if user_data:
                user = self.get_user(user_data['user_id'], request=request)
                return user
        
        if fb_user_id:
            user = self.get_user(fb_user_id, access_token=access_token)
            return user
            
        return None

    def get_user(self, user_id, request=None, access_token=None):
        user, created = User.objects.get_or_create(
            username=user_id)
        # TODO profile callback on created
        if created:
            kwargs = dict(sender=self, user=user)
            if request and hasattr(request, 'facebook'):
                kwargs.update(dict(facebook=request.facebook))
            if access_token:
                kwargs.update(dict(access_token=access_token))
            facebook_user_created.send_robust(**kwargs)
        return user
