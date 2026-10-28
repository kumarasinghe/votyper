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

    def button_row(self):
        for child in self.ui._dialog.winfo_children():
            kids = child.winfo_children()
            if kids and all(k.winfo_class() == "Button" for k in kids):
                return kids
        self.fail("no row of buttons")

    def test_buttons_sit_side_by_side_above_the_text(self):
        self.ui._root.update()
        buttons = self.button_row()
        self.assertEqual([b.cget("text") for b in buttons],
                         ["Change hotkey…", "Meeting mode", "Open transcriptions", "Quit votyper"])
        self.assertEqual(len({b.winfo_y() for b in buttons}), 1)
        self.assertLess(buttons[0].winfo_rooty(), self.ui._text.winfo_rooty())

    def test_header_has_the_logo_on_the_left_and_the_version_on_the_right(self):
        self.ui._root.update()
        header = self.ui._dialog.winfo_children()[0]
        logo, name, version = sorted(header.winfo_children(), key=lambda w: w.winfo_x())
        self.assertEqual(name.cget("text"), "Votyper")
        self.assertTrue(logo.cget("image"))
        self.assertTrue(version.cget("text").startswith("version "))
        self.assertGreater(version.winfo_x(), name.winfo_x())

    def test_the_hotkey_is_not_shown_as_text_but_in_a_tooltip(self):
        self.ui._root.update()
        labels = [w.cget("text") for w in self.ui._dialog.winfo_children()[:1][0].winfo_children()]
        self.assertNotIn("CTRL+SPACE", labels)
        change = self.button_row()[0]
        change.event_generate("<Enter>")
        self.ui._root.update()
        self.ui._root.after(600, self.ui._root.quit)
        self.ui._root.mainloop()                # lets the tooltip delay pass
        tips = [w for w in change.winfo_children() if w.winfo_class() == "Toplevel"]
        texts = [c.cget("text") for t in tips for c in t.winfo_children()]
        self.assertIn("Current hotkey: CTRL+SPACE", texts)

    def test_text_can_be_selected_and_copied_with_the_keyboard(self):
        self.ui.show_transcript_line("copy me", "")
        self.ui.show_transcript_line("and me", "")
        text = self.ui._text
        self.ui._dialog.update()
        text.focus_force()
        self.ui._root.update()
        text.event_generate("<Control-a>")
        text.event_generate("<Control-c>")
        self.assertEqual(self.ui._root.clipboard_get().strip(), "copy me\nand me")
        self.assertEqual(str(text.cget("state")), "disabled")

    def test_copy_takes_only_the_selection(self):
        self.ui.show_transcript_line("first", "")
        self.ui.show_transcript_line("second", "")
        text = self.ui._text
        text.tag_add("sel", "2.0", "2.6")
        text.event_generate("<<Copy>>")
        self.assertEqual(self.ui._root.clipboard_get(), "second")

    def test_copy_with_nothing_selected_takes_everything(self):
        self.ui.show_transcript_line("first", "")
        self.ui._text.event_generate("<<Copy>>")
        self.assertEqual(self.ui._root.clipboard_get().strip(), "first")

    def test_the_selection_survives_new_text(self):
        self.ui.show_transcript_line("first", "")
        text = self.ui._text
        text.tag_add("sel", "1.0", "1.5")
        self.ui.show_transcript_line(None, "typing")
        self.ui.show_transcript_line("second", "")
        self.assertEqual(text.get("sel.first", "sel.last"), "first")

    def test_reopening_in_a_meeting_restores_the_transcript(self):
        self.ui._dialog.destroy()
        self.ui._text = None
        self.ui.show_settings("ctrl+space", lambda d: None, lambda: None, lambda: None,
                              lambda: None, lambda: None, "/tmp/x.txt", ["one", "two"], "thr")
        self.assertEqual(self.shown(), "one\ntwo\nthr")


if __name__ == "__main__":
    unittest.main()
