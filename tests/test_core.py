import time
import unittest

from votyper.hotkey import Hotkey
from votyper.hotkeys import HotkeyMatcher
from votyper.live_typer import LiveTyper


class FakeKeyboard:
    """Applies keystrokes to a string, like a text field would."""

    def __init__(self):
        self.field = ""

    def type_text(self, text):
        self.field += text

    def backspace(self, count):
        self.field = self.field[:len(self.field) - count]


class LiveTyperTest(unittest.TestCase):
    def setUp(self):
        self.kb = FakeKeyboard()
        self.typer = LiveTyper(self.kb)

    def test_growing_text_only_appends(self):
        self.typer.update(1, "hello")
        self.typer.update(1, "hello world")
        self.assertEqual(self.kb.field, "hello world")

    def test_revision_erases_only_changed_tail(self):
        self.typer.update(1, "i wreck a nice")
        self.typer.update(1, "i recognize speech")
        self.assertEqual(self.kb.field, "i recognize speech")

    def test_lines_are_separated_by_a_space(self):
        self.typer.update(1, "first")
        self.typer.update(1, "first")          # completion repeats the text
        self.typer.update(2, "second")
        self.assertEqual(self.kb.field, "first second")

    def test_reset_starts_fresh_without_leading_space(self):
        self.typer.update(1, "one")
        self.typer.reset()
        self.typer.update(1, "two")
        self.assertEqual(self.kb.field, "onetwo")

    def test_empty_text_types_nothing(self):
        self.typer.update(1, "  ")
        self.assertEqual(self.kb.field, "")


class HotkeyTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(Hotkey.parse("F9"), Hotkey("f9"))
        self.assertEqual(Hotkey.parse("Ctrl+Alt+Space"),
                         Hotkey("space", frozenset({"ctrl", "alt"})))

    def test_str_round_trips(self):
        self.assertEqual(str(Hotkey.parse("alt+ctrl+f9")),
                         "ctrl+alt+f9")

    def test_rejects_modifier_only(self):
        with self.assertRaises(ValueError):
            Hotkey.parse("ctrl")


class MatcherTest(unittest.TestCase):
    def setUp(self):
        self.hits = []
        self.m = HotkeyMatcher()
        self.m.bind(Hotkey.parse("ctrl+f9"), lambda: self.hits.append(1))

    def press(self, *keys):
        for k in keys:
            self.m.feed(k, True)
        for k in reversed(keys):
            self.m.feed(k, False)
        time.sleep(0.05)                    # callbacks run on a thread

    def test_needs_the_right_modifiers(self):
        self.press("f9")
        self.press("ctrl", "shift", "f9")
        self.assertEqual(self.hits, [])
        self.press("ctrl", "f9")
        self.assertEqual(self.hits, [1])

    def test_auto_repeat_fires_once(self):
        self.m.feed("ctrl", True)
        for _ in range(5):
            self.m.feed("f9", True)
        time.sleep(0.05)
        self.assertEqual(self.hits, [1])

    def test_capture_takes_next_combo_instead_of_firing(self):
        got = []
        self.m.capture(got.append)
        self.press("ctrl", "f9")            # would normally fire the binding
        self.press("alt", "x")
        self.assertEqual(self.hits, [])
        self.assertEqual(got, [Hotkey.parse("ctrl+f9")])    # one-shot

    def test_modifier_alone_is_not_captured(self):
        got = []
        self.m.capture(got.append)
        self.press("ctrl")
        self.assertEqual(got, [])


if __name__ == "__main__":
    unittest.main()
