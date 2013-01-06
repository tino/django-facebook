from django.conf.urls import *
from django.views.generic import TemplateView

urlpatterns = patterns('django_facebook.views',
    url(r'^login/$', 'fb_server_login', name='djfb_login'),
    url(r'^login/client/$', 'fb_client_login', name='djfb_clientside_login'),
    url(r'^logout/$', 'fb_logout', name='djfb_logout'),
    url(r'^debug/$', TemplateView.as_view(template_name='django_facebook/debug.html'),
        name='djfb_debug'),
)
