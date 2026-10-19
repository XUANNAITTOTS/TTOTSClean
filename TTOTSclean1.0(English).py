import sys
import os
import re
import fnmatch
import json
import shutil
import ctypes
import ctypes.wintypes as wintypes
import time
from datetime import datetime
from typing import List, Set, Dict

import psutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QFileDialog, QLabel, QPushButton,
    QMessageBox, QCheckBox, QScrollArea, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox, QProgressBar, QComboBox, QLineEdit
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QPalette, QColor

# ================= Base environment =================
BASE_DATA_DIR = r'C:\TTOTScleanData'
UNDO_LOG_PATH = os.path.join(BASE_DATA_DIR, 'undo_log.json')
os.makedirs(BASE_DATA_DIR, exist_ok=True)

SIZE_LIMIT = 5 * 1024 * 1024 * 1024  # 5GB threshold
SKIP_DIRS = frozenset({
    'system volume information', '$recycle.bin', 'recycle.bin', '$extend',
    'pagefile.sys', 'hiberfil.sys', 'swapfile.sys'
})

CATE_STYLE = {
    'System File':       {'color': 'green',   'tag': '[System File]'},
    'Third-party App':   {'color': 'red',     'tag': '[Third-party App]'},
    'Virus':             {'color': 'purple',  'tag': '[Virus]'},
    'Video File':        {'color': '#0055AA', 'tag': '[Video]'},
    'Audio File':        {'color': '#AA5500', 'tag': '[Audio]'},
    'Media Project':     {'color': '#008855', 'tag': '[Media Project]'},
    'Programming File':  {'color': '#555555', 'tag': '[Programming]'},
    'Web File':          {'color': '#0088AA', 'tag': '[Web]'},
    'Design Project':    {'color': '#8800AA', 'tag': '[Design Project]'},
    'Office Document':   {'color': '#333333', 'tag': '[Office Document]'},
    'Archive':           {'color': '#666666', 'tag': '[Archive]'},
    'Image File':        {'color': '#008888', 'tag': '[Image]'},
    'Other File':        {'color': 'gray',    'tag': '[Other]'},
}


