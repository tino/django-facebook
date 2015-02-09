from urllib import quote

from django import template
from django.conf import settings
from django.core.urlresolvers import reverse, NoReverseMatch

from django_facebook import conf

register = template.Library()


@register.inclusion_tag('tags/facebook_load.html')
def facebook_load():
    # LANGUAGE_CODE defaults to en-us, which is also the default for FB
    lang, country = settings.LANGUAGE_CODE.split('-')
    fb_locale = "%s_%s" % (lang, country.upper())
    return {'fb_locale': fb_locale}


@register.tag
def facebook_init(parser, token):
    nodelist = parser.parse(('endfacebook_init',))
    parser.delete_first_token()
    return FacebookNode(nodelist)


class FacebookNode(template.Node):
    """ Allow code to be added inside the facebook asynchronous closure. """
    def __init__(self, nodelist):
        try:
            app_id = conf.APP_ID
        except AttributeError:
            raise template.TemplateSyntaxError, "%r tag requires " \
                "FACEBOOK_APP_ID to be configured." \
                % token.contents.split()[0]
        self.app_id = app_id
        self.nodelist = nodelist

    def render(self, context):
        t = template.loader.get_template('tags/facebook_init.html')
        code = self.nodelist.render(context)
        custom_context = context
        custom_context['code'] = code
        custom_context['app_id'] = self.app_id
        custom_context['version'] = getattr(settings, 'FACEBOOK_VERSION', '2.2')
        return t.render(custom_context)


@register.simple_tag
def facebook_perms():
    return ",".join(getattr(settings, 'FACEBOOK_PERMS', []))


@register.simple_tag
def facebook_login_url(request, redirect_after=None):
    """
    Templatetag for rendering the login url for server-sided login.

    An extra redirect url or urlname can be passed to be redirected to after
    server-side login has happened.
    """
    login_url = 'https://www.facebook.com/dialog/oauth?' + \
        'client_id=%s&scope=%s&redirect_uri=%s'
    redirect_to = reverse('djfb_login')
    if redirect_after:
        if redirect_after.startswith('/'):
            redirect_to += '?next=%s' % quote(redirect_after)
        else:
            redirect_to += '?next=%s' % quote(reverse(redirect_after))
    return login_url % (conf.APP_ID,
                        facebook_perms(),
                        request.build_absolute_uri(redirect_to))
