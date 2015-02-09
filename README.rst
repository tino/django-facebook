Facebook integration for your Django website
=============================================

TODO: Document the server-side login flow, and the difference between both.

Requirements
------------

Some recent version of jQuery. TODO: Document where it's needed and give example

Facebook Login
--------------

With Facebook there are two ways to log in
(http://developers.facebook.com/docs/authentication/):

- through the server-side flow
- through the client-side flow

django_facebook provides methods for both these flows. For completeness and
things like reducing the number of requests you need to make to FB
server-sided, you want to be authenticated on both sides. Unfortunately
facebook per 31 december 2011 deprecated
(http://developers.facebook.com/blog/post/624/) their cookie that gave us an
easy way to get the authentication details on the server when somebody was
logged in on the client side. To overcome this, an ajax post request is made,
as soon as somebody logs in on the client side, to notify the server and give
it a change to log someone in.

Installation
------------

Simply add ``django_facebook`` to your INSTALLED_APPS and configure
the following settings:

    FACEBOOK_APP_ID = ''
    FACEBOOK_APP_SECRET = ''
    FACEBOOK_REDIRECT_URI = ''

    # Optionally set default permissions to request, e.g: ['email', 'user_friends']
    FACEBOOK_PERMS = []

    # And for local debugging, use one of the debug middlewares and set:
    FACEBOOK_DEBUG_TOKEN = ''
    FACEBOOK_DEBUG_UID = ''
    FACEBOOK_DEBUG_COOKIE = ''
    FACEBOOK_DEBUG_SIGNEDREQ = ''


Templates
---------

A few helpers for using the Javascript SDK can be enabled by adding
this to your base template before other javascript that makes use of facebook:

    {% load facebook %}
    {% facebook_init %}
        {% block facebook_code %}{% endblock %}
    {% endfacebook %}

And this should be added just before your ``</html>`` tag:

    {% facebook_load %}

The ``facebook_load`` template tag inserts the code required to
asynchronously load the facebook javascript SDK. The ``facebook_init``
tag calls ``FB.init`` with your configured application settings. It is
best to put your facebook related javascript into the ``facebook_code``
region so that it can be called by the asynchronous handler.

You may find the ``facebook_perms`` tag useful, which takes the setting
in FACEBOOK_PERMS and prints the extended permissions out in a
comma-separated list.

    <fb:login-button show-faces="false" width="200" max-rows="1"
      perms="{% facebook_perms %}"></fb:login-button>


Once this is in place you are ready to start with the facebook javascript SDK!

This module also provides all of the tools necessary for working with facebook
on the backend:


Middleware
----------

There are a couple of different middleware classes that can be enabled to do
various things.

There is ``FacebookLoginMiddleware`` to log a user in if a facebook cookie is
present. As a counter part, there is ``FacebookLogoutMiddleware`` that logs a
user out when that cookie is not present anymore. For these two middlewares to
work, you need to add ``'django_facebook.auth.FacebookModelBackend'`` to your
``AUTHENTICATION_BACKENDS`` setting.

As a helper, there is ``FacebookHelperMiddleware``, that sets a ``facebook``
object on the request, containing:

- ``user_id``: If the user is logged in, this will be the facebook user id
- ``access_token``: A lazy access_token
- ``auth``: An instantiation of ``facebook.Auth``, an object to do
  authentication stuff with, like getting a new access_token
- ``graph``: An instantiation of ``facebook.GraphAPI``.

The ``FacebookMiddleware`` activates above three middlewares as a shortcut and
for backwards compatibility. With it installed you can do:

 def friends(request): if request.facebook.user_id: friends =
request.facebook.graph.get_connections('me', 'friends')

To use the middleware, simply add this to your MIDDLEWARE_CLASSES:

 'django_facebook.middleware.FacebookMiddleware'

### Debugging:

For debugging the following middleware classes are available:

``FacebookDebugCookieMiddleware`` allows you to set a cookie in your settings
file and use this to simulate facebook logins offline.

``FacebookDebugTokenMiddleware`` allows you to set a user_id and access_token to
force facebook graph availability.

``FacebookDebugCanvasMiddleware`` allows you to set a signed_request to mimic
a page being loaded as a canvas inside Facebook.


Authentication
--------------

This provides seamless integration with the Django user system.

djang_facebook defines one backend that "authenticates" users. The real
authentication is done through the facebook API of course, so this backend
only ensures a user exists within our database. If a user doesn't exist, it
wil be created, and the [django_facebook.auth.facebook_user_created](#signals)
signal will be fired. Connect to this signal to populate profile data for
example.

Don't forget to include the default backend if you want to use standard
logins for users as well:

    'django.contrib.auth.backends.ModelBackend'


Decorators and Mixins
---------------------

``@facebook_required`` is a decorator which ensures the user is currently
logged in with facebook and has access to the facebook graph. It is a replacement
for ``@login_required`` if you are not using the facebook authentication backend.

``@canvas_only`` is a decorater to ensure the view is being loaded with
a valid ``signed_request`` via Facebook Canvas. If signed_request is not found, the
decorator will return a HTTP 400. If signed_request is found but the user has not
authorised, the decorator will redirect the user to authorise.

The ``utils.FacebookRequiredMixin`` is a class-based-view mixin that can be
used when using CBV's. It needs to come before any other metaclasses otherwise
it will not work. For example:

    class MyView(FacebookRequiredMixin, django.views.generic.DetailView):
        # rest of view...


Signals
-------

django_facebook defines a signal:
``django_facebook.auth.facebook_user_created``. It is fired when the
FacebookModelBackend creates a user, and is passed ``user``, being the just
created user, and ``facebook`` the facebook helper object that you can use to
interact with facebook (the ``FacebookHelperMiddleware`` needs to be
installed for this, otherwise the ``facebook`` kwarg will be ``None``).

Asynchronous
------------

It is advisable to handle connections with external api's asynchronous with
the request, so your user don't need to wait if facebook takes a little more
time then usual. This app is built with that idea in mind, and there only
makes calls to facebook when necessary. This means that when a facebook cookie
is present, by default no call to facebook is made to validate that cookie and
to obtain an access-token.

The ``access_token`` set on the facebook helper object is a 'lazy' access_token.
This means that the access_token is only obtained or validated at the last
moment. When the access_token is expired, a new one will be obtained if
possible.

The access_token is stored in the users session, so django's SessionMiddleware
needs to be installed.

Original Author
---------------

This app was originally forked from Aidan Lister's http://github.com/pythonforfacebook/django-facebook and changed heavily. I therefore decided to release it as a new app (under the same license).
