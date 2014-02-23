from django.conf import settings
from django.contrib import auth as django_auth
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in
from django.contrib.auth import SESSION_KEY, BACKEND_SESSION_KEY
User = get_user_model()

import logging
log = logging.getLogger('django_facebook.auth')

import facebook

from django_facebook.signals import facebook_user_created
from django_facebook.utils import (get_signed_request_data, cache_access_token,
    del_cached_access_token, del_cached_fb_user_data)

auth = facebook.Auth(settings.FACEBOOK_APP_ID,
    settings.FACEBOOK_APP_SECRET, settings.FACEBOOK_REDIRECT_URI)


def get_fb_user_from_request(request, force_validate=False):
    """
    Try to get the facebook user from either the djfb_signed_request cookie
    or a canvas request.

    Return a dict containing the facebook user details, if found.

    The dict contains at least the auth method and user_id, it may also contain
    the access_token and any other info made available by the authentication
    method.

    If ``force_validate`` is True and the user is being logged in by cookie, a
    call to facebook will be made to validate the freshness of the cookie.
    """

    def get_fb_user_client_side(request):
        """Get the user_id from the ``djfb_signed_request`` cookie."""
        data = get_signed_request_data(request)
        if not data or not data.get('user_id'):
            return None

        access_token = request.COOKIES.get('djfb_access_token')
        expires_in = request.COOKIES.get('djfb_expires_in')

        return dict(user_id=data['user_id'],
                    access_token=access_token,
                    expires_in=expires_in,
                    method='cookie')

    def get_fb_user_canvas(request):
        """Attempt to find a user using a signed_request (canvas)."""
        # TODO Fix get_fb_user_canvas method, there will not be any uid nor user_id
        # in data See http://developers.facebook.com/docs/appsonfacebook/tutorial/#auth
        # for the workings of oauth 2 canvas login
        fb_user = None
        if request.POST.get('signed_request'):
            signed_request = request.POST['signed_request']
            try:
                data = auth.parse_signed_request(signed_request)
            except ValueError as e:
                # ValueErrors are raised by facebook.Auth with malformed tokens
                log.info('Something wrong with signed_request: %s' % e)
                return None

            if data and data.get('user_id'):
                fb_user = data['user']
                fb_user['method'] = 'canvas'
                fb_user['user_id'] = data['user_id']
                fb_user['access_token'] = data['oauth_token']
                fb_user['expires_in'] = data['expires']
                fb_user['metadata_page'] = data['page']
                fb_user['app_data'] = data.get('app_data', '')
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
        if request.session[SESSION_KEY] != user.get_username():
            # To avoid reusing another user's session, create a new, empty
            # session if the existing session corresponds to a different
            # authenticated user.
            request.session.flush()
    else:
        request.session.cycle_key()
    # save the username (is facebook id) as user id
    request.session[SESSION_KEY] = user.get_username()
    request.session[BACKEND_SESSION_KEY] = user.backend
    if hasattr(request, 'user'):
        request.user = user
    if hasattr(request, 'facebook'):
        request.facebook.user_id = user.get_username()
    log.debug('Facebook user %s logged in' % user.get_username())
    user_logged_in.send(sender=user.__class__, request=request, user=user)


def logout(request):
    """
    Logout the user, delete cached data and clear cookies so any auth calls
    coming after don't log the user in again.
    """
    user_id = request.user.get_username()
    del_cached_fb_user_data(user_id)
    del_cached_access_token(user_id)
    django_auth.logout(request)

    try:
        del request.COOKIES['djfb_access_token']
        del request.COOKIES['djfb_expires_in']
        del request.COOKIES['djfb_signed_request']
        del request.COOKIES['djfb_user_id']
    except KeyError:
        pass


class FacebookModelBackend(ModelBackend):

    create_on_not_found = True

    def authenticate(self, request=None, signed_request=None, code=None,
            access_token=None, expires_in=None, force_validate=False):
        """
        Users are basically authenticated by the signed_request facebook gives
        us, as facebook takes care of the real authentication. You must
        therefore only call this method with a request, upon which the
        ``djfb_signed_request`` cookie is used to validate the user, or with
        the ``signed_request`` itself.

        If you pass in the ``signed_request``, you must also
        provide the ``access_token`` and ``expires_in`` kwargs.

        If you call with ``force_validate=True``, a call to facebook will be
        made to validate the signed request is still valid.
        # TODO implement force_validate
        """
        if sum([bool(request), bool(signed_request)]) != 1:
            raise TypeError("Please provide excatly one of: request, "
                            "signed_request")

        user = None
        if request:
            auth_data = get_fb_user_from_request(request,
                                                force_validate=force_validate)
            if auth_data:
                user = self.get_user(auth_data['user_id'],
                                    request.COOKIES.get('djfb_access_token'))

            cache_access_token(auth_data['user_id'],
                               auth_data['access_token'],
                               auth_data['expires_in'])

        elif signed_request:
            if not access_token and expires_in:
                raise TypeError('If you pass the signed_request, you also need'
                ' to provide the access_token and expires_in kwargs.')
            try:
                auth_data = auth.parse_signed_request(signed_request)
            except facebook.AuthError:
                return None

            user = self.get_user(auth_data['user_id'], access_token)

        return user

    def get_user(self, user_id, access_token=None):
        """
        Lookup the user by their facebook id, and create a new one if they
        don't exist yet. Upon creation the facebook_user_created signal is
        fired. For this reason you really should pass a valid access_token for
        this user, so that connecting functions can actually do something
        usefull, like pre-fetching user data.
        """
        log.debug('FacebookModelBackend.get_user called')
        if self.create_on_not_found:
            user, created = User.objects.get_or_create(**{User.USERNAME_FIELD: user_id,
                'defaults': {'password': '!'}})  # also set unusable password
            if created:
                log.debug('New user created for facebook account %s' % user_id)
                kwargs = dict(sender=self, user=user, access_token=access_token)
                facebook_user_created.send_robust(**kwargs)
            return user
        else:
            return User.objects.filter(**{User.USERNAME_FIELD: user_id}).first()
