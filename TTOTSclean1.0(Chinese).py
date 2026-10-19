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
from typing import List, Tuple, Set, Dict

import psutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QFileDialog, QLabel, QPushButton,
    QMessageBox, QCheckBox, QScrollArea, QWidget,
    QVBoxLayout, QHBoxLayout, QGroupBox, QProgressBar, QComboBox, QLineEdit
)
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtGui import QCloseEvent, QPalette, QColor

# ================= 基础环境 =================
BASE_DATA_DIR = r'C:\TTOTScleanData'
UNDO_LOG_PATH = os.path.join(BASE_DATA_DIR, 'undo_log.json')
os.makedirs(BASE_DATA_DIR, exist_ok=True)

SIZE_LIMIT = 5 * 1024 * 1024 * 1024  # 5GB 阈值
SKIP_DIRS = frozenset({
    'system volume information', '$recycle.bin', 'recycle.bin', '$extend',
    'pagefile.sys', 'hiberfil.sys', 'swapfile.sys'
})

# 分类颜色映射
CATE_STYLE = {
    '系统文件':           {'color': 'green',  'tag': '[系统文件]'},
    '第三方应用文件':     {'color': 'red',    'tag': '[第三方应用文件]'},
    '病毒文件':           {'color': 'purple', 'tag': '[病毒文件]'},
    '视频文件':           {'color': '#0055AA', 'tag': '[视频文件]'},
    '音频文件':           {'color': '#AA5500', 'tag': '[音频文件]'},
    '音视频项目文件':     {'color': '#008855', 'tag': '[音视频项目文件]'},
    '编程文件':           {'color': '#555555', 'tag': '[编程文件]'},
    '网页文件':           {'color': '#0088AA', 'tag': '[网页文件]'},
    '设计项目文件':       {'color': '#8800AA', 'tag': '[设计项目文件]'},
    '办公文档文件':       {'color': '#333333', 'tag': '[办公文档文件]'},
    '压缩文件':           {'color': '#666666', 'tag': '[压缩文件]'},
    '图片文件':           {'color': '#008888', 'tag': '[图片文件]'},
    '其他文件':           {'color': 'gray',   'tag': '[其他文件]'}
}


