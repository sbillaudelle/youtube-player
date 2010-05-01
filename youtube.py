import re

import gdata.youtube
import gdata.youtube.service

import urllib

DEVELOPER_KEY = 'AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA'


RELEVANCE = 'relevance'
VIEW_COUNTT = 'viewCount'
PUBLISHED = 'published'
RATING = 'rating'

RESOLUTIONS = {
    '360p': 18,
    '720p': 22,
    '1080p': 37
    }


class YouTubeVideo(object):

    def __init__(self, entry):

        self.title = entry.media.title.text
        self.published = entry.published.text
        self.description = entry.media.description.text
        self.category = entry.media.category[0].text
        self.tags = entry.media.keywords.text
        self.uri = entry.media.player.url
        self.duration = entry.media.duration.seconds

        self.view_count = entry.statistics.view_count
        self.rating = entry.rating.average

        self.id = entry.id.text.split('/')[-1]

        video_info = urllib.urlopen('http://www.youtube.com/get_video_info?video_id={0}&el=embedded&ps=default&eurl='.format(self.id)).read()
        m = re.search('&token=([^&]+)', video_info)
        if m:
            self.token = m.group(1).replace('%3D', '=')
        else:
            print video_info


    def get_video_uri(self):

        for resolution in sorted(RESOLUTIONS.values(), reverse=True):
            if urllib.urlopen('http://www.youtube.com/get_video?video_id={0}&t={1}&eurl=&el=embedded&ps=default&fmt={2}'.format(self.id, self.token, resolution)).getcode() != 404:
                return 'http://www.youtube.com/get_video?video_id={0}&t={1}&eurl=&el=embedded&ps=default&fmt={2}'.format(self.id, self.token, resolution)


class YouTube(object):

    def __init__(self):

        self.service = gdata.youtube.service.YouTubeService()
        self.service.developer_key = DEVELOPER_KEY


    def search(self, search_string, order_by=RELEVANCE):

        query = gdata.youtube.service.YouTubeVideoQuery()
        query.vq = search_string
        query.orderby = order_by
        query.racy = 'include'
        feed = self.service.YouTubeQuery(query)
        
        for entry in feed.entry:
            v = YouTubeVideo(entry)
            print v.get_video_uri()


if __name__ == '__main__':
    yt = YouTube()
    yt.search('Annoying orange')
