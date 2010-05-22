import re
import urllib
import urlparse
import datetime
import gdata.youtube
import gdata.youtube.service
from cream.util import cached_property
from cream.util.dicts import ordereddict


VIDEO_INFO_URL = 'http://www.youtube.com/get_video_info?video_id={video_id}'

RESOLUTION_WARNING = """Found unknown resolution with id {resolution_id}.
Please file a bug at http://github.com/sbillaudelle/youtube-player/issues
or send a mail to cream@cream-project.org" including the following information:
    Video-ID: {video_id}
Thank you!"""

# Ordering options
SORT_BY_RELEVANCE  = 'relevance'
SORT_BY_VIEW_COUNT = 'viewCount'
SORT_BY_PUBLISHED  = 'published'
SORT_BY_RATING     = 'rating'

RESOLUTIONS = ordereddict((
    (37, '1080p'),
    (22, '720p'),
    (35, '480p'),
    (34, '480p'),
    (18, '360p'),
    (5,  'FLV1')
))


class YouTubeError(Exception):
    pass

class _VideoInfoProperty(property):
    """
    Property used to hide the ``Video.video_info`` dict
    (which is not a pretty API at all).

        foo = _VideoInfoProperty('blah')

    could be expressed with built-in Python tools like this::

        @property
        def foo(self):
            return self.video_info['blah']

    Additionally to that basic functionality the ``_VideoInfoProperty``
    can do some useful other stuff like automatically converting the
    assigend value using an arbitrary conversion function (e.g., ``int``).

    :param video_info_key:
        The attribute's key in the ``Video.video_info`` dict
        ('blah' in the example above)
    :param allow_none:
        Specifies whether the property's value should be ``None`` if the
        above mentioned key isn't given in the ``Video.video_info`` dict
        or whether an exception should be raised.
    :param type:
        the conversion function, e.g. ``int`` or ``float`` or whatever.
    """
    def __init__(self, video_info_key, allow_none=False, type=None):
        self.key = video_info_key
        self.allow_none = allow_none
        self.conversion_func = type or (lambda x:x)
        property.__init__(self, fget=self._fget)

    def _fget(self, obj):
        try:
            var = obj.video_info[self.key][0]
        except KeyError:
            if not self.allow_none:
                raise
        else:
            return self.conversion_func(var)

class Video(object):
    """
    Represents a YouTube video.

    Takes arbitrary keyword arguments that end up in instance attributes of the
    very same name::

        >>> video = Video(foo=42, bar='hello world')
        >>> video.foo
        42
        >>> video.bar
        'hello world'
    """

    def __init__(self, **attributes):
        for key, value in attributes.iteritems():
            setattr(self, key, value)

    def __repr__(self):
        return '<YouTubeVideo id={0}>'.format(self.video_id)

    @classmethod
    def from_feed_entry(cls, feed_entry):
        """
        Creates a new instance from a ``gdata.youtube.YouTubeVideoEntry`` and
        extracts the following information from that entry:

        * *video_id* (``str``)
        * *title* (``str``)
        * *description* (``str``)
        * *tags* (``list`` of ``str``)
        * *category* (``str``)
        * *uri* (``str``)
        * *duration* (``int``)
        * *view_count* (``int`` if given, else ``None``)
        * *rating* (``float`` if given, else ``None``)
        * *datetime* (``datetime.datetime``)

        All attributes mentioned end up as instance attributes like
        described in the documentation for ``Video``.
        """
        def _to_datetime(s):
            return datetime.datetime.strptime(s, '%Y-%m-%dT%H:%M:%S.000Z')

        return cls(
            title       = feed_entry.media.title.text,
            datetime    = _to_datetime(feed_entry.published.text),
            description = feed_entry.media.description.text,
            category    = feed_entry.media.category[0].text,
            tags        = map(str.strip, feed_entry.media.keywords.text.split(',')),
            uri         = feed_entry.media.player.url,
            duration    = int(feed_entry.media.duration.seconds),
            view_count  = feed_entry.statistics and int(feed_entry.statistics.view_count) or None,
            rating      = feed_entry.rating and float(feed_entry.rating.average) or None,
            video_id    = feed_entry.id.text.split('/')[-1]
        )

    #: URL to the video's thumbnail
    #: (``request_video_info`` has to be called before accessing this property``)
    thumbnail_url   = _VideoInfoProperty('thumbnail_url', allow_none=True)


    def request_video_info(self):
        """
        Sends a HTTP request to the YouTube servers asking for additional
        information about the video.

        Note that this method has to be called before accessing ``video_info`` and some
        other attributes that depend on it (like ``stream_urls`` or ``thumbnail_url``)!
        """
        if hasattr(self, '_video_info'):
            # All work already done, do nothing.
            return
        info = urlparse.parse_qs(
            urllib.urlopen(VIDEO_INFO_URL.format(video_id=self.video_id)).read()
        )
        if info['status'][0] != 'ok':
            try:
                video_title = "('" + self.title + "')"
            except AttributeError:
                video_title = ''
            raise YouTubeError("Could not get video information about video "
                               "'{video_id}' {video_title}: {reason}".format(
                                   video_id=self.video_id,
                                   video_title=video_title,
                                   reason=info['reason'][0]))
        else:
            self._video_info = info

    @property
    def video_info(self):
        """
        A dictionary containing addtional video meta data.

        Has to be requested from YouTube using ``request_video_info`` or a
        ``RuntimeError`` will be raised when trying to access this property.
        """
        try:
            return self._video_info
        except AttributeError:
            raise RuntimeError("Cannot access 'video_info': Make sure to request "
                               "it using 'request_video_info' first.")

    @cached_property
    def stream_urls(self):
        """
        A dictionary of directly streamable URLs in all resolutions that are
        known to be available for this video.

        (``request_video_info`` has to be called before accessing this property)
        """
        urls = dict()
        for item in self.video_info['fmt_url_map'][0].split(','):
            resolution_id, stream_url = item.split('|')
            resolution_id = int(resolution_id)
            try:
                resolution_name = RESOLUTIONS[resolution_id]
            except KeyError:
                self._warn_unknown_resolution(resolution_id)
            else:
                urls[resolution_name] = self._cleanup_stream_url(stream_url)
        return urls

    def _cleanup_stream_url(self, url):
        # TODO: Remove all unnecessary information from the URL
        # to protect the user's privacy as good as possible.
        return url

    def _warn_unknown_resolution(self, resolution_id):
        print RESOLUTION_WARNING.format(resolution_id=resolution_id,
                                        video_id=self.video_id)

    @cached_property
    def thumbnail_path(self):
        """
        Downloads the video thumbnail to the tempfile directory and returns
        its full, absolute file path.

        (``request_video_info`` has to be called before accessing this property)
        """
        if self.thumbnail_url is None:
            return None
        from tempfile import mkstemp
        file_fd, file_name = mkstemp()
        with open(file_name, 'w') as temp_file:
            temp_file.write(urllib.urlopen(self.thumbnail_url).read())
        return file_name


class API(object):

    def __init__(self, developer_key):

        self.service = gdata.youtube.service.YouTubeService()
        self.service.developer_key = developer_key


    def search(self, search_string, order_by=SORT_BY_RELEVANCE):

        query = gdata.youtube.service.YouTubeVideoQuery()
        query.vq = search_string
        query.orderby = order_by
        query.racy = 'include'
        feed = self.service.YouTubeQuery(query)

        for entry in feed.entry:
            yield Video.from_feed_entry(entry)
