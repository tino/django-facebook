import facebook
from django.utils.functional import SimpleLazyObject
from django.contrib.auth import BACKEND_SESSION_KEY
from django.core.cache import cache

import conf

FB_ACCESS_TOKEN_CACHE_KEY = '_fb_access_token_%s'
FB_DATA_CACHE_KEY = '_fb_data_%s'


def get_lazy_access_token(request):
    if request.user.is_anonymous():
        return None
    code, use_redirect_uri = get_code_from_request(request)
    fb_id = request.user.get_username()

    def get_lazy():
        access_token = get_cached_access_token(fb_id)

        if not access_token:
            try:
                access_token, expires_in = get_fresh_access_token(code, use_redirect_uri)
                cache_access_token(fb_id, access_token, expires_in)
            except facebook.AuthError:
                raise

        return access_token

    return SimpleLazyObject(get_lazy)


def get_code_from_request(request):
    """
    Fetches the code from either the GET params or the signed_request cookie.

    Returns the code and wether or not a redirect_uri should be used.
    """
    code = None
    use_redirect_uri = True
    if 'code' in request.GET:
        code = request.GET['code']
        use_redirect_uri = True
    elif 'code' in get_signed_request_data(request):
        code = get_signed_request_data(request)['code']
        use_redirect_uri = False

    return code, use_redirect_uri


def get_fresh_access_token(code, use_redirect_uri=True):
    """
    Get a fresh_access_token with the provided code. Raise a
    facebook.AuthError if we can't.

    If the user is logged in through the client side, use_redirect_uri should
    be False.

    Returns the access_token and the amount of seconds it expires in.
    """
    if not code:
        raise facebook.AuthError('OAuthException', 'Their is no code to get an'
            'access_token with. Reauthenticate the user')

    try:
        # freaking facebook doesn't want a redirect_uri is somebody is logged
        # in throught the client-side...
        kwargs = {'redirect_uri': ''} if not use_redirect_uri else {}
        data = conf.auth.get_access_token_from_code(code, **kwargs)
    except facebook.AuthError:
        raise

    return data['access_token'], data['expires']


def get_signed_request_data(request):
    """
    Cache parsed signed_request cookie data, so we only do it once per
    request.
    """
    if not hasattr(request, '_fb_cookie_data'):
        try:
            data = conf.auth.parse_signed_request(request.COOKIES[conf.COOKIE_NAME])
        except (KeyError, ValueError, facebook.AuthError):
            data = {}
        request._fb_cookie_data = data
    return request._fb_cookie_data


def is_fb_logged_in(request):
    backendstr = 'django_facebook.auth.FacebookModelBackend'
    return request.user.is_authenticated() and \
        request.session.get(BACKEND_SESSION_KEY) == backendstr


class FacebookRequiredMixin(object):
    """CBV view mixin to display a facebook login template when the user is
    not logged in.
    """
    facebook_required_template = "facebook_required.html"

    def dispatch(self, request, *args, **kwargs):
        if not is_fb_logged_in(request):
            self.template_name = self.facebook_required_template
            self.request = request
            self.object = None
            return self.render_to_response({})
        return super(FacebookRequiredMixin, self).dispatch(request, *args, **kwargs)


def cache_access_token(user_id, access_token, expires_in=3600):
    """Cache the access_token for a user"""
    cache.set(FB_ACCESS_TOKEN_CACHE_KEY % user_id, access_token, int(expires_in))


def get_cached_access_token(user_id, default=None):
    return cache.get(FB_ACCESS_TOKEN_CACHE_KEY % user_id, default)


def del_cached_access_token(user_id):
    cache.delete(FB_ACCESS_TOKEN_CACHE_KEY % user_id)


def cache_fb_user_data(user_id, data, expires_in=None):
    if not expires_in:
        cache.set(FB_DATA_CACHE_KEY % user_id, data)
    else:
        cache.set(FB_DATA_CACHE_KEY % user_id, data, int(expires_in))


def del_cached_fb_user_data(user_id):
    cache.delete(FB_DATA_CACHE_KEY % user_id)


def get_cached_fb_user_data(user_id, default=None):
    return cache.get(FB_DATA_CACHE_KEY % user_id, default)
