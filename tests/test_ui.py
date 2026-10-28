import os
import unittest

try:
    from votyper.ui import UI
except ImportError:             # pragma: no cover
    UI = None


@unittest.skipUnless(UI and os.environ.get("DISPLAY"), "needs tkinter and a display")
class TranscriptWindowTest(unittest.TestCase):
    def setUp(self):
        self.ui = UI()
        self.addCleanup(self.ui._root.destroy)
        self.ui.show_settings("ctrl+space", lambda done: None, lambda: None, lambda: None,
                              lambda: None, lambda: None)

    def shown(self):
        return self.ui._text.get("1.0", "end-1c")

    def test_finished_sentences_are_appended_and_the_live_one_is_replaced(self):
        self.ui.show_transcript_line(None, "hel")
        self.ui.show_transcript_line(None, "hello")
        self.assertEqual(self.shown(), "hello")
        self.ui.show_transcript_line("hello world", "")
        self.ui.show_transcript_line(None, "next")
        self.assertEqual(self.shown(), "hello world\nnext")
        self.ui.show_transcript_line("next one", "")
        self.assertEqual(self.shown(), "hello world\nnext one\n")

    def test_text_cannot_be_typed_into(self):
        self.assertEqual(str(self.ui._text.cget("state")), "disabled")

    def test_button_follows_the_meeting_state(self):
        self.ui.show_meeting_mode(True)
        self.assertEqual(self.ui._meeting_button.cget("text"), "Stop meeting")
        self.ui.show_meeting_mode(False)
        self.assertEqual(self.ui._meeting_button.cget("text"), "Meeting mode")

    def test_a_new_meeting_clears_the_text(self):
        self.ui.show_transcript_line("old", "")
        self.ui.start_transcript("/tmp/x.txt")
        self.assertEqual(self.shown(), "")
        self.assertIn("/tmp/x.txt", self.ui._status.cget("text"))

    def test_buttons_sit_side_by_side_above_the_text(self):
        self.ui._root.update()
        buttons = [w for w in self.ui._dialog.winfo_children()[3].winfo_children()]
        ys = {b.winfo_y() for b in buttons}
        self.assertEqual(len(buttons), 4)
        self.assertEqual(len(ys), 1)
        self.assertLess(buttons[0].winfo_rooty(), self.ui._text.winfo_rooty())

    def test_reopening_in_a_meeting_restores_the_transcript(self):
        self.ui._dialog.destroy()
        self.ui._text = None
        self.ui.show_settings("ctrl+space", lambda d: None, lambda: None, lambda: None,
                              lambda: None, lambda: None, "/tmp/x.txt", ["one", "two"], "thr")
        self.assertEqual(self.shown(), "one\ntwo\nthr")


if __name__ == "__main__":
    unittest.main()
