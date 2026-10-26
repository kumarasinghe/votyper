import re
import unittest

from votyper import __version__
from votyper.icon import ICON_FILE

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class IconTest(unittest.TestCase):
    def test_icon_ships_with_the_package_and_is_a_png(self):
        self.assertTrue(ICON_FILE.is_file(), f"missing {ICON_FILE}")
        self.assertEqual(ICON_FILE.read_bytes()[:8], PNG_SIGNATURE)


class VersionTest(unittest.TestCase):
    def test_version_looks_like_major_minor_patch(self):
        self.assertRegex(__version__, r"^\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
