import hashlib
import logging

from django.contrib import auth as django_auth
from django.contrib.auth import BACKEND_SESSION_KEY, get_user_model, SESSION_KEY
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.signals import user_logged_in
from django_facebook.signals import facebook_user_created
from django_facebook.utils import (cache_access_token, del_cached_access_token,
                                   del_cached_fb_user_data,
                                   get_signed_request_data)

import conf

User = get_user_model()

log = logging.getLogger('django_facebook.auth')


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
        del request.COOKIES[conf.COOKIE_NAME]
    except KeyError:
        pass


class FacebookModelBackend(ModelBackend):

    create_on_not_found = True

    def authenticate(self, request=None, access_token=None, expires_in=None,
                     force_validate=False):
        """
        Users are basically authenticated by the signed_request facebook gives
        us, as facebook takes care of the real authentication. You must
        therefore only call this method with a request, upon which the ``fbsr_``
        cookie is used to validate the user, or with the ``signed_request``
        itself.

        If you pass in the ``signed_request``, you must also provide the
        ``access_token`` and ``expires_in`` kwargs.
        """
        if not request:
            raise TypeError("Please provide the request")

        user = None
        if request:
            auth_data = get_signed_request_data(request)
            if auth_data:
                user = self.get_user(auth_data['user_id'], access_token)

                if access_token:
                    cache_access_token(auth_data['user_id'],
                                       access_token,
                                       expires_in)

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
            user, created = User.objects.get_or_create(
                **{User.USERNAME_FIELD: user_id,
                   'defaults': {'password': '!'}})  # also set unusable password
            if created:
                log.debug('New user created for facebook account %s' % user_id)
                kwargs = dict(sender=self, user=user, access_token=access_token)
                facebook_user_created.send_robust(**kwargs)
            return user
        else:
            return User.objects.filter(**{User.USERNAME_FIELD: user_id}).first()
