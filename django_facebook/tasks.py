import facebook
from celery.utils.log import get_task_logger
from django.core.exceptions import ImproperlyConfigured

from .utils import get_cached_access_token

try:
    from celery import shared_task, subtask
except ImportError:
    raise ImproperlyConfigured('You need to install a recent version of celery'
                               ' to use the tasks!')

log = get_task_logger(__name__)


@shared_task(bind=True, default_retry_delay=60)
def get_friends_for_user(self, fb_id, callback, next_uri=None):
    """
    Get the facebook friends for the user with fb_id.

    1. Needs a valid access_token in the cache
    2. Needs 'user_friends' permission
    3. Needs a callback function that can store the friends somewhere

    If 1. is not present, the task is delayed
    If 2. is not the case, you're out of luck
    """
    access_token = get_cached_access_token(fb_id)
    if access_token is None:
        raise self.retry(exc=ValueError("Failed to fetch facebook data for %s. "
                                        "No access_token found in cache" % fb_id))

    graph = facebook.GraphAPI(access_token)

    try:
        if next_uri:
            data = graph.bare_request(next_uri)
        else:
            data = graph.get_connections('me', 'friends', limit=500)
    except facebook.GraphAPIError as exc:
        raise self.retry(exc=exc)

    subtask(callback).delay(data['data'])
    if data['paging'].get('next'):
        self.delay(fb_id, callback, next_uri=data['paging']['next'])
