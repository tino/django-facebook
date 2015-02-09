from functools import update_wrapper, wraps

import facebook
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.http import (HttpResponse, HttpResponseBadRequest,
                         HttpResponseRedirect)
from django.utils.decorators import available_attrs
from django.utils.http import urlquote

import conf
from utils import is_fb_logged_in


def canvas_only(function=None):
    """
    Decorator ensures that a page is only accessed from within a facebook
    application.

    """
    def _dec(view_func):
        def _view(request, *args, **kwargs):
            # Make sure we're receiving a signed_request from facebook
            if not request.POST.get('signed_request'):
                return HttpResponseBadRequest('<h1>400 Bad Request</h1>'
                                    '<p>Missing <em>signed_request</em>.</p>')

            # Parse the request and ensure it's valid
            signed_request = request.POST["signed_request"]
            data = conf.auth.parse_signed_request(signed_request)
            if data is False:
                return HttpResponseBadRequest('<h1>400 Bad Request</h1>'
                                  '<p>Malformed <em>signed_request</em>.</p>')

            # If the user has not authorised redirect them
            if not data.get('uid'):
                scope = getattr(settings, 'FACEBOOK_PERMS', None)
                auth_url = conf.auth.auth_url(conf.APP_ID,
                                              conf.CANVAS_PAGE,
                                              scope)
                markup = ('<script type="text/javascript">'
                          'top.location.href="%s"</script>' % auth_url)
                return HttpResponse(markup)

            # Success so return the view
            return view_func(request, *args, **kwargs)
        return _view
    return _dec(function)


def facebook_required(function=None, redirect_field_name=REDIRECT_FIELD_NAME):
    """
    Decorator for views that checks that the user is logged in, redirecting
    to the log-in page if necessary.

    """
    def _passes_test(test_func, login_url=None,
                     redirect_field_name=REDIRECT_FIELD_NAME):
        if not login_url:
            from django.conf import settings
            login_url = settings.LOGIN_URL

        def decorator(view_func):
            def _wrapped_view(request, *args, **kwargs):
                if test_func(request):
                    return view_func(request, *args, **kwargs)
                path = urlquote(request.get_full_path())
                tup = login_url, redirect_field_name, path
                return HttpResponseRedirect('%s?%s=%s' % tup)
            return wraps(view_func, assigned=available_attrs(view_func))(
                                                                _wrapped_view)
        return decorator

    actual_decorator = _passes_test(
        is_fb_logged_in,
        redirect_field_name=redirect_field_name
    )

    if function:
        return actual_decorator(function)
    return actual_decorator
