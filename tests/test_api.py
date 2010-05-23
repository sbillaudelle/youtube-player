import datetime
import unittest
import youtube

YOUTUBE_DEVELOPER_KEY = 'AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA'

BUCKET = dict()

class YouTubePlayerTestCase(unittest.TestCase):
    def setUp(self):
        self.api = youtube.API(YOUTUBE_DEVELOPER_KEY)

    def get_some_video(self, force_new=False):
        """
        Get some video that can be used to test all features
        the API implements, hence, subtitles, multiple qualities and so on.
        """
        if force_new or 'some_video' not in BUCKET:
            search_results = self.api.search('google i/o keynote full length')
            BUCKET['some_video'] = search_results.next()
        return BUCKET['some_video']

    def get_some_video_without_subtitles(self):
        if 'some_video_without_subtitles' not in BUCKET:
            search_results = self.api.search('coldmirror')
            BUCKET['some_video_without_subtitles'] = search_results.next()
        return BUCKET['some_video_without_subtitles']

    def test_resolution_warning(self):
        video = youtube.Video(video_id=1337)
        video._warn_unknown_resolution(resolution_id=42)

    #def test_cleanup_stream_url(self):
    #    url1 = 'http://foobar.org/?ip=42.21.11.13&ipbits=8'
    #    self.assertEqual('http://foobar.org/?ip=0.0.0.0&ipbits=0',
    #                     youtube.Video._cleanup_stream_url(url1))

    def test_from_feed(self):
        video = self.get_some_video()
        for attr, expected_type in (('datetime', datetime.datetime),
                                    ('tags', list),
                                    ('duration', int),
                                    ('view_count', int),
                                    ('rating', float)):
            self.assert_(isinstance(getattr(video, attr), expected_type))

    def test_video_info(self):
        video = self.get_some_video(force_new=True)
        self.assertRaises(RuntimeError, lambda: video.video_info)
        video.request_video_info()
        self.assert_(video.video_info)

    def test_video_info_properties(self):
        video = self.get_some_video()
        video.request_video_info()
        self.assert_(isinstance(video.datetime, datetime.datetime))
        self.assert_(video.thumbnail_url)
        self.assert_(video.stream_urls)

    def test_video_thumbnail(self):
        video = self.get_some_video()
        video.request_video_info()
        self.assert_(video.download_thumbnail())

    def test_subtitle_list(self):
        video = self.get_some_video(force_new=True)
        self.assertRaises(RuntimeError, lambda: video.subtitle_list)
        video.request_subtitle_list()
        self.assert_(video.subtitle_list)
        self.assert_('en' in video.subtitle_list)

        video_without_subtitles = self.get_some_video_without_subtitles()
        video_without_subtitles.request_subtitle_list()
        self.assert_(not video_without_subtitles.subtitle_list)

    def test_download_subtitle(self):
        video = self.get_some_video()
        video.request_subtitle_list()
        subtitle = video.download_subtitle('en', format='mpl2')
        self.assert_(subtitle)
        self.assert_(open(subtitle).read(1) == '[')
        # TODO: that format-checking is *very* poor :-)
        self.assertRaises(youtube.YouTubeError, video.download_subtitle, 'uu')


if __name__ == '__main__':
    unittest.main()
