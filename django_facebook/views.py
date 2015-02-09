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

import conf
from .auth import login, FacebookModelBackend
from .utils import cache_access_token, is_fb_logged_in


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
        token = request.facebook.auth.get_access_token_from_code(code,
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

    The login middleware handles the login, we only need to cache the
    access_token.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(['POST'])

    if not is_fb_logged_in(request):
        return HttpResponseBadRequest('fb_client_login POSTed without valid '
                                      'fbsr_ cookie')

    cache_access_token(request.facebook.user_id,
                       request.POST['access_token'],
                       request.POST['expires_in'])
    log.debug('access_token cached in fb_client_login')
    return HttpResponse('OK')


def fb_logout(request, next=None):
    """
    Logout for the server-sided authentication flow. We can't rely on any js
    here.

    Upon logout we logout from the django auth system, we also delete the fbsr_
    cookie.

    TODO: this view does not work when you are logged in through the js SDK, due
    to the fact that the browser does not remove the fbsr_ cookie properly and
    our login middleware logs the user in again...
    """
    if next is None:
        try:
            next = settings.LOGOUT_REDIRECT_URL
        except AttributeError:
            next = reverse('djfb_debug')

    logout(request)

    response = HttpResponseRedirect(next)
    # Facebook sets the fbsr_ cookie for the "base_domain" in the fbm_ cookie
    cookie_domain = request.COOKIES.get('fbm_%s' % conf.APP_ID, '=').split('=')[1]
    response.delete_cookie(conf.COOKIE_NAME, domain=cookie_domain)
    return response