# ================= 启动自动创建模板 =================
def init_templates():
    """程序启动时自动创建数据库和病毒库模板"""
    db_path = os.path.join(BASE_DATA_DIR, '数据库.txt')
    virus_path = os.path.join(BASE_DATA_DIR, '病毒库.txt')

    # 基础安全路径与扩展名映射表
    SAFE_PATHS = [
        ('C:\\Windows.old', '升级系统留下的旧系统备份，可安全删除'),
        ('C:\\Windows\\SoftwareDistribution\\Download', 'Windows更新下载缓存'),
        ('C:\\Windows\\Temp', '系统临时文件夹'),
        ('C:\\Users\\*\\AppData\\Local\\Temp', '用户临时文件夹'),
        ('C:\\Users\\*\\Documents\\WeChat Files', '微信默认接收文件与聊天记录'),
        ('C:\\Users\\*\\Documents\\Tencent Files', 'QQ默认接收文件与聊天记录'),
    ]

    EXT_RULES = [
        # --- 第三方应用及游戏启动器 (含 .hmcl) ---
        ('.dll', '第三方应用文件'), ('.xml', '第三方应用文件'), ('.json', '第三方应用文件'),
        ('.ini', '第三方应用文件'), ('.config', '第三方应用文件'), ('.sys', '第三方应用文件'),
        ('.dat', '第三方应用文件'), ('.bin', '第三方应用文件'), ('.log', '第三方应用文件'),
        ('.bak', '第三方应用文件'), ('.tmp', '第三方应用文件'), ('.exe', '第三方应用文件'),
        ('.msi', '第三方应用文件'), ('.ocx', '第三方应用文件'), ('.inf', '第三方应用文件'),
        ('.pdb', '第三方应用文件'), ('.hmcl', '第三方应用文件'), # Minecraft HMCL 启动器
        # --- 视频 ---
        ('.mp4', '视频文件'), ('.avi', '视频文件'), ('.mkv', '视频文件'), ('.flv', '视频文件'),
        ('.mov', '视频文件'), ('.wmv', '视频文件'), ('.rmvb', '视频文件'), ('.rm', '视频文件'),
        ('.ts', '视频文件'), ('.3gp', '视频文件'), ('.swf', '视频文件'), ('.mpeg', '视频文件'),
        ('.mpg', '视频文件'), ('.asf', '视频文件'), ('.webm', '视频文件'),
        # --- 音频 ---
        ('.mp3', '音频文件'), ('.wav', '音频文件'), ('.flac', '音频文件'), ('.ape', '音频文件'),
        ('.m4a', '音频文件'), ('.aac', '音频文件'), ('.ogg', '音频文件'), ('.wma', '音频文件'),
        # --- 音视频项目 ---
        ('.m3u8', '音视频项目文件'), ('.m3u', '音视频项目文件'), ('.pls', '音视频项目文件'),
        ('.cue', '音视频项目文件'), ('.srt', '音视频项目文件'), ('.ass', '音视频项目文件'),
        ('.sub', '音视频项目文件'),
        # --- 编程 ---
        ('.py', '编程文件'), ('.cpp', '编程文件'), ('.c', '编程文件'), ('.h', '编程文件'),
        ('.hpp', '编程文件'), ('.cs', '编程文件'), ('.java', '编程文件'), ('.js', '编程文件'),
        ('.html', '编程文件'), ('.css', '编程文件'), ('.php', '编程文件'), ('.sql', '编程文件'),
        ('.sh', '编程文件'), ('.bat', '编程文件'), ('.ps1', '编程文件'), ('.vb', '编程文件'),
        ('.go', '编程文件'), ('.rs', '编程文件'), ('.swift', '编程文件'),
        # --- 网页 ---
        ('.htm', '网页文件'), ('.mht', '网页文件'), ('.shtml', '网页文件'),
        # --- 设计项目 ---
        ('.mlt', '设计项目文件'), ('.psd', '设计项目文件'), ('.ai', '设计项目文件'),
        ('.cdr', '设计项目文件'), ('.dxf', '设计项目文件'), ('.dwg', '设计项目文件'),
        ('.prproj', '设计项目文件'), ('.aep', '设计项目文件'),
        # --- 办公文档 ---
        ('.doc', '办公文档文件'), ('.docx', '办公文档文件'), ('.xls', '办公文档文件'),
        ('.xlsx', '办公文档文件'), ('.ppt', '办公文档文件'), ('.pptx', '办公文档文件'),
        ('.pdf', '办公文档文件'), ('.txt', '办公文档文件'), ('.md', '办公文档文件'),
        ('.rtf', '办公文档文件'), ('.wps', '办公文档文件'), ('.odt', '办公文档文件'),
        ('.et', '办公文档文件'), ('.ofd', '办公文档文件'),
        # --- 压缩 ---
        ('.zip', '压缩文件'), ('.rar', '压缩文件'), ('.7z', '压缩文件'), ('.tar', '压缩文件'),
        ('.gz', '压缩文件'), ('.bz2', '压缩文件'), ('.xz', '压缩文件'),
        # --- 图片 ---
        ('.jpg', '图片文件'), ('.jpeg', '图片文件'), ('.png', '图片文件'), ('.bmp', '图片文件'),
        ('.gif', '图片文件'), ('.ico', '图片文件'), ('.svg', '图片文件'), ('.webp', '图片文件'),
        ('.tiff', '图片文件'), ('.tif', '图片文件')
    ]

    if not os.path.exists(db_path):
        with open(db_path, 'w', encoding='utf-8') as f:
            f.write('# 已知的安全大文件/系统文件夹路径（一行一个）\n')
            f.write('# 格式：路径 - 说明文字\n')
            for p, d in SAFE_PATHS:
                f.write(f'{p} - {d}\n')
            
            f.write('\n# --- 以下为扩展名文件类型分类规则 (优先级最高) ---\n')
            f.write('# 格式：.扩展名 - 类型\n')
            for ext, cat in EXT_RULES:
                f.write(f'{ext} - {cat}\n')

    if not os.path.exists(virus_path):
        with open(virus_path, 'w', encoding='utf-8') as f:
            f.write('# 病毒/木马/广告软件特征（一行一个通配符）\n')
            f.write('# 支持 * 和 ? 通配符，例如 *.ransom\n')
            f.write('*.ransom - 常见勒索病毒后缀\n')
            f.write('*.locked - 常见勒索病毒后缀\n')
            f.write('*coinminer* - 挖矿木马关键词\n')
            f.write('*违纪名单*.exe - 银狐木马变种\n')
            f.write('*裁员名单*.exe - 银狐木马变种\n')
            f.write('*激活工具*.exe - 伪装激活工具的木马\n')


