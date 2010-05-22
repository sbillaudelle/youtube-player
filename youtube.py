import re
import urllib
import urlparse
from datetime import datetime
import gdata.youtube
import gdata.youtube.service
from cream.util import cached_property
from cream.util.dicts import ordereddict


HTTP_FOUND = 200
GET_VIDEO_URL = 'http://www.youtube.com/get_video?video_id={video_id}&t={token}' \
                '&eurl=&el=embedded&ps=default&fmt={resolution_code}'
VIDEO_INFO_URL = 'http://www.youtube.com/get_video_info?video_id={video_id}' \
                 '&el=embedded&ps=default&eurl='
RESOLUTIONS = ordereddict((
    (37, '1080p'),
    (22, '720p'),
    (35, '480p'),
    (34, '480p'),
    (18, '360p'),
    (5,  'FLV1')
))

# Ordering options
SORT_BY_RELEVANCE  = 'relevance'
SORT_BY_VIEW_COUNT = 'viewCount'
SORT_BY_PUBLISHED  = 'published'
SORT_BY_RATING     = 'rating'

RESOLUTION_WARNING = """Found unknown resolution with id {resolution_id}.
Please file a bug at http://github.com/sbillaudelle/youtube-player/issues
or send a mail to cream@cream-project.org" including the following information:
    Video-ID: {video_id}
Thank you!"""



class _VideoInfoProperty(property):
    def __init__(self, video_info_key, value_index=0, allow_none=False, type=None):
        self.key = video_info_key
        self.value_index = value_index
        self.allow_none = allow_none
        self.conversion_func = type or (lambda x:x)
        property.__init__(self, fget=self._fget)

    def _fget(self, obj):
        try:
            var = obj.video_info[self.key][self.value_index]
        except KeyError:
            if not self.allow_none:
                raise
        else:
            return self.conversion_func(var)

class YouTubeError(Exception):
    pass

class Video(object):
    """ Represents a YouTube video. """

    def __init__(self, **attributes):
        for key, value in attributes.iteritems():
            setattr(self, key, value)

    def __repr__(self):
        return '<YouTubeVideo id={0}>'.format(self.video_id)

    @classmethod
    def from_feed_entry(cls, feed_entry):
        """ Creates a new instance from a ``gdata.youtube.YouTubeVideoEntry``. """
        return cls(
            title       = feed_entry.media.title.text,
            published   = feed_entry.published.text,
            description = feed_entry.media.description.text,
            category    = feed_entry.media.category[0].text,
            tags        = feed_entry.media.keywords.text,
            uri         = feed_entry.media.player.url,
            duration    = int(feed_entry.media.duration.seconds),
            view_count  = feed_entry.statistics and feed_entry.statistics.view_count,
            rating      = feed_entry.rating and float(feed_entry.rating.average) or None,
            video_id    = feed_entry.id.text.split('/')[-1]
        )

    thumbnail_url   = _VideoInfoProperty('thumbnail_url', allow_none=True)
    datetime        = _VideoInfoProperty('timestamp', type=datetime.fromtimestamp)


    def request_video_info(self):
        if hasattr(self, '_video_info'):
            # All work already done, do nothing.
            return
        info = urlparse.parse_qs(
            urllib.urlopen(VIDEO_INFO_URL.format(video_id=self.video_id)).read()
        )
        if info['status'][0] != 'ok':
            raise YouTubeError("Could not get video information about video "
                               "'{video_id}' ('{video_title}'): {reason}".format(
                                   video_id=self.video_id,
                                   video_title=self.title,
                                   reason=info['reason'][0]))
        else:
            self._video_info = info

    @property
    def video_info(self):
        try:
            return self._video_info
        except AttributeError:
            raise RuntimeError("Cannot access 'video_info': Make sure to request "
                               "it using 'request_video_info' first.")

    @cached_property
    def stream_urls(self):
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
        if self.thumbnail_url is None:
            return None
        import os
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
