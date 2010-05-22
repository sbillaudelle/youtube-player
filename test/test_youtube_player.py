import datetime
import unittest
import youtube

YOUTUBE_DEVELOPER_KEY = 'AI39si5ABc6YvX1MST8Q7O-uxN7Ra1ly-KKryqH7pc0fb8MrMvvVzvqenE2afoyjQB276fWVx1T3qpDi7FFO6tkVs7JqqTmRRA'

class YouTubePlayerTestCase(unittest.TestCase):
    _some_video = None

    def setUp(self):
        self.api = youtube.API(YOUTUBE_DEVELOPER_KEY)

    def get_some_video(self):
        if self._some_video:
            return self._some_video
        search_results = self.api.search('google i/o keynote full length')
        for result in search_results:
            self._some_video = result
            return result

    def test_resolution_warning(self):
        video = youtube.Video(video_id=1337)
        video._warn_unknown_resolution(resolution_id=42)

    def test_from_feed(self):
        video = self.get_some_video()
        for attr, expected_type in (('datetime', datetime.datetime),
                                    ('tags', list),
                                    ('duration', int),
                                    ('view_count', int),
                                    ('rating', float)):
            self.assert_(isinstance(getattr(video, attr), expected_type))

    def test_video_info(self):
        video = self.get_some_video()
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
        self.assert_(video.thumbnail_path)


if __name__ == '__main__':
    unittest.main()
