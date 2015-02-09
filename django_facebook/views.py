import urllib
import logging

from django.core.urlresolvers import reverse
from django.contrib.auth import logout, authenticate
from django.http import (HttpResponse, HttpResponseRedirect,
    HttpResponseNotAllowed, HttpResponseBadRequest)
from django.conf import settings
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt

import facebook

from .auth import login, FacebookModelBackend
from .utils import cache_access_token, get_cached_access_token


log = logging.getLogger('django_facebook.views')


def fb_server_login(request):
    """View that accepts the redirect from Facebook after the user signs in
    there.
    """
    # TODO error_reason when user denies
    next = request.GET.get('next')
    if not next:
        next = reverse(getattr(settings, 'FACEBOOK_LOGIN_REDIRECT_URL', 'djfb_debug'))

    code = request.GET.get('code')
    if not code:
        log.error('Could not log into facebook because no code was present in '
            'the GET parameters')
        # best we can do is redirect to login page again...
        return HttpResponseRedirect(next)

    # authenticate doesn't work here, as it needs the signed request, not
    # the code. So do the validating here ourselves
    try:
        scheme = request.is_secure() and 'https' or 'http'
        redirect_uri = '%s://%s%s' % (scheme, request.get_host(), reverse('djfb_login'))
        token = request.facebook.auth.get_access_token(code,
            redirect_uri=redirect_uri)
        access_token, expires_in = token['access_token'], token['expires']
        fb_user = facebook.GraphAPI(access_token).get_object('me')
    except facebook.GraphAPIError, e:
        log.error('Could not log into facebook because: %s' % e)
        # best we can do is redirect to login page again...
        return HttpResponseRedirect(next)

    # Cache the access_token (normally autenticate does this)
    cache_access_token(fb_user['id'], access_token, expires_in)

    user = FacebookModelBackend().get_user(fb_user['id'], access_token)
    user.backend = 'django_facebook.auth.FacebookModelBackend'
    login(request, user)

    response = HttpResponseRedirect(next)
    # Set djfb_access_token and djfb_user_id, otherwise the user will be logged
    # out by our middleware
    response.set_cookie('djfb_access_token', access_token)
    response.set_cookie('djfb_user_id', fb_user['id'])

    return response


@csrf_exempt
def fb_client_login(request):
    """
    View for the POST request that is made by our javascript on login of the
    user, so the server and client are in sync concerning login status.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(['POST'])

    # Try to bail early if the user_id's still match. This happens if the
    # window.djfb.user_id was not set properly. Do update the access_token though
    user_id = request.POST.get('user_id')
    if user_id and request.user.is_authenticated():
        if user_id == request.user.get_username():
            cache_access_token(user_id,
                               request.POST['access_token'],
                               request.POST['expires_in'])
            return HttpResponse('OK')

    if not 'signed_request' in request.POST:
        return HttpResponseBadRequest('This view needs the signed_request')

    user = authenticate(signed_request=request.POST['signed_request'],
                        access_token=request.POST['access_token'],
                        expires_in=request.POST['expires_in'])
    if not user:
        return HttpResponseBadRequest('Could not log the user in with the '
                                      'given signed_request')
    login(request, user)
    log.debug('logged in user through fb_client_login')
    return HttpResponse('OK')


def fb_logout(request, next=None):
    """
    Logout for the server-sided authentication flow. We can't rely on any js
    here.

    Upon logout we logout from the django auth system, we also delete any
    cookies we might have set.
    """
    if next is None:
        try:
            next = settings.LOGOUT_REDIRECT_URL
        except AttributeError:
            next = reverse('djfb_debug')

    logout(request)

    response = HttpResponseRedirect(next)
    response.delete_cookie('djfb_access_token')
    response.delete_cookie('djfb_expires_in')
    response.delete_cookie('djfb_signed_request')
    response.delete_cookie('djfb_user_id')
    return response
