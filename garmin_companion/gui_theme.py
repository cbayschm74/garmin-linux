"""Read public Omarchy color tokens; otherwise follow the native Qt palette."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import re
from string import Template

try:
    import tomllib
except ImportError:  # Python 3.10 keeps native Qt styling.
    tomllib = None

from PyQt6.QtCore import QEvent, QFileSystemWatcher, QObject, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


def mix(first: str, second: str, weight: float) -> str:
    a, b = QColor(first), QColor(second)
    return QColor(*(round(x * (1 - weight) + y * weight)
                    for x, y in zip((a.red(), a.green(), a.blue()),
                                    (b.red(), b.green(), b.blue())))).name()


def luminance(color: str) -> float:
    def linear(v):
        v /= 255
        return v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4
    c = QColor(color)
    return sum(x * y for x, y in zip((.2126, .7152, .0722),
                                     map(linear, (c.red(), c.green(), c.blue()))))


def contrast(first: str, second: str) -> float:
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


def legible(background: str, preferred: str) -> str:
    if contrast(background, preferred) >= 4.5:
        return preferred
    return max(('#111111', '#ffffff'), key=lambda color: contrast(background, color))


@dataclass(frozen=True)
class Colors:
    background: str
    surface: str
    foreground: str
    accent: str
    accent_text: str
    alternate: str
    border: str
    muted: str
    hover: str
    hover_surface: str
    sidebar: str
    sidebar_text: str
    disabled_bg: str
    disabled_text: str
    success: str
    warning: str
    error: str

    def result_pair(self, kind: str) -> tuple[str, str]:
        ink = {'pass': self.success, 'fail': self.error, 'info': self.accent}[kind]
        background = mix(self.background, ink, .16)
        return legible(background, ink), background


def native_colors(palette: QPalette) -> Colors:
    role = QPalette.ColorRole
    bg = palette.color(role.Window).name()
    surface = palette.color(role.Base).name()
    fg = legible(bg, palette.color(role.WindowText).name())
    accent = palette.color(role.Highlight).name()
    return make_colors(bg, surface, fg, accent,
                       palette.color(role.AlternateBase).name(),
                       '#2e7d32', '#a15c00', '#c62828')


def make_colors(bg, surface, fg, accent, alternate, success, warning, error) -> Colors:
    fg = legible(bg, fg)
    if contrast(surface, fg) < 4.5:
        surface = mix(bg, fg, .035)
    if contrast(alternate, fg) < 4.5:
        alternate = mix(bg, fg, .07)
    return Colors(bg, surface, fg, accent, legible(accent, fg), alternate,
                  mix(fg, bg, .72), legible(bg, mix(fg, bg, .28)),
                  mix(accent, fg, .12), mix(surface, accent, .14),
                  bg, fg, mix(surface, bg, .55), mix(fg, bg, .45),
                  legible(bg, success), legible(bg, warning), legible(bg, error))


def load_colors(path: Path, native: QPalette) -> Colors | None:
    if tomllib is None:
        return None
    try:
        with path.open('rb') as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            return None
        data = tomllib.loads(raw.decode('utf-8'))
        defaults = native_colors(native)
        def color(key, fallback=None):
            value = data.get(key, fallback)
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3}', value):
                raise ValueError('Invalid theme color')
            return QColor(value).name()
        bg, fg = color('background'), color('foreground')
        surface = color('lighter_background', mix(bg, fg, .035))
        return make_colors(bg, surface, fg, color('accent', defaults.accent),
                           color('selection', mix(bg, fg, .07)),
                           color('green', defaults.success),
                           color('orange', color('yellow', defaults.warning)),
                           color('red', defaults.error))
    except (OSError, ValueError, UnicodeError):
        return None


def omarchy_theme_path() -> Path | None:
    """Use Omarchy only on an identified Omarchy session/host; no shell command."""
    try:
        installed = any(line.strip() in ('ID=omarchy', 'ID="omarchy"')
                        for line in Path('/etc/os-release').read_text().splitlines())
    except OSError:
        installed = False
    if not installed and not os.environ.get('OMARCHY_PATH'):
        return None
    state = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state')))
    config = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config')))
    current = state / 'omarchy/current/theme/colors.toml'
    legacy = config / 'omarchy/current/theme/colors.toml'
    return legacy if not current.exists() and legacy.is_file() else current


class ThemeController(QObject):
    changed = pyqtSignal(object)

    def __init__(self, window, *, path: Path | None = None):
        super().__init__(window)
        self.window = window
        self.path = path if path is not None else omarchy_theme_path()
        self.colors = native_colors(QApplication.palette())
        self.source = 'qt'
        self._applying = False
        self._stopped = False
        self._fingerprint = None
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._schedule)
        self._watcher.directoryChanged.connect(self._schedule)
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(100)
        self._debounce.timeout.connect(self.reload)
        # Stat-only fallback also catches directory/symlink replacements on
        # filesystems where Qt's directory notification is missed or coalesced.
        self._poll = QTimer(self)
        self._poll.setInterval(1000)
        self._poll.timeout.connect(self._check)
        if self.path is not None:
            self._poll.start()
        QApplication.instance().installEventFilter(self)

    def _schedule(self, *_):
        if not self._stopped:
            self._debounce.start()

    def _signature(self):
        if self.path is None:
            return None
        try:
            stat = self.path.stat()
            return stat.st_ino, stat.st_size, stat.st_mtime_ns
        except OSError:
            return ()

    def _check(self):
        if self._signature() != self._fingerprint:
            self._schedule()

    def _rewatch(self):
        old = self._watcher.files() + self._watcher.directories()
        if old:
            self._watcher.removePaths(old)
        if self.path is not None:
            candidates = [self.path, *list(self.path.parents)[:3]]
            existing = [str(p) for p in candidates if p.exists()]
            if existing:
                self._watcher.addPaths(existing)

    def eventFilter(self, obj, event):
        if not self._applying and event.type() == QEvent.Type.ApplicationPaletteChange:
            self._schedule()
        return False

    def reload(self):
        if self._applying or self._stopped:
            return
        self._applying = True
        try:
            native = QApplication.palette()
            loaded = load_colors(self.path, native) if self.path is not None else None
            self.colors = loaded or native_colors(native)
            self.source = 'omarchy' if loaded is not None else 'qt'
            self._fingerprint = self._signature()
            self._rewatch()
            # A zero resolve mask lets Qt propagate future desktop changes when
            # there is no Omarchy theme. Theme palettes stay scoped to this app window.
            palette = QPalette(native) if loaded is not None else QPalette()
            if loaded is not None:
                roles = QPalette.ColorRole
                for role, value in {
                    roles.Window: self.colors.background, roles.WindowText: self.colors.foreground,
                    roles.Base: self.colors.surface, roles.Text: self.colors.foreground,
                    roles.AlternateBase: self.colors.alternate, roles.Button: self.colors.alternate,
                    roles.ButtonText: self.colors.foreground, roles.Highlight: self.colors.accent,
                    roles.HighlightedText: self.colors.accent_text,
                    roles.ToolTipBase: self.colors.surface, roles.ToolTipText: self.colors.foreground,
                    roles.PlaceholderText: self.colors.muted, roles.Link: self.colors.accent,
                }.items():
                    palette.setColor(role, QColor(value))
            self.window.setPalette(palette)
            self.changed.emit(self.colors)
        finally:
            self._applying = False

    def stop(self):
        self._stopped = True
        self._watcher.blockSignals(True)
        watched = self._watcher.files() + self._watcher.directories()
        if watched:
            self._watcher.removePaths(watched)
        self._poll.stop()
        self._debounce.stop()
        QApplication.instance().removeEventFilter(self)


# Palette substitutions are deliberately centralized, including local editors
# and semantic feedback; no theme text is interpolated into Qt style syntax.
_CSS = """
            QMainWindow, QStackedWidget, QScrollArea, QScrollArea > QWidget > QWidget { background: $background; }
            QWidget { color: $foreground; font-size: 13px; }
            QPlainTextEdit { background: $surface; color: $foreground; border: 1px solid $border; }
            QListWidget { background: $surface; color: $foreground; }
            QDialog, QMessageBox { background: $background; }
            #courseTransferReview { background: $background; }
            #courseTransferReview QLabel { background: transparent; color: $foreground; }
            QComboBox { background: $surface; color: $foreground; border: 1px solid $border; padding: 6px; }
            QComboBox QAbstractItemView { background: $surface; color: $foreground;
                                         selection-background-color: $accent; selection-color: $accent_text; }
            #navigation { background: $sidebar; color: $sidebar_text; border: 0; padding: 24px 8px; }
            #navigation::item { padding: 13px 14px; border-radius: 7px; }
            #navigation::item:selected { background: $accent; color: $accent_text; }
            #pageTitle { font-size: 25px; font-weight: 700; }
            #pageIntro { color: $muted; }
            #deviceCard { background: $surface; border: 1px solid $border; border-radius: 9px; }
            #cardTitle { font-size: 17px; font-weight: 650; }
            #statusText { color: $success; }
            #warningText { color: $warning; }
            #emptyCard { background: $surface; border: 1px dashed $border; border-radius: 9px; }
            QPushButton { background: $accent; color: $accent_text; border: 0; border-radius: 6px;
                          padding: 9px 16px; font-weight: 600; }
            QPushButton:hover { background: $hover; }
            QPushButton:disabled { background: $disabled_bg; color: $disabled_text; }
            QTableWidget { background: $surface; alternate-background-color: $alternate; border: 1px solid $border; }
            QHeaderView::section { background: $alternate; color: $foreground; border: 0;
                                   border-bottom: 1px solid $border; padding: 8px; font-weight: 600; }
            #courseTabs::pane, #mapTabs::pane { background: $background; border: 1px solid $border; }
            #mapTabs QTabBar::tab, #courseTabs QTabBar::tab { background: $alternate; color: $foreground;
                                      border: 1px solid $border; padding: 10px 16px;
                                      margin-right: 4px; border-top-left-radius: 6px;
                                      border-top-right-radius: 6px; }
            #mapTabs QTabBar::tab:!selected:hover, #courseTabs QTabBar::tab:!selected:hover { background: $hover_surface; color: $foreground; }
            #mapTabs QTabBar::tab:selected, #courseTabs QTabBar::tab:selected { background: $accent; color: $accent_text;
                                               border-color: $accent; font-weight: 600; }
        
QLineEdit, QPlainTextEdit, QTextEdit, QTableWidget {
  color: $foreground; background: $surface;
  selection-background-color: $accent; selection-color: $accent_text;
}
QTableWidget::item:selected { color: $accent_text; background: $accent; }
QTableWidget QLineEdit {
  color: $foreground; background: $surface;
  selection-background-color: $accent; selection-color: $accent_text;
  border: 2px solid $accent; padding: 3px;
}
QProgressBar { background: $surface; color: $foreground; border: 1px solid $border; border-radius: 4px; }
QProgressBar::chunk { background: $accent; }
QToolTip { color: $foreground; background: $surface; border: 1px solid $border; }
"""

def stylesheet(colors: Colors) -> str:
    text = Template(_CSS).substitute(asdict(colors))
    for kind in ('pass', 'fail', 'info'):
        ink, bg = colors.result_pair(kind)
        text += (f'QLabel[garminResult="{kind}"] {{ color: {ink}; background: {bg}; '
                 'font-weight: 600; padding: 8px; border-radius: 5px; }\n')
    return text
