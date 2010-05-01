import re
import urllib
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
RELEVANCE = 'relevance'
VIEW_COUNTT = 'viewCount'
PUBLISHED = 'published'
RATING = 'rating'


class YouTubeVideo(object):

    def __init__(self, **attributes):
        for key, value in attributes.iteritems():
            setattr(self, key, value)

    def __repr__(self):
        return '<YouTubeVideo id={0}>'.format(self.video_id)

    @classmethod
    def from_feed(cls, feed_entry):
        return cls(
            title       = feed_entry.media.title.text,
            published   = feed_entry.published.text,
            description = feed_entry.media.description.text,
            category    = feed_entry.media.category[0].text,
            tags        = feed_entry.media.keywords.text,
            uri         = feed_entry.media.player.url,
            duration    = feed_entry.media.duration.seconds,
            view_count  = feed_entry.statistics.view_count,
            rating      = feed_entry.rating.average,
            video_id    = feed_entry.id.text.split('/')[-1]
        )

    @cached_property
    def video_token(self):
        content = urllib.urlopen(VIDEO_INFO_URL.format(video_id=self.video_id)).read()
        video_token = re.search('&token=([^&]+)', content)
        if not video_token:
            raise IOError("Video %s: Could not get_video_info" % self.video_id)
        return video_token.group(1).replace('%3D', '=')


    @cached_property
    def resolutions(self):
        return tuple(sorted(self.find_resolutions(), reverse=True))

    def find_resolutions(self):
        for resolution, resolution_code in RESOLUTIONS.iteritems():
            urlhandle = urllib.urlopen(self.get_video_url(resolution))
            if urlhandle.getcode() == HTTP_FOUND:
                yield resolution

    @cached_property
    def video_url(self):
        return self.get_video_url()

    def get_video_url(self, resolution=None):
        if resolution is None:
            resolution = self.resolutions[0]
        resolution_code = RESOLUTIONS[resolution]

        return GET_VIDEO_URL.format(
            token=self.video_token,
            video_id=self.video_id,
            resolution_code=resolution_code
        )


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
            yield YouTubeVideo.from_feed(entry)


if __name__ == '__main__':
    yt = YouTubeAPI('AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA')
    for item in yt.search('Annoying orange'):
        print item, item.resolutions, item.get_video_url(), item.get_video_url('360p')