# ================= Startup templates =================
def init_templates():
    db_path = os.path.join(BASE_DATA_DIR, 'database.txt')
    virus_path = os.path.join(BASE_DATA_DIR, 'virus_db.txt')

    SAFE_PATHS = [
        ('C:\\Windows.old', 'Old OS backup after upgrade, safe to delete'),
        ('C:\\Windows\\SoftwareDistribution\\Download', 'Windows update download cache'),
        ('C:\\Windows\\Temp', 'System temp folder'),
        ('C:\\Users\\*\\AppData\\Local\\Temp', 'User temp folder'),
        ('C:\\Users\\*\\Documents\\WeChat Files', 'WeChat received files / chat history'),
        ('C:\\Users\\*\\Documents\\Tencent Files', 'QQ received files / chat history'),
    ]

    EXT_RULES = [
        ('.dll', 'Third-party App'), ('.xml', 'Third-party App'), ('.json', 'Third-party App'),
        ('.ini', 'Third-party App'), ('.config', 'Third-party App'), ('.dat', 'Third-party App'),
        ('.bin', 'Third-party App'), ('.log', 'Third-party App'), ('.bak', 'Third-party App'),
        ('.tmp', 'Third-party App'), ('.exe', 'Third-party App'), ('.msi', 'Third-party App'),
        ('.ocx', 'Third-party App'), ('.inf', 'Third-party App'), ('.pdb', 'Third-party App'),
        ('.sys', 'Third-party App'), ('.hmcl', 'Third-party App'),
        ('.mp4', 'Video File'), ('.avi', 'Video File'), ('.mkv', 'Video File'),
        ('.flv', 'Video File'), ('.mov', 'Video File'), ('.wmv', 'Video File'),
        ('.rmvb', 'Video File'), ('.rm', 'Video File'), ('.ts', 'Video File'),
        ('.3gp', 'Video File'), ('.swf', 'Video File'), ('.mpeg', 'Video File'),
        ('.mpg', 'Video File'), ('.asf', 'Video File'), ('.webm', 'Video File'),
        ('.mp3', 'Audio File'), ('.wav', 'Audio File'), ('.flac', 'Audio File'),
        ('.ape', 'Audio File'), ('.m4a', 'Audio File'), ('.aac', 'Audio File'),
        ('.ogg', 'Audio File'), ('.wma', 'Audio File'),
        ('.m3u8', 'Media Project'), ('.m3u', 'Media Project'), ('.pls', 'Media Project'),
        ('.cue', 'Media Project'), ('.srt', 'Media Project'), ('.ass', 'Media Project'),
        ('.sub', 'Media Project'),
        ('.py', 'Programming File'), ('.cpp', 'Programming File'), ('.c', 'Programming File'),
        ('.h', 'Programming File'), ('.hpp', 'Programming File'), ('.cs', 'Programming File'),
        ('.java', 'Programming File'), ('.js', 'Programming File'), ('.css', 'Programming File'),
        ('.php', 'Programming File'), ('.sql', 'Programming File'), ('.sh', 'Programming File'),
        ('.bat', 'Programming File'), ('.ps1', 'Programming File'), ('.vb', 'Programming File'),
        ('.go', 'Programming File'), ('.rs', 'Programming File'), ('.swift', 'Programming File'),
        ('.html', 'Web File'), ('.htm', 'Web File'), ('.mht', 'Web File'),
        ('.shtml', 'Web File'),
        ('.mlt', 'Design Project'), ('.psd', 'Design Project'), ('.ai', 'Design Project'),
        ('.cdr', 'Design Project'), ('.dxf', 'Design Project'), ('.dwg', 'Design Project'),
        ('.prproj', 'Design Project'), ('.aep', 'Design Project'),
        ('.doc', 'Office Document'), ('.docx', 'Office Document'), ('.xls', 'Office Document'),
        ('.xlsx', 'Office Document'), ('.ppt', 'Office Document'), ('.pptx', 'Office Document'),
        ('.pdf', 'Office Document'), ('.txt', 'Office Document'), ('.md', 'Office Document'),
        ('.rtf', 'Office Document'), ('.wps', 'Office Document'), ('.odt', 'Office Document'),
        ('.et', 'Office Document'), ('.ofd', 'Office Document'),
        ('.zip', 'Archive'), ('.rar', 'Archive'), ('.7z', 'Archive'), ('.tar', 'Archive'),
        ('.gz', 'Archive'), ('.bz2', 'Archive'), ('.xz', 'Archive'),
        ('.jpg', 'Image File'), ('.jpeg', 'Image File'), ('.png', 'Image File'),
        ('.bmp', 'Image File'), ('.gif', 'Image File'), ('.ico', 'Image File'),
        ('.svg', 'Image File'), ('.webp', 'Image File'), ('.tiff', 'Image File'),
        ('.tif', 'Image File'),
    ]

    if not os.path.exists(db_path):
        with open(db_path, 'w', encoding='utf-8') as f:
            f.write('# Known safe large-file / system folder paths (one per line)\n')
            f.write('# format: path - description\n')
            for p, d in SAFE_PATHS:
                f.write(f'{p} - {d}\n')
            f.write('\n# --- extension type rules (highest priority) ---\n')
            f.write('# format: .ext - type\n')
            for ext, cat in EXT_RULES:
                f.write(f'{ext} - {cat}\n')

    if not os.path.exists(virus_path):
        with open(virus_path, 'w', encoding='utf-8') as f:
            f.write('# virus / trojan / adware patterns (one wildcard per line)\n')
            f.write('# supports * and ? , e.g. *.ransom\n')
            f.write('*.ransom - ransomware suffix\n')
            f.write('*.locked - ransomware suffix\n')
            f.write('*coinminer* - cryptominer keyword\n')
            f.write('*activator*.exe - trojan disguised as activator\n')


# ================= Windows low-level walk =================
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF

if sys.platform == 'win32':
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
else:
    kernel32 = None


def long_path(path: str) -> str:
    if not path or path.startswith('\\\\?\\'):
        return path
    raw = os.path.abspath(path)
    if raw.startswith('\\\\') or raw.startswith('//'):
        return '\\\\?\\UNC\\' + raw[2:].lstrip('\\/')
    return '\\\\?\\' + raw


