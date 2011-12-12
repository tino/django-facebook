from django import template
from django.conf import settings
from django.core.urlresolvers import reverse

register = template.Library()


@register.inclusion_tag('tags/facebook_load.html')
def facebook_load():
    pass


@register.tag
def facebook_init(parser, token):
    nodelist = parser.parse(('endfacebook',))
    parser.delete_first_token()
    return FacebookNode(nodelist)


class FacebookNode(template.Node):
    """ Allow code to be added inside the facebook asynchronous closure. """
    def __init__(self, nodelist):
        try:
            app_id = settings.FACEBOOK_APP_ID
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
        return t.render(context)


@register.simple_tag
def facebook_perms():
    return ",".join(getattr(settings, 'FACEBOOK_PERMS', []))


@register.simple_tag
def facebook_login_url(request):
    login_url = 'https://www.facebook.com/dialog/oauth?' + \
         'client_id=%s&redirect_uri=%s&scope=%s&'
    redirect_to = reverse('django_facebook_login')
    return login_url % (settings.FACEBOOK_APP_ID,
                        request.build_absolute_uri(redirect_to),
                        facebook_perms())