import os
import re
import stat
import tempfile
import unittest
from unittest import mock

from votyper.hotkey import Hotkey
from votyper.meeting import Meeting


class MeetingTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.meeting = Meeting(os.path.join(self.folder.name, "meetings"))
        self.addCleanup(self.meeting.stop)      # closes the file

    def saved(self):
        with open(self.meeting.path, encoding="utf-8") as f:
            return f.read()

    def test_file_is_named_after_the_utc_start_time_and_is_private(self):
        path = self.meeting.start()
        self.assertRegex(os.path.basename(path), r"^\d{8}T\d{6}Z\.txt$")
        self.assertEqual(stat.S_IMODE(os.stat(path).st_mode), 0o600)

    def test_two_meetings_in_one_second_do_not_share_a_file(self):
        with mock.patch("votyper.meeting.datetime") as clock:
            clock.now.return_value.strftime.return_value = "20260101T000000Z"
            first = self.meeting.start()
            other = Meeting(os.path.dirname(first))
            second = other.start()
        self.addCleanup(other.stop)
        self.assertNotEqual(first, second)
        self.assertTrue(re.search(r"-2\.txt$", second))

    def test_only_finished_sentences_reach_the_disk(self):
        self.meeting.start()
        self.assertIsNone(self.meeting.heard("hello wor", final=False))
        self.assertEqual(self.saved(), "")
        self.assertEqual(self.meeting.live, "hello wor")
        self.assertEqual(self.meeting.heard("hello world", final=True), "hello world")
        self.assertEqual(self.meeting.heard("second one", final=True), "second one")
        self.assertEqual(self.saved(), "hello world\nsecond one\n")
        self.assertEqual(self.meeting.live, "")

    def test_empty_sentences_are_not_saved(self):
        self.meeting.start()
        self.assertEqual(self.meeting.heard("  ", final=True), "")
        self.assertEqual(self.saved(), "")

    def test_stopping_saves_a_sentence_cut_off_mid_way(self):
        self.meeting.start()
        self.meeting.heard("unfinished thought", final=False)
        self.meeting.stop()
        self.assertEqual(self.saved(), "unfinished thought\n")

    def test_stop_without_a_meeting_does_nothing(self):
        self.meeting.stop()

    def test_a_new_meeting_starts_with_an_empty_transcript(self):
        self.meeting.start()
        self.meeting.heard("old", final=True)
        self.meeting.stop()
        self.meeting.start()
        self.assertEqual(self.meeting.lines, [])


class AppMeetingTest(unittest.TestCase):
    """The app's rules: the hotkey is off in a meeting, and nothing is typed."""

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        for name in ("UI", "Keyboard", "KeyListener", "Tray", "Dictation", "IdleTimer",
                     "Blinker", "play_start", "play_stop"):
            patcher = mock.patch(f"votyper.app.{name}")
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = mock.patch("votyper.app.Meeting", lambda: Meeting(os.path.join(folder.name, "m")))
        patcher.start()
        self.addCleanup(patcher.stop)
        from votyper.app import App
        self.app = App(Hotkey.parse("ctrl+space"))
        self.addCleanup(self.app.meeting.stop)
        self.app.typer = mock.Mock()
        self.app.state = "idle"

    def test_meeting_starts_and_stops(self):
        self.app.toggle_meeting()
        self.assertEqual(self.app.state, "meeting")
        self.app.dictation.start.assert_called_once()
        self.app.toggle_meeting()
        self.assertEqual(self.app.state, "idle")
        self.app.dictation.stop.assert_called_once()

    def test_hotkey_does_nothing_during_a_meeting(self):
        self.app.toggle_meeting()
        self.app.toggle()
        self.assertEqual(self.app.state, "meeting")
        self.app.dictation.start.assert_called_once()

    def test_speech_goes_to_the_transcript_and_is_never_typed(self):
        self.app.toggle_meeting()
        self.app._heard(1, "hello there", True)
        self.app.typer.update.assert_not_called()
        self.assertEqual(self.app.meeting.lines, ["hello there"])

    def test_starting_a_meeting_stops_typing_first(self):
        self.app.state = "listening"
        self.app.toggle_meeting()
        self.assertEqual(self.app.state, "meeting")
        self.app.dictation.stop.assert_called_once()
        self.app.typer.reset.assert_called()

    def test_speech_is_typed_outside_a_meeting(self):
        self.app.state = "listening"
        self.app._heard(1, "hello", False)
        self.app.typer.update.assert_called_once_with(1, "hello")

    def test_meeting_button_is_ignored_while_the_model_loads(self):
        self.app.state = "loading"
        self.app.toggle_meeting()
        self.assertEqual(self.app.state, "loading")

    def test_a_sleeping_app_wakes_up_for_a_meeting(self):
        self.app.state = "sleeping"
        self.app.toggle_meeting()
        self.app.dictation.load.assert_called_once()
        self.assertEqual(self.app.state, "meeting")

    def test_the_icon_blinks_during_a_meeting(self):
        self.app.toggle_meeting()
        self.app.tray.update.reset_mock()
        self.app._blink(False)
        self.assertEqual(self.app.tray.update.call_args[0][0], "listening_dim")

    def test_open_folder_button_shows_the_transcripts_folder(self):
        with mock.patch("votyper.app.open_folder") as opener:
            self.app.show_settings()
            on_open_folder = self.app.ui.show_settings.call_args[0][4]
            on_open_folder()
            opener.assert_called_once_with(self.app.meeting.folder)


class OpenFolderTest(unittest.TestCase):
    def test_creates_the_folder_and_asks_the_system_to_open_it(self):
        from votyper.folders import open_folder
        with tempfile.TemporaryDirectory() as base, mock.patch("votyper.folders.subprocess") as sp:
            target = os.path.join(base, "meetings")
            open_folder(target)
            self.assertTrue(os.path.isdir(target))
            self.assertEqual(sp.Popen.call_args[0][0][1], target)


if __name__ == "__main__":
    unittest.main()