# ================= Windows 底层遍历 =================
FILE_ATTRIBUTE_DIRECTORY     = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
INVALID_FILE_ATTRIBUTES      = 0xFFFFFFFF
TOKEN_ADJUST_PRIVILEGES      = 0x0020
TOKEN_QUERY                  = 0x0008
SE_PRIVILEGE_ENABLED         = 0x00000002

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


def enable_backup_privilege() -> bool:
    if kernel32 is None:
        return False
    try:
        h = wintypes.HANDLE()
        if not kernel32.OpenProcessToken(
                kernel32.GetCurrentProcess(),
                TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, ctypes.byref(h)):
            return False
        class LUID(ctypes.Structure):
            _fields_ = [('LowPart', wintypes.DWORD), ('HighPart', wintypes.LONG)]
        class LAA(ctypes.Structure):
            _fields_ = [('Luid', LUID), ('Attributes', wintypes.DWORD)]
        class TP(ctypes.Structure):
            _fields_ = [('PrivilegeCount', wintypes.DWORD), ('Privileges', LAA)]
        luid = LUID()
        if not kernel32.LookupPrivilegeValueW(None, 'SeBackupPrivilege', ctypes.byref(luid)):
            kernel32.CloseHandle(h)
            return False
        tp = TP(1, LAA(luid, SE_PRIVILEGE_ENABLED))
        kernel32.AdjustTokenPrivileges(h, False, ctypes.byref(tp), 0, None, None)
        kernel32.CloseHandle(h)
        return True
    except Exception:
        return False


def is_reparse(attrs: int) -> bool:
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)


# ================= 数据库 / 病毒库极速规则引擎 =================
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
        elif '-' in line:
            parts = line.split('-', 1)
            if not os.path.isabs(parts[0].strip()) and not parts[0].strip().endswith((':', '\\', '/')):
                return parts[0].strip()
        return line

    def _load_db(self):
        db_path = os.path.join(BASE_DATA_DIR, '数据库.txt')
        if not os.path.isfile(db_path):
            return
        
        with open(db_path, 'r', encoding='utf-8', errors='ignore') as f:
            in_ext_rules = False
            for line in f:
                s_line = line.strip()
                if not s_line:
                    continue
                if s_line.startswith('#'):
                    if '扩展名' in s_line:
                        in_ext_rules = True
                    continue
                
                if ' - ' in s_line:
                    raw = s_line.split(' - ')[0].strip().lower()
                    cat = s_line.split(' - ')[1].strip()
                    
                    # 优先加载扩展名规则 (以.开头)
                    if raw.startswith('.') and in_ext_rules:
                        self.ext_categories[raw] = cat
                        continue
                
                # 加载文件/文件夹路径
                if not in_ext_rules and ('\\' in s_line or '/' in s_line or ':' in s_line):
                    raw = self._parse_line(line)
                    if raw.endswith(os.sep) or raw.endswith('/') or raw.endswith('\\'):
                        self.known_dirs.add(os.path.normcase(os.path.normpath(raw)))
                    elif os.path.splitext(raw)[1]:
                        self.known_files.add(os.path.normcase(os.path.normpath(raw)))
                    else:
                        self.known_dirs.add(os.path.normcase(os.path.normpath(raw)))

    def _load_virus(self):
        v_path = os.path.join(BASE_DATA_DIR, '病毒库.txt')
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
        
        # 1. 病毒库优先
        for pat in self.virus_patterns:
            if pat.search(np_) or pat.search(filename):
                return '病毒文件'
                
        # 2. 扩展名分类规则 (最高优先级，强制匹配)
        ext = os.path.splitext(np_)[1].lower()
        if ext in self.ext_categories:
            return self.ext_categories[ext]

        # 3. 数据库（文件）匹配
        if np_ in self.known_files:
            return '系统文件'
            
        # 4. 数据库（目录）逐层向上匹配
        p = np_
        while True:
            if p in self.known_dirs:
                return '系统文件'
            parent = os.path.dirname(p)
            if parent == p:
                break
            p = parent
            
        # 5. 默认归类
        return '第三方应用文件'


