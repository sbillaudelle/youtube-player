import unittest
import common
import os

class UtilsTestCase(unittest.TestCase):
    def test_named_tempfile(self):
        with common.NamedTempfile('somefile', 'cream/youtube-player-tests') as f:
            f.write('hello world')
        # assume we are on Linux with default settings:
        self.assert_(os.path.exists('/tmp/cream/youtube-player-tests/somefile'))
        tmpfile2 = common.NamedTempfile('somefile', 'cream/youtube-player-tests')
        with tmpfile2.file:
            self.assertEqual(tmpfile2.file.read(), 'hello world')

        tmpfile3 = common.NamedTempfile('some-file-that-will-be-automatically-deleted',
                                        'cream/youtube-player-tests',
                                        auto_delete=True)
        self.assert_(os.path.exists('/tmp/cream/youtube-player-tests/some-file-that-will-be-automatically-deleted'))
        del tmpfile3
        self.assert_(not os.path.exists('/tmp/cream/youtube-player-tests/some-file-that-will-be-automatically-deleted'))

if __name__ == '__main__':
    unittest.main()
