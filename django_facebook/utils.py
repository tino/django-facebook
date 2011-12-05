import datetime
import urllib
import urlparse
import time
import json

from django.utils.functional import SimpleLazyObject
from django.conf import settings
import facebook
from facebook import GraphAPIError

ACCESS_TOKEN_SESSION_KEY = '_fb_access_token'
ACCESS_TOKEN_EXPIRES_SESSION_KEY = '_fb_access_token_expires'

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
    
    Raise an GraphAPIError if we can get that code, or can't get an
    access_token.
    """
    code = None
    if 'code' in request.GET:
        code = request.GET['code']
    elif 'code' in get_fb_cookie_data(request):
        code = get_fb_cookie_data(request)['code']
    
    if not code:
        raise GraphAPIError('OAuthException', 'Their is no code to get an \
            access_token with. Reauthenticate the user')
            
    args = {
        'client_id': settings.FACEBOOK_APP_ID,
        'client_secret': settings.FACEBOOK_SECRET_KEY,
        'code': code,
        'redirect_uri': '',
    }
    response = urllib.urlopen("https://graph.facebook.com/oauth/access_token"+
        "?%s" % urllib.urlencode(args))
    data = response.read()
    if "error" in data:
        data = json.loads(data)
        raise GraphAPIError(data['error']['type'], data['error']['message'])
    
    # No error, data is in querysting format...
    data = urlparse.parse_qs(data)
    return data['access_token'][0], data['expires'][0]
    

def get_fb_cookie_data(request):
    """Cache parsed cookie data, so we only do it once per request."""
    if not hasattr(request, '_fb_cookie_data'):
        cookie = request.COOKIES.get("fbsr_" + settings.FACEBOOK_APP_ID, None)
        if not cookie:
            return {}
        data = facebook.parse_signed_request(cookie,
                                            settings.FACEBOOK_SECRET_KEY)
        if not data: # data can be False...
            return {}
        request._fb_cookie_data = data
    return request._fb_cookie_data