# ================= 日志系统 =================
def _get_today_log_path() -> str:
    return os.path.join(BASE_DATA_DIR, f'{datetime.now():%Y%m%d}.txt')


def _count_today_entries(log_path: str) -> int:
    if not os.path.isfile(log_path):
        return 0
    count = 0
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            if re.match(r'^\d{4}-\d{2}-\d{2}-\d+', line.strip()):
                count += 1
    return count


def write_scan_log(content: str, enable_log=True):
    if not enable_log:
        return
    log_path = _get_today_log_path()
    entry_num = _count_today_entries(log_path) + 1
    now = datetime.now()
    header = f'{now:%Y-%m-%d}-{entry_num} (第{entry_num}次) -{now:%H:%M:%S}'
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'{header}\n{content}\n{"-" * 56}\n')


def write_clean_log(targets_all, cleaned, skipped, total_time_sec, enable_log=True):
    if not enable_log:
        return
    log_path = _get_today_log_path()
    entry_num = _count_today_entries(log_path) + 1
    now = datetime.now()
    total_h = int(total_time_sec // 3600)
    total_m = int((total_time_sec % 3600) // 60)
    total_s = int(total_time_sec % 60)
    header = f'{now:%Y-%m-%d}-{entry_num} (第{entry_num}次) -{now:%H:%M:%S}-总用时{total_h:02d}:{total_m:02d}:{total_s:02d}'

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(f'{header}\n\n')
        f.write('需要清理文件：\n')
        for i, (label, path, size, cat) in enumerate(targets_all, 1):
            f.write(f'{i}. {path}  ({size / 1024**3:.2f} GB)\n')
        if not targets_all:
            f.write('(无)\n')
        f.write('\n已清理文件：\n')
        for i, (path, elapsed) in enumerate(cleaned, 1):
            f.write(f'{i}. {path}    用时{elapsed}\n')
        if not cleaned:
            f.write('(无)\n')
        f.write('\n未清理文件：\n')
        for i, (path, reason) in enumerate(skipped, 1):
            f.write(f'{i}. {path}    ({reason})\n')
        if not skipped:
            f.write('(无)\n')
        f.write(f'\n{"-" * 56}\n')


def load_undo_log() -> List[dict]:
    if os.path.isfile(UNDO_LOG_PATH):
        try:
            with open(UNDO_LOG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_undo_log(entry: dict, enable_save_record=True):
    if not enable_save_record:
        return
    log = load_undo_log()
    log.append(entry)
    with open(UNDO_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


# ================= 1. 主窗口 =================
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
        row_disk.addWidget(QLabel('需要清理的磁盘:'))
        self.combo_disk = QComboBox()
        self.combo_disk.setMinimumWidth(200)
        self.combo_disk.addItem('C:\\')
        row_disk.addWidget(self.combo_disk)
        row_disk.addStretch()
        top_layout.addLayout(row_disk, 1)

        row_theme = QHBoxLayout()
        row_theme.addWidget(QLabel('自定义明暗:'))
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(['亮色', '暗色', '跟随系统设置'])
        self.combo_theme.setCurrentText('跟随系统设置')
        self.combo_theme.currentTextChanged.connect(self.on_theme_changed)
        row_theme.addWidget(self.combo_theme)
        top_layout.addLayout(row_theme, 1)

        main_layout.addLayout(top_layout)

        left_options_group = QVBoxLayout()
        self.chk_admin = QCheckBox('是否为该程序开启管理员权限')
        self.chk_admin.setToolTip('将扫描到更多系统隐藏文件')
        left_options_group.addWidget(self.chk_admin)
        self.chk_enable_log = QCheckBox('在启动后是否开启日志')
        left_options_group.addWidget(self.chk_enable_log)
        self.chk_save_record = QCheckBox('是否保存清理记录')
        left_options_group.addWidget(self.chk_save_record)

        right_dir_group = QVBoxLayout()
        row_log_dir = QHBoxLayout()
        row_log_dir.addWidget(QLabel('日志保存目录:'))
        self.edit_log_dir = QLineEdit(BASE_DATA_DIR)
        btn_log_dir = QPushButton('浏览')
        btn_log_dir.clicked.connect(lambda: self.browse_dir(self.edit_log_dir))
        row_log_dir.addWidget(self.edit_log_dir)
        row_log_dir.addWidget(btn_log_dir)
        right_dir_group.addLayout(row_log_dir)

        row_record_dir = QHBoxLayout()
        row_record_dir.addWidget(QLabel('清理记录保存目录:'))
        self.edit_record_dir = QLineEdit(BASE_DATA_DIR)
        btn_record_dir = QPushButton('浏览')
        btn_record_dir.clicked.connect(lambda: self.browse_dir(self.edit_record_dir))
        row_record_dir.addWidget(self.edit_record_dir)
        row_record_dir.addWidget(btn_record_dir)
        right_dir_group.addLayout(row_record_dir)

        config_and_dir_layout = QHBoxLayout()
        config_and_dir_layout.addLayout(left_options_group, 1)
        config_and_dir_layout.addLayout(right_dir_group, 2)
        main_layout.addLayout(config_and_dir_layout)

        btn_area = QHBoxLayout()
        btn_area.addStretch()
        self.btn_start = QPushButton('启动')
        self.btn_start.setMinimumWidth(100)
        self.btn_cancel = QPushButton('取消')
        self.btn_cancel.setMinimumWidth(100)
        self.btn_start.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        self.btn_cancel.setStyleSheet("font-weight: bold; padding: 5px 15px;")
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

    def browse_dir(self, line_edit):
        d = QFileDialog.getExistingDirectory(self, '选择目录', line_edit.text())
        if d:
            line_edit.setText(d)

    def _apply_theme(self, theme_type):
        palette = self.palette()
        if theme_type == "亮色":
            palette.setColor(QPalette.Window, QColor(240, 240, 240))
            palette.setColor(QPalette.WindowText, QColor(0, 0, 0))
            palette.setColor(QPalette.Base, QColor(255, 255, 255))
            palette.setColor(QPalette.AlternateBase, QColor(230, 230, 230))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, QColor(0, 0, 0))
            palette.setColor(QPalette.Text, QColor(0, 0, 0))
            palette.setColor(QPalette.Button, QColor(240, 240, 240))
            palette.setColor(QPalette.ButtonText, QColor(0, 0, 0))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        else:
            palette.setColor(QPalette.Window, QColor(30, 30, 30))
            palette.setColor(QPalette.WindowText, QColor(240, 240, 240))
            palette.setColor(QPalette.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.AlternateBase, QColor(35, 35, 35))
            palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
            palette.setColor(QPalette.ToolTipText, QColor(255, 255, 255))
            palette.setColor(QPalette.Text, QColor(240, 240, 240))
            palette.setColor(QPalette.Button, QColor(45, 45, 45))
            palette.setColor(QPalette.ButtonText, QColor(240, 240, 240))
            palette.setColor(QPalette.BrightText, QColor(255, 0, 0))
            palette.setColor(QPalette.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        
        QApplication.setPalette(palette)
        for widget in QApplication.allWidgets():
            widget.update()
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _apply_system_theme(self):
        try:
            registry_key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
            try:
                import winreg
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER, registry_key) as key:
                    val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    is_light = (val == 1)
                    if is_light:
                        self._apply_theme("亮色")
                        self.combo_theme.setCurrentText('亮色')
                    else:
                        self._apply_theme("暗色")
                        self.combo_theme.setCurrentText('暗色')
                    return
            except FileNotFoundError:
                pass
        except Exception:
            pass
        self._apply_theme("亮色")
        self.combo_theme.setCurrentText('亮色')

    def on_theme_changed(self, text):
        if text == "跟随系统设置":
            self._apply_system_theme()
        else:
            self._apply_theme(text)

    def on_start_clicked(self):
        selected_disk = self.combo_disk.currentText().strip()
        if not selected_disk:
            QMessageBox.warning(self, '提示', '请选择要扫描的磁盘/路径。')
            return

        enable_admin = self.chk_admin.isChecked()
        enable_log = self.chk_enable_log.isChecked()
        enable_save_record = self.chk_save_record.isChecked()

        if enable_admin:
            write_scan_log(f'用户请求开启管理员权限进行扫描', enable_log)
        
        write_scan_log(f'开始对 {selected_disk} 执行扫描任务', enable_log)
        
        self.hide()
        self.scan_window = ScanWindow(
            self, 
            selected_disk, 
            enable_log=enable_log, 
            enable_save_record=enable_save_record
        )
        self.scan_window.start_scan() 
        self.scan_window.exec()
        self.show()


# ================= 2. 后台扫描线程 =================
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
            self.error_signal.emit(f'扫描异常：{exc}')

    def _run_inner(self):
        self.progress_signal.emit('正在加载规则库 …')
        engine = RuleEngine()
        self.progress_signal.emit(f'正在打开 {self.disk} …')

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
                ename_lower = e.name.lower()
                if ename_lower in SKIP_DIRS:
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
                    f'扫描中… 已扫描 {dirs_seen} 个目录，已处理约 {bytes_seen / 1024 ** 3:.2f} GB'
                )

        flush()

        if self._stopped_by_user:
            self.progress_signal.emit('扫描已终止。')
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

        self.progress_signal.emit('扫描完成！请勾选需要清理的项目。')
        self.result_signal.emit({'large_files': large_files, 'large_folders': large_folders}, perm_errs)


# ================= 3. 扫描弹窗 (含原生绿色动态进度条) =================
class ScanWindow(QDialog):
    def __init__(self, parent, disk, enable_log=True, enable_save_record=True):
        super().__init__(parent)
        self.setWindowTitle('正在扫描磁盘文件')
        self.resize(720, 560)
        self.setMinimumSize(640, 480)
        
        self.disk = disk
        self.enable_log = enable_log
        self.enable_save_record = enable_save_record
        self.current_results = {'large_files': [], 'large_folders': []}
        self._scanning = False
        self._all_items = []
        self._file_row_count = 0
        self._folder_row_count = 0
        self._checked_count = 0

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 1. 强制绿色 Windows 原生动态进度条 (呼吸灯动画)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0) # 设置为 Indeterminate 模式，触发 Windows 原生动画
        self.progress_bar.setMaximumHeight(12)
        self.progress_bar.setTextVisible(False)
        # 强制指定绿色样式
        self.progress_bar.setStyleSheet(
            "QProgressBar {"
            "   border: 1px solid #b8b8b8;"
            "   border-radius: 2px;"
            "   background-color: #e8e8e8;"
            "}"
            "QProgressBar::chunk {"
            "   background-color: #2ecc71;" # 绿色进度条
            "}"
        )
        layout.addWidget(self.progress_bar)

        self.lbl_path = QLabel('正在准备…', self)
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

        self.gb_files = QGroupBox('5GB以上单文件：', self)
        self.gb_files_layout = QVBoxLayout(self.gb_files)
        self.gb_files_layout.setContentsMargins(8, 12, 8, 8)

        self.gb_folders = QGroupBox('5GB以上文件夹：', self)
        self.gb_folders_layout = QVBoxLayout(self.gb_folders)
        self.gb_folders_layout.setContentsMargins(8, 12, 8, 8)

        self.scroll_layout.addWidget(self.gb_files)
        self.scroll_layout.addWidget(self.gb_folders)
        self.scroll_layout.addStretch()
        self.scroll.setWidget(scroll_content)
        layout.addWidget(self.scroll)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel_scan = QPushButton('取消', self)
        self.btn_cancel_scan.setStyleSheet('color: gray; font-size: 13px;')
        self.btn_cancel_scan.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel_scan)

        self.btn_stop = QPushButton('终止任务', self)
        self.btn_stop.setStyleSheet('color: red; font-weight: bold; font-size: 14px;')
        self.btn_stop.clicked.connect(self._on_stop_clicked)
        btn_layout.addWidget(self.btn_stop)

        self.btn_clean = QPushButton('开始清理（0）', self)
        self.btn_clean.setEnabled(False)
        self.btn_clean.setStyleSheet('font-weight: bold; font-size: 14px;')
        self.btn_clean.clicked.connect(self._on_preview_clean)
        btn_layout.addWidget(self.btn_clean)

        layout.addLayout(btn_layout)

    def start_scan(self):
        self._scanning = True
        self.progress_bar.setRange(0, 0) # 开始绿色原生动态扫描
        self.lbl_path.setText(f'正在打开: {self.disk}\\')
        self.btn_stop.setEnabled(True)
        self.btn_stop.setText('终止任务')
        self.btn_clean.setEnabled(False)
        self.btn_clean.setText('开始清理（0）')

        self.worker = ScanWorker(self.disk)
        self.worker.progress_signal.connect(self._on_progress_text)
        self.worker.path_signal.connect(self._on_path_text)
        self.worker.item_signal.connect(self._on_scan_item)
        self.worker.result_signal.connect(self._on_scan_finished)
        self.worker.error_signal.connect(self._on_scan_error)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_progress_text(self, text):
        self.lbl_path.setText(text)

    def _on_path_text(self, path):
        self.lbl_path.setText(f'当前扫描: {path}')

    def _on_worker_finished(self):
        self._scanning = False
        self.btn_stop.setEnabled(False)
        self.btn_clean.setEnabled(self._checked_count > 0)

    def _on_stop_clicked(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.btn_stop.setEnabled(False)
            self.btn_stop.setText('正在终止…')
            self.worker.stop()
            self.lbl_path.setText('正在终止扫描…')

    def _on_scan_error(self, message):
        self._scanning = False
        self.progress_bar.setRange(0, 100) # 停止动画
        self.progress_bar.setValue(0)
        self.lbl_path.setText(message)
        self.btn_stop.setEnabled(False)
        self.btn_clean.setEnabled(False)
        QMessageBox.critical(self, '扫描错误', message)

    def _on_scan_item(self, rows):
        for kind, path, size, cat in rows:
            self._all_items.append((kind, path, size, cat))
            style = CATE_STYLE.get(cat, CATE_STYLE['其他文件'])
            tag_text = style['tag']
            color = style['color']

            cb = QCheckBox()
            cb.setText(f'{tag_text}  ({path})')
            cb.setStyleSheet(f'color: {color}; font-size: 12px;')
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
        if checked:
            self._checked_count += 1
        else:
            self._checked_count = max(0, self._checked_count - 1)
        
        self.btn_clean.setText(f'开始清理（{self._checked_count}）')
        self.btn_clean.setEnabled(not self._scanning and self._checked_count > 0)

    def _clear_rows(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_scan_finished(self, results, perm_errs):
        self.current_results = results
        self._scanning = False
        self.progress_bar.setRange(0, 100) # 停止动画，进度充满
        self.progress_bar.setValue(100)

        total = len(results['large_files']) + len(results['large_folders'])
        tip = f'共找到 {total} 项大文件/文件夹'
        if perm_errs > 0:
            tip += f'，{perm_errs} 处因权限跳过'
        self.lbl_path.setText(f'扫描完成！{tip}。请勾选需要清理的项目。')

        self.btn_clean.setEnabled(self._checked_count > 0)
        self.btn_clean.setText(f'开始清理（{self._checked_count}）')

    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        super().closeEvent(event)

    def _collect_selected(self):
        out = []
        for kind, path, size, cat in self._all_items:
            container = self.gb_files_layout if kind == 'file' else self.gb_folders_layout
            for i in range(container.count()):
                item = container.itemAt(i)
                if item and item.widget() and isinstance(item.widget(), QCheckBox):
                    cb = item.widget()
                    if f'({path})' in cb.text() and cb.isChecked():
                        out.append((kind, path, size, cat))
                        break
        return out

    def _on_preview_clean(self):
        targets = self._collect_selected()
        if not targets:
            QMessageBox.warning(self, '提示', '请先勾选需要清理的项目。')
            return

        total_size = sum(t[2] for t in targets)
        detail = '\n'.join(f'[{t[3]}] {t[2] / 1024**3:.2f} GB | {t[1]}' for t in targets[:30])
        if len(targets) > 30:
            detail += f'\n……共 {len(targets)} 项'

        msg = QMessageBox(self)
        msg.setWindowTitle('清理确认')
        msg.setText(f'即将处理 {len(targets)} 项，合计 {total_size / 1024**3:.2f} GB\n是否继续？')
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

        cleaned = []
        skipped_list = []
        undo_entries = []
        removed = set()
        start_time = time.time()

        sorted_targets = sorted(targets, key=lambda x: len(x[1]), reverse=True)

        for kind, path, size, cat in sorted_targets:
            n = os.path.normcase(path)
            if any(n == r or n.startswith(r + os.sep) for r in removed):
                skipped_list.append((path, '已被上级目录删除覆盖'))
                continue

            item_t0 = time.time()
            try:
                if send2trash:
                    send2trash(path)
                elif os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                undo_entries.append({'action': 'delete', 'path': path})
                cleaned.append((path, self._fmt_elapsed(time.time() - item_t0)))
                removed.add(n)
            except Exception as e:
                skipped_list.append((path, str(e)))

        total_time = time.time() - start_time
        save_undo_log({'time': datetime.now().isoformat(), 'count': len(undo_entries), 'entries': undo_entries}, self.enable_save_record)
        write_clean_log(targets, cleaned, skipped_list, total_time, self.enable_log)

        total_h = int(total_time // 3600)
        total_m = int((total_time % 3600) // 60)
        total_s = int(total_time % 60)
        txt = (f'处理完成：成功 {len(cleaned)}，未清理 {len(skipped_list)}\n'
               f'总用时 {total_h:02d}:{total_m:02d}:{total_s:02d}')
        QMessageBox.information(self, '清理结果', txt)
        self.accept()

    def _fmt_elapsed(self, sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = int(sec % 60)
        return f'{h:02d}:{m:02d}:{s:02d}'


# ================= 4. 程序入口 =================
if __name__ == '__main__':
    def excepthook(t, v, tb):
        import traceback
        traceback.print_exception(t, v, tb)
        try:
            input('程序异常，按回车退出…')
        except Exception:
            pass
    sys.excepthook = excepthook

    init_templates()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
