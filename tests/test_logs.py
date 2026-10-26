import logging
import os
import tempfile
import threading
import unittest
from unittest import mock

from votyper import app, logs


class LogFileTest(unittest.TestCase):
    def setUp(self):
        self.state = tempfile.TemporaryDirectory()
        patcher = mock.patch.dict(os.environ, {"XDG_STATE_HOME": self.state.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.state.cleanup)
        self.addCleanup(self.drop_handlers)

    @staticmethod
    def drop_handlers():
        for handler in list(logs.log.handlers):
            handler.close()
            logs.log.removeHandler(handler)

    def read_log(self) -> str:
        with open(logs.log_path()) as f:
            return f.read()

    def test_messages_reach_the_file_with_a_timestamp(self):
        logs.setup()
        logs.log.info("hello log")
        line = self.read_log().splitlines()[-1]
        self.assertIn("INFO hello log", line)
        self.assertRegex(line, r"^\d{4}-\d\d-\d\d ")

    def test_debug_lines_only_appear_in_debug_mode(self):
        logs.setup(debug=False)
        logs.log.debug("quiet")
        self.assertNotIn("quiet", self.read_log())
        self.drop_handlers()
        logs.setup(debug=True)
        logs.log.debug("loud")
        self.assertIn("loud", self.read_log())

    def test_crash_in_a_thread_is_logged(self):
        logs.setup()
        thread = threading.Thread(target=lambda: 1 / 0, name="worker")
        thread.start()
        thread.join()
        self.assertIn("thread worker crashed", self.read_log())
        self.assertIn("ZeroDivisionError", self.read_log())

    def test_start_failure_is_logged_and_returns_an_error_code(self):
        with mock.patch.object(app, "App", side_effect=RuntimeError("no /dev/uinput")):
            self.assertEqual(app.main(), 1)
        self.assertIn("could not start", self.read_log())
        self.assertIn("no /dev/uinput", self.read_log())

    def test_unwritable_log_location_does_not_break_setup(self):
        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": "/proc/forbidden"}):
            logs.setup()                    # must warn, not raise


if __name__ == "__main__":
    unittest.main()