def strip_long_prefix(path: str) -> str:
    if path.startswith('\\\\?\\UNC\\'):
        return '\\\\' + path[8:]
    if path.startswith('\\\\?\\'):
        return path[4:]
    return path


def get_file_attrs(path: str) -> int:
    if kernel32 is None:
        return 0
    attrs = kernel32.GetFileAttributesW(path)
    return attrs if attrs is not None else INVALID_FILE_ATTRIBUTES


def is_reparse(attrs: int) -> bool:
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


# ================= Rule engine =================
class RuleEngine:
    def __init__(self):
        self.known_files: Set[str] = set()
        self.known_dirs: Set[str] = set()
        self.ext_categories: Dict[str, str] = {}
        self.virus_patterns = []
        self._load_db()
        self._load_virus()

    def _parse_line(self, line: str) -> str:
        line = line.strip()
        if not line or line.startswith('#'):
            return ''
        if ' - ' in line:
            return line.split(' - ', 1)[0].strip()
        return line

    def _load_db(self):
        db_path = os.path.join(BASE_DATA_DIR, 'database.txt')
        if not os.path.isfile(db_path):
            return
        with open(db_path, 'r', encoding='utf-8', errors='ignore') as f:
            in_ext = False
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s.startswith('#'):
                    if 'extension' in s.lower():
                        in_ext = True
                    continue
                if ' - ' in s:
                    raw = s.split(' - ')[0].strip().lower()
                    cat = s.split(' - ', 1)[1].strip()
                    if raw.startswith('.') and in_ext:
                        self.ext_categories[raw] = cat
                        continue
                if not in_ext and ('\\' in s or '/' in s or ':' in s):
                    raw = self._parse_line(line)
                    if raw.endswith(('\\', '/')):
                        self.known_dirs.add(os.path.normcase(os.path.normpath(raw)))
                    elif os.path.splitext(raw)[1]:
                        self.known_files.add(os.path.normcase(os.path.normpath(raw)))
                    else:
                        self.known_dirs.add(os.path.normcase(os.path.normpath(raw)))

    def _load_virus(self):
        v_path = os.path.join(BASE_DATA_DIR, 'virus_db.txt')
        if not os.path.isfile(v_path):
            return
        with open(v_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                raw = self._parse_line(line)
                if not raw:
                    continue
                try:
                    self.virus_patterns.append(re.compile(fnmatch.translate(raw), re.IGNORECASE))
                except re.error:
                    pass

    def categorize(self, fullpath: str, filename: str) -> str:
        np_ = os.path.normcase(os.path.normpath(fullpath))
        for pat in self.virus_patterns:
            if pat.search(np_) or pat.search(filename):
                return 'Virus'
        ext = os.path.splitext(np_)[1].lower()
        if ext in self.ext_categories:
            return self.ext_categories[ext]
        if np_ in self.known_files:
            return 'System File'
        p = np_
        while True:
            if p in self.known_dirs:
                return 'System File'
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
        return 'Third-party App'


# ================= Logging =================
def _today_log_path() -> str:
    return os.path.join(BASE_DATA_DIR, f'{datetime.now():%Y%m%d}.txt')


def _count_entries(log_path: str) -> int:
    if not os.path.isfile(log_path):
        return 0
    c = 0
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if re.match(r'^\d{4}-\d{2}-\d{2}-\d+', line.strip()):
                c += 1
    return c


def write_scan_log(content: str, enable_log=True):
    if not enable_log:
        return
    p = _today_log_path()
    n = _count_entries(p) + 1
    now = datetime.now()
    header = f'{now:%Y-%m-%d}-{n} (run #{n}) -{now:%H:%M:%S}'
    with open(p, 'a', encoding='utf-8') as f:
        f.write(f'{header}\n{content}\n{"-" * 56}\n')


def write_clean_log(targets_all, cleaned, skipped, total_time_sec, enable_log=True):
    if not enable_log:
        return
    p = _today_log_path()
    n = _count_entries(p) + 1
    now = datetime.now()
    h = int(total_time_sec // 3600)
    m = int((total_time_sec % 3600) // 60)
    s = int(total_time_sec % 60)
    header = f'{now:%Y-%m-%d}-{n} (run #{n}) -{now:%H:%M:%S}-total {h:02d}:{m:02d}:{s:02d}'
    with open(p, 'a', encoding='utf-8') as f:
        f.write(f'{header}\n\nto clean:\n')
        for i, (_, path, size, cat) in enumerate(targets_all, 1):
            f.write(f'{i}. {path}  ({size / 1024**3:.2f} GB)\n')
        if not targets_all:
            f.write('(none)\n')
        f.write('\ncleaned:\n')
        for i, (path, el) in enumerate(cleaned, 1):
            f.write(f'{i}. {path}    took {el}\n')
        if not cleaned:
            f.write('(none)\n')
        f.write('\nskipped:\n')
        for i, (path, why) in enumerate(skipped, 1):
            f.write(f'{i}. {path}    ({why})\n')
        if not skipped:
            f.write('(none)\n')
        f.write(f'\n{"-" * 56}\n')


def save_undo_log(entry: dict, enable_save_record=True):
    if not enable_save_record:
        return
    log = []
    if os.path.isfile(UNDO_LOG_PATH):
        try:
            with open(UNDO_LOG_PATH, 'r', encoding='utf-8') as f:
                log = json.load(f)
        except Exception:
            log = []
    log.append(entry)
    with open(UNDO_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ================= Main window =================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('TTOTSclean 1.0')
        self.resize(800, 500)
        self._build_ui()
        self._apply_system_theme()

    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(20, 20, 20, 10)
        main_layout.setSpacing(15)

        top_layout = QHBoxLayout()
        row_disk = QHBoxLayout()
        row_disk.addWidget(QLabel('Disk to clean:'))
        self.combo_disk = QComboBox()
        self.combo_disk.setMinimumWidth(200)
        self.combo_disk.addItem('C:\\')
        row_disk.addWidget(self.combo_disk)
        row_disk.addStretch()
        top_layout.addLayout(row_disk, 1)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel('Theme:'))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(['Light', 'Dark', 'Follow System'])
        self.combo_theme.setCurrentText('Follow System')
        self.combo_theme.currentTextChanged.connect(self.on_theme_changed)
        row_theme.addWidget(self.combo_theme)
        top_layout.addLayout(row_theme, 1)
        main_layout.addLayout(top_layout)

        left_opts = QVBoxLayout()
        self.chk_admin = QCheckBox('Run with administrator privileges')
        self.chk_admin.setToolTip('Will detect more hidden system files')
        left_opts.addWidget(self.chk_admin)
        self.chk_enable_log = QCheckBox('Enable logging after start')
        left_opts.addWidget(self.chk_enable_log)
        self.chk_save_record = QCheckBox('Save clean records')
        left_opts.addWidget(self.chk_save_record)

        right_dirs = QVBoxLayout()
        row_log_dir = QHBoxLayout()
        row_log_dir.addWidget(QLabel('Log directory:'))
        self.edit_log_dir = QLineEdit(BASE_DATA_DIR)
        btn_log_dir = QPushButton('Browse')
        btn_log_dir.clicked.connect(lambda: self.browse_dir(self.edit_log_dir))
        row_log_dir.addWidget(self.edit_log_dir)
        row_log_dir.addWidget(btn_log_dir)
        right_dirs.addLayout(row_log_dir)

        row_rec_dir = QHBoxLayout()
        row_rec_dir.addWidget(QLabel('Record directory:'))
        self.edit_record_dir = QLineEdit(BASE_DATA_DIR)
        btn_rec_dir = QPushButton('Browse')
        btn_rec_dir.clicked.connect(lambda: self.browse_dir(self.edit_record_dir))
        row_rec_dir.addWidget(self.edit_record_dir)
        row_rec_dir.addWidget(btn_rec_dir)
        right_dirs.addLayout(row_rec_dir)

        cfg_dir = QHBoxLayout()
        cfg_dir.addLayout(left_opts, 1)
        cfg_dir.addLayout(right_dirs, 2)
        main_layout.addLayout(cfg_dir)

        btn_area = QHBoxLayout()
        btn_area.addStretch()
        self.btn_start = QPushButton('Start')
        self.btn_start.setMinimumWidth(100)
        self.btn_cancel = QPushButton('Cancel')
        self.btn_cancel.setMinimumWidth(100)
        self.btn_start.setStyleSheet('font-weight: bold; padding: 5px 15px;')
        self.btn_cancel.setStyleSheet('font-weight: bold; padding: 5px 15px;')
        btn_area.addWidget(self.btn_start)
        btn_area.addWidget(self.btn_cancel)
        main_layout.addLayout(btn_area)

        self.load_disks()
        self.btn_start.clicked.connect(self.on_start_clicked)
        self.btn_cancel.clicked.connect(self.close)

    def load_disks(self):
        try:
            for p in psutil.disk_partitions(all=True):
                if p.mountpoint:
                    self.combo_disk.addItem(p.mountpoint)
        except Exception:
            pass

    def browse_dir(self, le):
        d = QFileDialog.getExistingDirectory(self, 'Select Directory', le.text())
        if d:
            le.setText(d)

    def _apply_theme(self, theme_type):
        palette = self.palette()
        if theme_type == 'Light':
            pairs = [
                (QPalette.Window, QColor(240, 240, 240)),
                (QPalette.WindowText, QColor(0, 0, 0)),
                (QPalette.Base, QColor(255, 255, 255)),
                (QPalette.AlternateBase, QColor(230, 230, 230)),
                (QPalette.ToolTipBase, QColor(255, 255, 255)),
                (QPalette.ToolTipText, QColor(0, 0, 0)),
                (QPalette.Text, QColor(0, 0, 0)),
                (QPalette.Button, QColor(240, 240, 240)),
                (QPalette.ButtonText, QColor(0, 0, 0)),
                (QPalette.BrightText, QColor(255, 0, 0)),
                (QPalette.Highlight, QColor(42, 130, 218)),
                (QPalette.HighlightedText, QColor(255, 255, 255)),
            ]
        else:
            pairs = [
                (QPalette.Window, QColor(30, 30, 30)),
                (QPalette.WindowText, QColor(240, 240, 240)),
                (QPalette.Base, QColor(25, 25, 25)),
                (QPalette.AlternateBase, QColor(35, 35, 35)),
                (QPalette.ToolTipBase, QColor(255, 255, 255)),
                (QPalette.ToolTipText, QColor(255, 255, 255)),
                (QPalette.Text, QColor(240, 240, 240)),
                (QPalette.Button, QColor(45, 45, 45)),
                (QPalette.ButtonText, QColor(240, 240, 240)),
                (QPalette.BrightText, QColor(255, 0, 0)),
                (QPalette.Highlight, QColor(42, 130, 218)),
                (QPalette.HighlightedText, QColor(255, 255, 255)),
            ]
        for role, col in pairs:
            palette.setColor(role, col)
        QApplication.setPalette(palette)
        for widget in QApplication.allWidgets():
            widget.update()
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _apply_system_theme(self):
        try:
            import winreg
            key = r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                val, _ = winreg.QueryValueEx(k, 'AppsUseLightTheme')
                choice = 'Light' if val == 1 else 'Dark'
            self._apply_theme(choice)
            self.combo_theme.setCurrentText(choice)
            return
        except Exception:
            pass
        self._apply_theme('Light')
        self.combo_theme.setCurrentText('Light')

    def on_theme_changed(self, text):
        if text == 'Follow System':
            self._apply_system_theme()
        else:
            self._apply_theme(text)

    def on_start_clicked(self):
        disk = self.combo_disk.currentText().strip()
        if not disk:
            QMessageBox.warning(self, 'Notice', 'Please select a disk/path to scan.')
            return
        enable_admin = self.chk_admin.isChecked()
        enable_log = self.chk_enable_log.isChecked()
        enable_rec = self.chk_save_record.isChecked()
        if enable_admin:
            write_scan_log('User requested admin privilege for scan', enable_log)
        write_scan_log(f'Start scan on {disk}', enable_log)

        self.hide()
        self.scan_window = ScanWindow(self, disk, enable_log=enable_log, enable_save_record=enable_rec)
        self.scan_window.start_scan()
        self.scan_window.exec()
        self.show()


# ================= Scan worker =================
class ScanWorker(QThread):
    progress_signal = Signal(str)
    path_signal = Signal(str)
    item_signal = Signal(list)
    result_signal = Signal(dict, int)
    error_signal = Signal(str)

    def __init__(self, disk: str):
        super().__init__()
        d = os.path.normpath(disk).rstrip('\\/')
        if len(d) == 2 and d[1] == ':':
            d += os.sep
        self.disk = d
        self._stop = False
        self._stopped_by_user = False

    def stop(self):
        self._stop = True
        self._stopped_by_user = True

    def run(self):
        try:
            self._run_inner()
        except Exception as exc:
            self.error_signal.emit(f'Scan error: {exc}')

    def _run_inner(self):
        self.progress_signal.emit('Loading rule database ...')
        engine = RuleEngine()
        self.progress_signal.emit(f'Opening {self.disk} ...')

        dir_own_size = {}
        large_files = []
        dirs_seen = bytes_seen = perm_errs = 0
        pending = []
        MAX_ITEMS, FLUSH_EVERY = 2000, 30

        def flush():
            nonlocal pending
            if pending:
                self.item_signal.emit(pending)
                pending = []

        stack = [long_path(self.disk)]
        while stack and not self._stop:
            dir_long = stack.pop()
            dirs_seen += 1
            self.path_signal.emit(strip_long_prefix(dir_long))
            try:
                entries = list(os.scandir(dir_long))
            except OSError:
                perm_errs += 1
                continue
            total = 0
            subdirs = []
            for e in entries:
                if self._stop:
                    break
                if e.name.lower() in SKIP_DIRS:
                    continue
                attrs = get_file_attrs(e.path)
                if attrs == INVALID_FILE_ATTRIBUTES:
                    continue
                if attrs & FILE_ATTRIBUTE_DIRECTORY:
                    if is_reparse(attrs):
                        continue
                    subdirs.append(e.path)
                else:
                    try:
                        sz = e.stat(follow_symlinks=False).st_size
                    except OSError:
                        perm_errs += 1
                        continue
                    total += sz
                    bytes_seen += sz
                    if sz > SIZE_LIMIT and len(large_files) < MAX_ITEMS:
                        clean = strip_long_prefix(e.path)
                        cat = engine.categorize(clean, e.name)
                        large_files.append((clean, sz, cat))
                        pending.append(('file', clean, sz, cat))
                        if len(pending) >= FLUSH_EVERY:
                            flush()
            dir_own_size[os.path.normcase(strip_long_prefix(dir_long))] = total
            stack.extend(subdirs)
            if dirs_seen % 200 == 0:
                self.progress_signal.emit(
                    f'Scanning... {dirs_seen} dirs, ~{bytes_seen / 1024 ** 3:.2f} GB processed')

        flush()

        if self._stopped_by_user:
            self.progress_signal.emit('Scan terminated.')
            self.result_signal.emit({'large_files': large_files, 'large_folders': []}, perm_errs)
            return

        folder_size = dict(dir_own_size)
        for p in sorted(dir_own_size.keys(), key=lambda s: s.count(os.sep), reverse=True):
            parent = os.path.normcase(os.path.dirname(p))
            if parent != p:
                folder_size[parent] = folder_size.get(parent, 0) + dir_own_size[p]

        large_folders = [
            (p, s, engine.categorize(p, os.path.basename(p)))
            for p, s in folder_size.items() if s > SIZE_LIMIT
        ][:MAX_ITEMS]

        large_files.sort(key=lambda x: x[1], reverse=True)
        large_folders.sort(key=lambda x: x[1], reverse=True)
        if large_folders:
            self.item_signal.emit([('folder', p, s, c) for p, s, c in large_folders])

        self.progress_signal.emit('Scan complete! Select items to clean.')
        self.result_signal.emit({'large_files': large_files, 'large_folders': large_folders}, perm_errs)


# ================= Scan dialog (green native progress bar) =================
class ScanWindow(QDialog):
    def __init__(self, parent, disk, enable_log=True, enable_save_record=True):
        super().__init__(parent)
        self.setWindowTitle('Scanning Disk Files')
        self.resize(720, 560)
        self.setMinimumSize(640, 480)
        self.disk = disk
        self.enable_log = enable_log
        self.enable_save_record = enable_save_record
        self._scanning = False
        self._all_items = []
        self._file_row_count = 0
        self._folder_row_count = 0
        self._checked_count = 0
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            'QProgressBar { border: 1px solid #b8b8b8; border-radius: 2px; background-color: #e8e8e8; }'
            'QProgressBar::chunk { background-color: #2ecc71; }')
        layout.addWidget(self.progress_bar)

        self.lbl_path = QLabel('Preparing...', self)
        self.lbl_path.setStyleSheet('color: #555; font-size: 12px; padding: 4px 0;')
        layout.addWidget(self.lbl_path)

        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(8, 4, 8, 4)
        self.scroll_layout.setSpacing(12)
        self.gb_files = QGroupBox('Single files over 5GB:', self)
        self.gb_files_layout = QVBoxLayout(self.gb_files)
        self.gb_files_layout.setContentsMargins(8, 12, 8, 8)
        self.gb_folders = QGroupBox('Folders over 5GB:', self)
        self.gb_folders_layout = QVBoxLayout(self.gb_folders)
        self.gb_folders_layout.setContentsMargins(8, 12, 8, 8)
        self.scroll_layout.addWidget(self.gb_files)
        self.scroll_layout.addWidget(self.gb_folders)
        self.scroll_layout.addStretch()
        self.scroll.setWidget(scroll_content)
        layout.addWidget(self.scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_cancel_scan = QPushButton('Cancel', self)
        self.btn_cancel_scan.setStyleSheet('color: gray; font-size: 13px;')
        self.btn_cancel_scan.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel_scan)
        self.btn_stop = QPushButton('Stop Task', self)
        self.btn_stop.setStyleSheet('color: red; font-weight: bold; font-size: 14px;')
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        btn_layout.addWidget(self.btn_stop)
        self.btn_clean = QPushButton('Clean (0)', self)
        self.btn_clean.setEnabled(False)
        self.btn_clean.setStyleSheet('font-weight: bold; font-size: 14px;')
        self.btn_clean.clicked.connect(self._on_preview_clean)
        btn_layout.addWidget(self.btn_clean)
        layout.addLayout(btn_layout)

    def start_scan(self):
        self._scanning = True
        self.progress_bar.setRange(0, 0)
        self.lbl_path.setText(f'Opening: {self.disk}')
        self.btn_stop.setEnabled(True)
        self.btn_stop.setText('Stop Task')
        self.btn_clean.setEnabled(False)
        self.btn_clean.setText('Clean (0)')
        self.worker = ScanWorker(self.disk)
        self.worker.progress_signal.connect(self.lbl_path.setText)
        self.worker.path_signal.connect(lambda p: self.lbl_path.setText(f'Current: {p}'))
        self.worker.item_signal.connect(self._on_scan_item)
        self.worker.result_signal.connect(self._on_scan_finished)
        self.worker.error_signal.connect(self._on_scan_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_worker_finished(self):
        self._scanning = False
        self.btn_stop.setEnabled(False)
        self.btn_clean.setEnabled(self._checked_count > 0)

    def _on_stop_clicked(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText('Stopping...')
            self.worker.stop()
            self.lbl_path.setText('Terminating scan...')

    def _on_scan_error(self, message):
        self._scanning = False
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.lbl_path.setText(message)
        self.btn_stop.setEnabled(False)
        self.btn_clean.setEnabled(False)
        QMessageBox.critical(self, 'Scan Error', message)

    def _on_scan_item(self, rows):
        for kind, path, size, cat in rows:
            self._all_items.append((kind, path, size, cat))
            style = CATE_STYLE.get(cat, CATE_STYLE['Other File'])
            cb = QCheckBox()
            cb.setText(f'{style["tag"]}  ({path})')
            cb.setStyleSheet(f'color: {style["color"]}; font-size: 12px;')
            cb.toggled.connect(self._on_checkbox_toggled)
            if kind == 'file':
                self._file_row_count += 1
                cb.setText(f'{self._file_row_count}.  {cb.text()}')
                self.gb_files_layout.addWidget(cb)
            else:
                self._folder_row_count += 1
                cb.setText(f'{self._folder_row_count}.  {cb.text()}')
                self.gb_folders_layout.addWidget(cb)

    def _on_checkbox_toggled(self, checked):
        self._checked_count += 1 if checked else -1
        self._checked_count = max(0, self._checked_count)
        self.btn_clean.setText(f'Clean ({self._checked_count})')
        self.btn_clean.setEnabled(not self._scanning and self._checked_count > 0)

    def _on_scan_finished(self, results, perm_errs):
        self._scanning = False
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        total = len(results['large_files']) + len(results['large_folders'])
        tip = f'Found {total} large files/folders'
        if perm_errs > 0:
            tip += f', {perm_errs} skipped by permission'
        self.lbl_path.setText(f'Scan complete! {tip}. Select items to clean.')
        self.btn_clean.setEnabled(self._checked_count > 0)
        self.btn_clean.setText(f'Clean ({self._checked_count})')

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        super().closeEvent(event)

    def _collect_selected(self):
        out = []
        for kind, path, size, cat in self._all_items:
            layout = self.gb_files_layout if kind == 'file' else self.gb_folders_layout
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and isinstance(item.widget(), QCheckBox):
                    cb = item.widget()
                    if f'({path})' in cb.text() and cb.isChecked():
                        out.append((kind, path, size, cat))
                        break
        return out

    def _on_preview_clean(self):
        targets = self._collect_selected()
        if not targets:
            QMessageBox.warning(self, 'Notice', 'Please select items to clean first.')
            return
        total_size = sum(t[2] for t in targets)
        detail = '\n'.join(f'[{t[3]}] {t[2] / 1024**3:.2f} GB | {t[1]}' for t in targets[:30])
        if len(targets) > 30:
            detail += f'\n... {len(targets)} items in total'
        msg = QMessageBox(self)
        msg.setWindowTitle('Clean Confirmation')
        msg.setText(f'{len(targets)} items, total {total_size / 1024**3:.2f} GB\nContinue?')
        msg.setInformativeText(detail)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        if msg.exec() == QMessageBox.Yes:
            self._do_clean(targets)

    def _do_clean(self, targets):
        send2trash = None
        try:
            from send2trash import send2trash
        except Exception:
            pass
        cleaned, skipped_list, undo_entries = [], [], []
        removed = set()
        start_time = time.time()
        for kind, path, size, cat in sorted(targets, key=lambda x: len(x[1]), reverse=True):
            n = os.path.normcase(path)
            if any(n == r or n.startswith(r + os.sep) for r in removed):
                skipped_list.append((path, 'covered by parent deletion'))
                continue
            t0 = time.time()
            try:
                if send2trash:
                    send2trash(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                undo_entries.append({'action': 'delete', 'path': path})
                cleaned.append((path, self._fmt(time.time() - t0)))
                removed.add(n)
            except Exception as e:
                skipped_list.append((path, str(e)))
        total_time = time.time() - start_time
        save_undo_log({'time': datetime.now().isoformat(), 'count': len(undo_entries), 'entries': undo_entries},
                      self.enable_save_record)
        write_clean_log(targets, cleaned, skipped_list, total_time, self.enable_log)
        txt = (f'Done: cleaned {len(cleaned)}, skipped {len(skipped_list)}\n'
               f'total {int(total_time // 3600):02d}:{int((total_time % 3600) // 60):02d}:{int(total_time % 60):02d}')
        QMessageBox.information(self, 'Clean Result', txt)
        self.accept()

    def _fmt(self, sec):
        return f'{int(sec // 3600):02d}:{int((sec % 3600) // 60):02d}:{int(sec % 60):02d}'


# ================= Entry =================
if __name__ == '__main__':
    def excepthook(t, v, tb):
        import traceback
        traceback.print_exception(t, v, tb)
        try:
            input('Program error, press Enter to exit...')
        except Exception:
            pass
    sys.excepthook = excepthook

    init_templates()
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
