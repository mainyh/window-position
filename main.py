"""Window Position - save and restore Windows application positions with Alt+1..0."""

from __future__ import annotations

import ctypes
import json
import os
import queue
import shutil
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import win32api
import win32con
import win32gui
import win32process

from icon_data import ICON_PNG_BASE64


APP_NAME = "Window Position"
FONT = "Segoe UI"
COLOR_BG = "#f3f4f6"
COLOR_CARD = "#ffffff"
COLOR_BORDER = "#d1d5db"
COLOR_TEXT = "#111827"
COLOR_MUTED = "#6b7280"
COLOR_PRIMARY = "#2563eb"
COLOR_PRIMARY_DARK = "#1e40af"
COLOR_FILLED = "#eff6ff"
COLOR_ARMED = "#fef3c7"
SLOT_COUNT = 10
MOD_ALT = 0x0001
WM_HOTKEY = 0x0312
VK_CODES = [ord(str(i)) for i in range(1, 10)] + [ord("0")]
DWMWA_CLOAKED = 14
SAVE_WAIT_SECONDS = 60
SAVE_STABLE_SECONDS = 0.5


def data_path() -> Path:
    root = Path(os.environ.get("APPDATA", Path.home()))
    base = root / "WindowPosition"
    base.mkdir(parents=True, exist_ok=True)
    target = base / "slots.json"
    legacy = root / "WindowSlot" / "slots.json"  # data from before the rename
    if not target.exists() and legacy.exists():
        try:
            shutil.copyfile(legacy, target)
        except OSError:
            pass
    return target


