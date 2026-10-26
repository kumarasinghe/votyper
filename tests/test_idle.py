import threading
import time
import unittest

from votyper.idle import IdleTimer


class IdleTimerTest(unittest.TestCase):
    def setUp(self):
        self.fired = threading.Event()
        self.count = 0

    def callback(self):
        self.count += 1
        self.fired.set()

    def test_fires_once_after_the_quiet_period(self):
        IdleTimer(0.05, self.callback).restart()
        self.assertTrue(self.fired.wait(1))
        time.sleep(0.1)
        self.assertEqual(self.count, 1)

    def test_cancel_prevents_firing(self):
        timer = IdleTimer(0.05, self.callback)
        timer.restart()
        timer.cancel()
        time.sleep(0.15)
        self.assertEqual(self.count, 0)

    def test_restart_pushes_the_deadline_back(self):
        timer = IdleTimer(0.2, self.callback)
        timer.restart()
        time.sleep(0.12)
        timer.restart()                     # 0.12 s in, so it must not fire at 0.2 s
        time.sleep(0.12)
        self.assertEqual(self.count, 0)
        self.assertTrue(self.fired.wait(1))
        self.assertEqual(self.count, 1)

    def test_cancel_without_a_timer_is_harmless(self):
        IdleTimer(1, self.callback).cancel()


if __name__ == "__main__":
    unittest.main()
