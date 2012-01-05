import urllib
import logging

from django.core.urlresolvers import reverse
from django.contrib.auth import logout, authenticate
from django.http import HttpResponse, HttpResponseRedirect
from django.conf import settings
from django.template.loader import render_to_string

import facebook

from .auth import login
from .utils import cache_access_token


log = logging.getLogger('django_facebook.views')


def fb_login(request):
    """View that accepts the redirect from Facebook after the user signs in 
    there.
    """
    # TODO error_reason when user denies
    next = request.GET.get('next')
    if not next:
        next = reverse(getattr(settings, 'FACEBOOK_LOGIN_REDIRECT_URL', 'django_facebook_debug'))
    
    code = request.GET.get('code')
    if not code:
        log.error('Could not log into facebook because no code was present in '
            'the GET parameters')
        # best we can do is redirect to login page again...
        return HttpResponseRedirect(next)

    try:
        scheme = request.is_secure() and 'https' or 'http'
        redirect_uri = '%s://%s%s' % (scheme, request.get_host(), reverse('django_facebook_login'))
        data = request.facebook.auth.get_access_token(code,
            redirect_uri=redirect_uri)
        access_token, expires = data['access_token'], data['expires']
        # Set the access_token for further use:
        cache_access_token(request, access_token, expires)
        fb_user = facebook.GraphAPI(access_token).get_object('me')
    except facebook.GraphAPIError, e:
        log.error('Could not log into facebook because: %s' % e)
        # best we can do is redirect to login page again...
        return HttpResponseRedirect(next)

    user = authenticate(fb_user_id=fb_user['id'], access_token=access_token)
    login(request, user)
    return HttpResponseRedirect(next)


def fb_logout(request, next=None):
    # def logout_response(*args, **kwargs):
    #     """We need to delete the cookie otherwise the middleware logs us in 
    #     again!
    #     """
    #     response = HttpResponseRedirect(*args, **kwargs)
    #     response.delete_cookie('fbsr_%s' % settings.FACEBOOK_APP_ID)
    #     return response
    #     
    # logout(request)
    # import pdb; pdb.set_trace()
    # if next is None:
    #     next = reverse('django_facebook_debug')
    # if not hasattr(request, 'facebook'):
    #     # We have no facebook data so we can't log out of facebook
    #     return logout_response(next)
    # try:
    #     access_token = 'adfsd' #str(request.facebook.access_token)
    # except GraphAPIError:
    #     return logout_response(next)
    # logout_url = 'https://www.facebook.com/logout.php?next=%s&access_token=%s'
    # return logout_response(logout_url % (
    #     urllib.quote(request.build_absolute_uri(next)),
    #     # access_token)
    #     )
    # )
    
    if next is None:
        next = reverse('django_facebook_debug')
    context = dict(redirect_uri=next, app_id=settings.FACEBOOK_APP_ID)
    
    logout(request)

    response = HttpResponse(render_to_string('django_facebook/js_logout.html', context))
    response.delete_cookie('fbsr_%s' % settings.FACEBOOK_APP_ID)
    return response