def resource_path(name: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / name


def is_window_cloaked(hwnd: int) -> bool:
    try:
        cloaked = wintypes.DWORD()
        result = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return result == 0 and cloaked.value != 0
    except Exception:
        return False


class WindowPositionApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root_hwnd = int(root.winfo_id())
        self.root.title(APP_NAME)
        self.set_app_icon()
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.slots: dict[str, dict] = self.load_slots()
        self.buttons: list[ttk.Button] = []
        self.status = tk.StringVar(value="원하는 앱을 앞에 띄운 뒤 슬롯을 저장하세요.")
        self.registered_hotkeys: list[int] = []
        self.hotkey_queue: queue.Queue = queue.Queue()
        self.pending_save_key: str | None = None
        self.pending_save_started = 0.0
        self.save_candidate_hwnd: int | None = None
        self.save_candidate_started = 0.0
        self._build_ui()
        # Size the window to its content so no empty space is left below the button.
        self.root.update_idletasks()
        width, height = 520, self.root.winfo_reqheight()
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(width, height)
        self.root.after(100, self.register_hotkeys)
        self.root.after(150, self.poll_hotkeys)

    def set_app_icon(self) -> None:
        # The embedded PNG is the reliable path: it needs no bundled file, so the
        # window and taskbar never fall back to Tk's default feather icon.
        try:
            self.icon_image = tk.PhotoImage(data=ICON_PNG_BASE64)
            self.root.iconphoto(True, self.icon_image)
        except tk.TclError:
            pass
        try:
            self.root.iconbitmap(str(resource_path("icon.ico")))
        except tk.TclError:
            pass

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(background=COLOR_BG)
        style.configure("TFrame", background=COLOR_BG)
        style.configure("Header.TFrame", background=COLOR_PRIMARY)
        style.configure("Header.TLabel", background=COLOR_PRIMARY, foreground="#ffffff", font=(FONT, 16, "bold"))
        style.configure("HeaderSub.TLabel", background=COLOR_PRIMARY, foreground="#dbeafe", font=(FONT, 9))
        style.configure("TLabel", background=COLOR_BG, foreground=COLOR_TEXT, font=(FONT, 9))
        style.configure("Hint.TLabel", foreground=COLOR_MUTED)
        style.configure("Status.TLabel", background=COLOR_CARD, foreground=COLOR_TEXT, padding=(12, 10))
        style.configure("Card.TFrame", background=COLOR_BORDER)
        slot_base = dict(font=(FONT, 10), padding=(12, 10), anchor="w", relief="flat", borderwidth=1, focusthickness=0)
        for name, bg, fg, hover in (
            ("Empty", COLOR_CARD, COLOR_MUTED, "#f1f5f9"),
            ("Filled", COLOR_FILLED, COLOR_PRIMARY_DARK, "#dbeafe"),
            ("Armed", COLOR_ARMED, "#92400e", "#fde68a"),
        ):
            style.configure(f"{name}.Slot.TButton", background=bg, foreground=fg, bordercolor=COLOR_BORDER, **slot_base)
            style.map(f"{name}.Slot.TButton", background=[("active", hover)])
        style.configure("Quit.TButton", font=(FONT, 9), padding=(14, 6), background=COLOR_CARD, foreground=COLOR_TEXT, bordercolor=COLOR_BORDER)
        style.map("Quit.TButton", background=[("active", "#f1f5f9")])

    def _build_ui(self) -> None:
        self._setup_styles()
        header = ttk.Frame(self.root, style="Header.TFrame", padding=(20, 16))
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="창의 위치와 크기를 저장하고 Alt+숫자로 복원합니다",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        body = ttk.Frame(self.root, padding=(20, 16, 20, 16))
        body.pack(fill="both", expand=True)

        grid = ttk.Frame(body)
        grid.pack(fill="x")
        for column in range(2):
            grid.columnconfigure(column, weight=1, uniform="slot")
        for index in range(SLOT_COUNT):
            slot_key = str(index + 1 if index < 9 else 0)
            row, column = divmod(index, 2)
            button = ttk.Button(grid, command=lambda key=slot_key: self.arm_save(key))
            button.grid(row=row, column=column, sticky="ew", padx=4, pady=4)
            self.buttons.append(button)
        self.refresh_buttons()

        ttk.Label(
            body,
            text="슬롯을 누른 뒤 60초 안에 저장할 창을 클릭하세요.\n0.5초간 활성 상태가 유지되면 자동 저장됩니다.",
            style="Hint.TLabel",
            justify="left",
        ).pack(anchor="w", pady=(14, 8))

        status_card = ttk.Frame(body, style="Card.TFrame", padding=1)
        status_card.pack(fill="x")
        # Fixed two-line height so long messages never push the layout around.
        tk.Label(
            status_card,
            textvariable=self.status,
            background=COLOR_CARD,
            foreground=COLOR_TEXT,
            font=(FONT, 9),
            height=2,
            anchor="w",
            justify="left",
            wraplength=440,
            padx=12,
            pady=8,
        ).pack(fill="x")

        ttk.Button(body, text="프로그램 종료", style="Quit.TButton", command=self.quit).pack(anchor="e", pady=(16, 0))

    def slot_text(self, key: str) -> str:
        item = self.slots.get(key)
        if self.pending_save_key == key:
            return f"Alt+{key}   ·   선택 대기 중…"
        if not item:
            return f"Alt+{key}   ·   비어 있음"
        name = item.get("program_name", "").strip() or self.program_name(item)
        short = name if len(name) <= 10 else name[:9] + '…'
        return f"Alt+{key}   ·   {short}"

    def slot_style(self, key: str) -> str:
        if self.pending_save_key == key:
            return "Armed.Slot.TButton"
        return "Filled.Slot.TButton" if self.slots.get(key) else "Empty.Slot.TButton"

    @staticmethod
    def program_name(item: dict) -> str:
        exe = item.get("exe", "")
        if exe:
            return Path(exe).stem or Path(exe).name
        return item.get("title", "창") or "창"

    def load_slots(self) -> dict[str, dict]:
        try:
            with data_path().open("r", encoding="utf-8") as file:
                value = json.load(file)
            return value if isinstance(value, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def write_slots(self) -> None:
        path = data_path()
        temporary = path.with_suffix(".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(self.slots, file, ensure_ascii=False, indent=2)
        temporary.replace(path)

    def foreground_window(self) -> int | None:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd or self.is_own_window(hwnd):
            return None
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return None
        return hwnd

    def is_own_window(self, hwnd: int) -> bool:
        """Exclude this process, including Tk's native wrapper and dialogs."""
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if pid == os.getpid():
                return True
            own_root = win32gui.GetAncestor(int(self.root.winfo_id()), win32con.GA_ROOT)
            target_root = win32gui.GetAncestor(hwnd, win32con.GA_ROOT)
            return hwnd == self.root_hwnd or (bool(own_root) and target_root == own_root)
        except win32gui.error:
            return hwnd == self.root_hwnd

    @staticmethod
    def window_exe(hwnd: int) -> str:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = win32api.OpenProcess(win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            try:
                return win32process.GetModuleFileNameEx(process, 0)
            finally:
                process.Close()
        except Exception:
            return ""

    def window_info(self, hwnd: int) -> dict:
        exe = self.window_exe(hwnd)
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        program_name = Path(exe).stem if exe else (win32gui.GetWindowText(hwnd) or "창")
        return {
            "hwnd": int(hwnd),
            "title": win32gui.GetWindowText(hwnd),
            "class_name": win32gui.GetClassName(hwnd),
            "exe": exe,
            "program_name": program_name,
            "rect": [left, top, right, bottom],
        }

    def arm_save(self, key: str) -> None:
        """Wait for a newly selected target window, then save after it stays active."""
        self.pending_save_key = key
        self.pending_save_started = time.monotonic()
        self.save_candidate_hwnd = None
        self.save_candidate_started = 0.0
        self.refresh_buttons()
        self.status.set(f"Alt+{key} 저장 대기 중입니다. 60초 안에 저장할 프로그램 창을 클릭하세요.")

    def save_selected_window(self, key: str, hwnd: int) -> None:
        if not hwnd or self.is_own_window(hwnd):
            self.status.set("저장할 활성 창을 찾지 못했습니다. 앱 창을 먼저 선택하세요.")
            return
        try:
            info = self.window_info(hwnd)
            self.slots[key] = info
            self.pending_save_key = None
            self.save_candidate_hwnd = None
            self.write_slots()
            self.refresh_buttons()
            self.status.set(f"Alt+{key} 슬롯에 ‘{info['program_name']}’ 위치를 저장했습니다.")
        except Exception as error:
            # Stop the poll loop from retrying the same failing save every tick.
            self.pending_save_key = None
            self.save_candidate_hwnd = None
            self.refresh_buttons()
            self.status.set(f"저장 실패: {error}")

    def find_saved_window(self, item: dict) -> int | None:
        wanted_title = item.get("title", "")
        wanted_class = item.get("class_name", "")
        wanted_exe = os.path.normcase(item.get("exe", ""))
        hwnd = int(item.get("hwnd", 0) or 0)
        # A saved handle may be stale and reused by an unrelated window after
        # the app restarts, so confirm it still belongs to the same program.
        if hwnd and win32gui.IsWindow(hwnd) and not self.is_own_window(hwnd):
            same_exe = not wanted_exe or os.path.normcase(self.window_exe(hwnd)) == wanted_exe
            same_class = not wanted_class or win32gui.GetClassName(hwnd) == wanted_class
            if same_exe and same_class:
                return hwnd
        matches: list[tuple[int, int]] = []

        def callback(candidate: int, _extra: object) -> None:
            if self.is_own_window(candidate) or not win32gui.IsWindowVisible(candidate) or is_window_cloaked(candidate):
                return
            title = win32gui.GetWindowText(candidate)
            if not title:
                return
            if wanted_exe and os.path.normcase(self.window_exe(candidate)) != wanted_exe:
                return  # never restore onto a different program
            score = 6 if wanted_exe else 0
            if title == wanted_title:
                score += 4
            if win32gui.GetClassName(candidate) == wanted_class:
                score += 2
            if score:
                matches.append((score, candidate))

        win32gui.EnumWindows(callback, None)
        return max(matches, default=(0, None))[1]

    def restore_slot(self, key: str) -> None:
        item = self.slots.get(key)
        if not item:
            self.status.set(f"Alt+{key} 슬롯은 비어 있습니다.")
            self.show_window()
            return
        hwnd = self.find_saved_window(item)
        if not hwnd:
            self.status.set(f"저장된 앱을 찾지 못했습니다: {item.get('title', '')}")
            return
        try:
            left, top, right, bottom = item["rect"]
            width, height = right - left, bottom - top
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetWindowPos(hwnd, win32con.HWND_TOP, left, top, width, height, win32con.SWP_SHOWWINDOW)
            win32gui.SetForegroundWindow(hwnd)
            self.status.set(f"Alt+{key}: ‘{win32gui.GetWindowText(hwnd)}’ 위치를 복원했습니다.")
        except Exception as error:
            self.status.set(f"복원 실패: {error}")

    def refresh_buttons(self) -> None:
        for index, button in enumerate(self.buttons):
            key = str(index + 1 if index < 9 else 0)
            button.configure(text=self.slot_text(key), style=self.slot_style(key))

    def register_hotkeys(self) -> None:
        # Tk's event loop can swallow WM_HOTKEY, so listen on a dedicated
        # thread with its own message loop and hand keys over via a queue.
        self.hotkey_thread = threading.Thread(target=self._hotkey_loop, daemon=True)
        self.hotkey_thread.start()

    def _hotkey_loop(self) -> None:
        user32 = ctypes.windll.user32
        self.hotkey_thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        failed = False
        for index, vk in enumerate(VK_CODES):
            hotkey_id = index + 1
            if user32.RegisterHotKey(None, hotkey_id, MOD_ALT, vk):
                self.registered_hotkeys.append(hotkey_id)
            else:
                failed = True
        if failed:
            self.hotkey_queue.put(None)
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            if message.message == WM_HOTKEY:
                self.hotkey_queue.put(str(message.wParam if message.wParam < 10 else 0))
        for hotkey_id in self.registered_hotkeys:
            user32.UnregisterHotKey(None, hotkey_id)
        self.registered_hotkeys.clear()

    def unregister_hotkeys(self) -> None:
        thread_id = getattr(self, "hotkey_thread_id", None)
        if thread_id:
            ctypes.windll.user32.PostThreadMessageW(thread_id, win32con.WM_QUIT, 0, 0)

    def poll_hotkeys(self) -> None:
        try:
            foreground = self.foreground_window()
            if self.pending_save_key:
                now = time.monotonic()
                if now - self.pending_save_started >= SAVE_WAIT_SECONDS:
                    self.pending_save_key = None
                    self.save_candidate_hwnd = None
                    self.refresh_buttons()
                    self.status.set("저장 대기 시간이 끝났습니다. 저장 버튼을 다시 눌러주세요.")
                elif foreground is None:
                    # The slot manager is still active (or focus is transitioning).
                    self.save_candidate_hwnd = None
                elif foreground != self.save_candidate_hwnd:
                    # Start the half-second confirmation only after the user
                    # selects an external application window.
                    self.save_candidate_hwnd = foreground
                    self.save_candidate_started = now
                    self.status.set("프로그램을 선택했습니다. 0.5초 후 자동 저장합니다.")
                elif now - self.save_candidate_started >= SAVE_STABLE_SECONDS:
                    key = self.pending_save_key
                    self.save_selected_window(key, foreground)
            while True:
                try:
                    key = self.hotkey_queue.get_nowait()
                except queue.Empty:
                    break
                if key is None:
                    self.status.set("일부 단축키를 등록하지 못했습니다. 다른 프로그램의 단축키와 겹치는지 확인하세요.")
                else:
                    self.restore_slot(key)
        finally:
            self.root.after(80, self.poll_hotkeys)

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit(self) -> None:
        self.unregister_hotkeys()
        self.root.destroy()


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("이 프로그램은 Windows에서 실행해야 합니다.")
    try:
        # Own AppUserModelID so the taskbar shows this app's icon, not python.exe's.
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mainyh.WindowPosition")
    except Exception:
        pass
    root = tk.Tk()
    WindowPositionApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
