from django.dispatch import Signal

facebook_user_created = Signal(providing_args=["user", "access_token"])