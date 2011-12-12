from django.conf.urls.defaults import *
from django.views.generic import TemplateView

from views import fb_login, fb_logout

urlpatterns = patterns('',
    url(r'^login/$', fb_login, name='django_facebook_login'), 
    url(r'^logout/$', fb_logout, name='django_facebook_logout'), 
    url(r'^debug/$', TemplateView.as_view(template_name='django_facebook/debug.html'),
        name='django_facebook_debug'),
)
