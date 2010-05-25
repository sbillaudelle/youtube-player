import re
import urllib2
import urlparse
import datetime
from lxml.etree import XMLSyntaxError, parse as parse_xml, \
                       fromstring as parse_xml_from_string

import gdata.youtube
import gdata.youtube.service
from cream.util import cached_property
from cream.util.dicts import ordereddict
from common import NamedTempfile


VIDEO_INFO_URL      = 'http://www.youtube.com/get_video_info?video_id={video_id}'
SUBTITLE_LIST_URL   = 'http://video.google.com/timedtext?tlangs=1&type=list&v={video_id}'
SUBTITLE_GET_URL    = 'http://video.google.com/timedtext?type=track&v={video_id}&lang={language_code}'

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

        def _split_tags(s):
            if not s:
                return None
            return map(str.split, s.split(','))

        return cls(
            title       = feed_entry.media.title.text,
            datetime    = _to_datetime(feed_entry.published.text),
            description = feed_entry.media.description.text,
            category    = feed_entry.media.category[0].text,
            tags        = _split_tags(feed_entry.media.keywords.text),
            uri         = feed_entry.media.player.url,
            duration    = int(feed_entry.media.duration.seconds),
            view_count  = feed_entry.statistics and int(feed_entry.statistics.view_count) or None,
            rating      = feed_entry.rating and float(feed_entry.rating.average) or None,
            video_id    = feed_entry.id.text.split('/')[-1]
        )

    #: URL to the video's thumbnail
    #: (``request_video_info`` has to be called before accessing this property``)
    thumbnail_url   = _VideoInfoProperty('thumbnail_url', allow_none=True)
    has_subtitles   = _VideoInfoProperty('has_cc', type=lambda x:x == 'True')


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
        tempfile = NamedTempfile(self.video_id+'-info')
        if tempfile.isempty():
            raw_data = urllib2.urlopen(VIDEO_INFO_URL.format(video_id=self.video_id)).read()
            with tempfile:
                tempfile.file.write(raw_data)
        else:
            with tempfile:
                raw_data = tempfile.file.read()

        info = urlparse.parse_qs(raw_data)
        if info['status'][0] != 'ok':
            try:
                video_title = "('" + self.title + "')"
            except AttributeError:
                video_title = ''
            exc = YouTubeError(
                "Could not get video information about video '%s' %s: %s" % (
                    self.video_id, video_title, info['reason'][0]
            ))
            exc.reason = info['reason'][0]
            raise exc

        else:
            self._video_info = info

    @property
    def video_info(self):
        """
        A dictionary containing additional video meta data.

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

    @staticmethod
    def _cleanup_stream_url(url):
        """
        Removes all unnecessary information from the given stream ``url``
        to protect the user's privacy as good as possible.
        """
        # XXX: Stripping away IP information seems to not work
        # with all videos, so we disable that until we know
        # in which cases we can safely remove the IP stuff.
        #regex_substitutions = (
        #    ('ip=\d+\.\d+\.\d+\.\d+', 'ip=0.0.0.0'),
        #    ('ipbits=\d+', 'ipbits=0')
        #)
        #for pattern, replace in regex_substitutions:
        #    url = re.sub(pattern, replace, url)
        return url


    def _warn_unknown_resolution(self, resolution_id):
        print RESOLUTION_WARNING.format(resolution_id=resolution_id,
                                        video_id=self.video_id)

    def download_thumbnail(self):
        """
        Downloads the video thumbnail to the tempfile directory and returns
        its full, absolute file path.

        (``request_video_info`` has to be called before accessing this property)
        """
        return self._thumbnail_path

    @cached_property
    def _thumbnail_path(self):
        if self.thumbnail_url is None:
            return None

        tempfile = NamedTempfile('thumbnail-'+self.video_id)
        if tempfile.isempty():
            # download the thumbnail if not already done so.
            with tempfile:
                tempfile.file.write(urllib2.urlopen(self.thumbnail_url).read())
        return tempfile.name

    def request_subtitle_list(self):
        if hasattr(self, '_subtitle_list'):
            # All work is done, do nothing.
            return self._subtitle_list

        self._subtitle_list = dict()
        self._subtitles = dict()
        try:
            # XXX: The following breaks lxml and I don't know why.
            # I'll file a bug report.
            #xml = parse_xml(SUBTITLE_LIST_URL.format(video_id=self.video_id))
            url = SUBTITLE_LIST_URL.format(video_id=self.video_id)
            xmltree = parse_xml_from_string(urllib2.urlopen(url).read())
        except XMLSyntaxError, exc:
            if str(exc) not in ('Document is empty', 'None'):
                raise
            else:
                # no subtitles
                return
        for child in xmltree:
            self._subtitle_list[child.attrib['lang_code']] = child.attrib

    @property
    def subtitle_list(self):
        """
        A dictionary containing information about all subtitles available
        for this video. The dict looks like this::

             {
                'de': {'lang_code': 'de',
                       'lang_translated': 'German',
                       'id': '5',
                       'lang_original': 'Deutsch'
                      },
                'hu': {'lang_code': 'hu',
                       'lang_translated': 'Hungarian',
                       'id': '23',
                       'lang_original': 'Magyar'
                      },
                'fa': {'lang_code': 'fa',
                       'lang_translated': 'Persian',
                       'id': '49',
                       'lang_original': u'\u0641\u0627\u0631\u0633\u06cc'
                      },
                ...
            }

        Has to be requested from YouTube using ``request_subtitle_list`` or a
        ``RuntimeError`` will be raised when trying to access this property.
        """
        try:
            return self._subtitle_list
        except AttributeError:
            raise RuntimeError("Cannot access 'subtitle_list': Make sure to request "
                               "it using 'request_subtitle_list' first.")

    def download_subtitle(self, language, format='xml'):
        """
        Downloads the subtitle for ``language`` where ``language`` is
        a language code of 2 chars (e.g., *en*) and returns a temporary
        file the subtitles were downloaded to.

        The ``format`` parameter specifies the file format the subtitles
        shall be returned in. Currently supported are

        * 'xml': (default) returns the original data received from YouTube.
        * 'mpl2': returns the subtitles in MPL2 format.
        """
        if language in self._subtitles:
            # All work done, just returned the cached subtitles.
            return self._subtitles[language]

        tempfile = NamedTempfile(self.video_id+'-subtitle-'+language+'.xml')
        if tempfile.isempty():
            subtitle_url = SUBTITLE_GET_URL.format(video_id=self.video_id, language_code=language)
            with tempfile:
                tempfile.file.write(urllib2.urlopen(subtitle_url).read())
            if tempfile.isempty():
                raise YouTubeError("Subtitle for video '{0}' not available in '{1}'"\
                                   .format(self.video_id, language))

        if format == 'xml':
            return tempfile.name
        #elif format == 'json':
        #    return self._subtitle_file_to_json(tempfile.name, language)
        elif format == 'mpl2':
            return self._subtitle_file_as_mpl2(tempfile.name, language)
        else:
            raise TypeError("Unknown subtitle format '%s'" % format)


    def _subtitle_file_as_mpl2(self, xmlfile, language):
        # see http://lists.mplayerhq.hu/pipermail/mplayer-users/2003-February/030222.html
        tempfile = NamedTempfile(self.video_id+'-subtitle-'+language+'.mpl2')
        if not tempfile.isempty():
            return tempfile.name
        with tempfile:
            xmltree = parse_xml(xmlfile).getroot()
            for element in xmltree:
               start = int(float(element.attrib['start'])*1000)
               end = start + int(float(element.attrib['dur'])*1000)
               text = element.text.replace('\n', '|')
               tempfile.file.write('[{0}][{1}]{2}\n'.format(start, end, text))
        return tempfile.name


class API(object):

    def __init__(self, developer_key):

        self.service = gdata.youtube.service.YouTubeService()
        self.service.developer_key = developer_key


    def search(self, search_string, order_by=SORT_BY_RELEVANCE, **query_args):

        query = gdata.youtube.service.YouTubeVideoQuery()
        query.vq = search_string
        query.orderby = order_by
        query.racy = 'include'
        query.update(query_args)
        feed = self.service.YouTubeQuery(query)

        for entry in feed.entry:
            yield Video.from_feed_entry(entry)
