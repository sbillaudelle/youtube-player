#!/usr/bin/env python
import youtube
import sys

video_id = sys.argv[1]
if 'v=' in video_id:
    import urlparse
    video_id = urlparse.parse_qs(urlparse.urlparse(video_id).query)['v'][0]
video = youtube.YouTubeVideo(video_id=video_id)

try:
    resolution = sys.argv[2]
except IndexError:
    resolution = video.resolutions[0]
else:
    # TODO: Think about new names for stuff like 480p
    resolution = {
        'low' : '360p',
        'middle' : '720p',
        'mid' : '720p',
        'high' : '1080p',
        '360' : '360p',
        '720' : '720p',
        '1080' : '1080p'
    }.get(resolution, resolution)
    if resolution not in video.resolutions:
        print "Warning: Requested video {video_id} is not available in {resolution}!".format(**globals())
        resolution = video.resolutions[0]

video_url = video.get_video_url(resolution=resolution)

print "mp4 URL for {video_id} ({resolution}) is\n{video_url}".format(**globals())
