import os
import unittest
from unittest.mock import Mock, patch

import main


class WindowSelectionTests(unittest.TestCase):
    def setUp(self):
        self.app = main.WindowPositionApp.__new__(main.WindowPositionApp)
        self.app.root = Mock()
        self.app.root.winfo_id.return_value = 100
        self.app.root_hwnd = 100
        self.app.status = Mock()
        self.app.slots = {}
        self.app.hotkey_queue = main.queue.Queue()
        self.app.buttons = []
        self.app.arm_save("1")

    def test_native_tk_wrapper_is_excluded(self):
        root = main.tk.Tk()
        try:
            root.withdraw()
            root.update_idletasks()
            self.app.root = root
            self.app.root_hwnd = int(root.winfo_id())
            wrapper = main.win32gui.GetAncestor(self.app.root_hwnd, main.win32con.GA_ROOT)
            self.assertNotEqual(wrapper, self.app.root_hwnd)
            self.assertTrue(self.app.is_own_window(wrapper))
        finally:
            root.destroy()

    def test_own_process_dialog_is_excluded(self):
        with patch.object(main.win32process, "GetWindowThreadProcessId", return_value=(1, os.getpid())):
            self.assertTrue(self.app.is_own_window(300))

    def test_direct_save_cannot_store_own_window(self):
        self.app.window_info = Mock()
        with patch.object(self.app, "is_own_window", return_value=True):
            self.app.save_selected_window("1", 200)
        self.app.window_info.assert_not_called()
        self.assertEqual(self.app.slots, {})
        self.assertEqual(self.app.pending_save_key, "1")

    def test_waits_for_stable_external_selection(self):
        self.app.pending_save_started = 10.0
        self.app.save_selected_window = Mock()
        with patch.object(self.app, "foreground_window", side_effect=[None, 200, None, 200, 200, 200]), \
                patch.object(main.time, "monotonic", side_effect=[10.1, 10.2, 10.4, 10.5, 10.9, 11.1]):
            for _ in range(5):
                self.app.poll_hotkeys()
                self.app.save_selected_window.assert_not_called()
            self.app.poll_hotkeys()
        self.app.save_selected_window.assert_called_once_with("1", 200)


if __name__ == "__main__":
    unittest.main()
