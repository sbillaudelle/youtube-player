import unittest
import youtube

class YouTubePlayerTestCase(unittest.TestCase):
    def test_resolution_warning(self):
        video = youtube.Video(video_id=1337)
        video._warn_unknown_resolution(resolution_id=42)


if __name__ == '__main__':
    unittest.main()
