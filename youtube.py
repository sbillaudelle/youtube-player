import re
import urllib
import urlparse
import gdata.youtube
import gdata.youtube.service
from cream.util import cached_property


HTTP_FOUND = 200
GET_VIDEO_URL = 'http://www.youtube.com/get_video?video_id={video_id}&t={token}' \
                '&eurl=&el=embedded&ps=default&fmt={resolution_code}'
VIDEO_INFO_URL = 'http://www.youtube.com/get_video_info?video_id={video_id}' \
                 '&el=embedded&ps=default&eurl='
RESOLUTIONS = {
    '360p': 18,
    '720p': 22,
    '1080p': 37
}

# Ordering options
RELEVANCE  = 'relevance'
VIEW_COUNT = 'viewCount'
PUBLISHED  = 'published'
RATING     = 'rating'


class YouTubeVideo(object):
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
            duration    = feed_entry.media.duration.seconds,
            view_count  = feed_entry.statistics.view_count,
            rating      = feed_entry.rating and feed_entry.rating.average,
            video_id    = feed_entry.id.text.split('/')[-1]
        )

    @cached_property
    def _video_info(self):
        return urlparse.parse_qs(
            urllib.urlopen(VIDEO_INFO_URL.format(video_id=self.video_id)).read()
        )

    @property
    def creator(self):
        return self._video_info['creator']

    @cached_property
    def resolutions(self):
        """
        Tuple with all resolutions available for this video.
        Possible resolutions are::

            '360p', '720p', '1080p'

        (``cached_property`` that gets its value from ``find_resolutions``.)
        """
        return tuple(sorted(self.find_resolutions(), reverse=True))

    def find_resolutions(self):
        """
        Finds all resolutions in which this video is available.
        This method sends 3 HTTP requests to the YouTube servers.
        """
        # TODO: List of available resolutions/stream urls can be extracted
        # from ``self._video_info``, so no extra HTTP requests needed here.
        for resolution, resolution_code in RESOLUTIONS.iteritems():
            urlhandle = urllib.urlopen(self.get_video_url(resolution))
            if urlhandle.getcode() == HTTP_FOUND:
                yield resolution

    @cached_property
    def video_url(self):
        return self.get_video_url()

    def get_video_url(self, resolution=None):
        """
        Returns the video stream URL of this video with the given `resolution`.

        If no `resolution` is given, the highest available resolution will be
        chosen from the ``r
        esolutions`` attribute.
        """
        if resolution is None:
            resolution = self.resolutions[0]
        resolution_code = RESOLUTIONS[resolution]

        return GET_VIDEO_URL.format(
            token=self._video_info['token'],
            video_id=self.video_id,
            resolution_code=resolution_code
        )

    @property
    def thumbnail_url(self):
        try:
            return self._video_info['thumbnail_url'][0]
        except KeyError:
            return None

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


class YouTubeAPI(object):

    def __init__(self, developer_key):

        self.service = gdata.youtube.service.YouTubeService()
        self.service.developer_key = developer_key


    def search(self, search_string, order_by=RELEVANCE):

        query = gdata.youtube.service.YouTubeVideoQuery()
        query.vq = search_string
        query.orderby = order_by
        query.racy = 'include'
        feed = self.service.YouTubeQuery(query)

        for entry in feed.entry:
            yield YouTubeVideo.from_feed_entry(entry)


if __name__ == '__main__':
    yt = YouTubeAPI('AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA')
    for item in yt.search('Annoying orange'):
        print item, item.resolutions, item.get_video_url(), item.get_video_url('360p')
        print item.thumbnail_url
        print item.thumbnail_path
        break
