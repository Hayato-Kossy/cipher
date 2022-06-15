"""
Pyperclip

プレーンテキストへのコピー＆ペースト機能を備えた、Python用のクロスプラットフォームなクリップボードモジュール.
作者: Al Sweigart al@inventwithpython.com
BSD License

書式:
  import pyperclip
  pyperclip.copy('The text to be copied to the clipboard.')
  spam = pyperclip.paste()

  if not pyperclip.is_available():
    print("Copy functionality unavailable!")

Windowsの場合、追加のモジュールは必要ない.
Macの場合、pyobjモジュールが使われ、pbcopyとpbpasteといったcliコマンドにフォールバックする
（これらのコマンドはmacOSに付属しているはず）.
Linuxの場合、パッケージマネージャーでxclipまたはxselをインストールする.例：Debianの場合は、以下の通り.
    sudo apt install xclip
    sudo apt install xsel

他のLinuxの場合、gtkまたはPyQt5/PyQt4モジュールをインストールする必要がある.

gtkとPyQt4モジュールはまだPyGObjectで動作しないため、
Python 3で利用できない.

注意: 以下によると、Python 3でgtkを取得する方法があるようだ.
    https://askubuntu.com/questions/697397/python3-is-not-supporting-gtk-module

Cygwinは現在サポートしていない.

セキュリティ上の注意: 本モジュールは以下の名前のプログラムを実行する.
    - which
    - where
    - pbcopy
    - pbpaste
    - xclip
    - xsel
    - klipper
    - qdbus
悪意のあるユーザーは、これらの名前のプログラムをリネームしたり追加したりして、
pyperclipをだまし、Pythonプロセスが持つ権限で実行させられる.

"""
__version__ = '1.6.0'

import contextlib
import ctypes
import os
import platform
import subprocess
import sys
import time
import warnings

from ctypes import c_size_t, sizeof, c_wchar_p, get_errno, c_wchar


# 環境変数DISPLAYが設定されていない場合は、 `import PyQt4` sys.exit()を実行する.
# よって、設定されていない場合は、PyQt4を読み込まないように、
# 手動で$DISPLAYを検出する必要がある.
HAS_DISPLAY = os.getenv("DISPLAY", False)

EXCEPT_MSG = """
    Pyperclip could not find a copy/paste mechanism for your system.
    For more information, please visit https://pyperclip.readthedocs.io/en/latest/introduction.html#not-implemented-error """

PY2 = sys.version_info[0] == 2

STR_OR_UNICODE = unicode if PY2 else str

ENCODING = 'utf-8'

# whichというUNIXコマンドは、コマンドがどこにあるかを見つける.
if platform.system() == 'Windows':
    WHICH_CMD = 'where'
else:
    WHICH_CMD = 'which'

def _executable_exists(name):
    return subprocess.call([WHICH_CMD, name],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE) == 0



# 例外クラス.
class PyperclipException(RuntimeError):
    pass

class PyperclipWindowsException(PyperclipException):
    def __init__(self, message):
        message += " (%s)" % ctypes.WinError()
        super(PyperclipWindowsException, self).__init__(message)



def init_osx_pbcopy_clipboard():

    def copy_osx_pbcopy(text):
        p = subprocess.Popen(['pbcopy', 'w'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode(ENCODING))

    def paste_osx_pbcopy():
        p = subprocess.Popen(['pbpaste', 'r'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode(ENCODING)

    return copy_osx_pbcopy, paste_osx_pbcopy


def init_osx_pyobjc_clipboard():
    def copy_osx_pyobjc(text):
        '''クリップボードに引数の文字列をコピーする.'''
        newStr = Foundation.NSString.stringWithString_(text).nsstring()
        newData = newStr.dataUsingEncoding_(Foundation.NSUTF8StringEncoding)
        board = AppKit.NSPasteboard.generalPasteboard()
        board.declareTypes_owner_([AppKit.NSStringPboardType], None)
        board.setData_forType_(newData, AppKit.NSStringPboardType)

    def paste_osx_pyobjc():
        "Returns contents of clipboard"
        board = AppKit.NSPasteboard.generalPasteboard()
        content = board.stringForType_(AppKit.NSStringPboardType)
        return content

    return copy_osx_pyobjc, paste_osx_pyobjc


def init_gtk_clipboard():
    global gtk
    import gtk

    def copy_gtk(text):
        global cb
        cb = gtk.Clipboard()
        cb.set_text(text)
        cb.store()

    def paste_gtk():
        clipboardContents = gtk.Clipboard().wait_for_text()
        # Ptyhon 2のために、クリップボードが空のときはNoneを返す.
        if clipboardContents is None:
            return ''
        else:
            return clipboardContents

    return copy_gtk, paste_gtk


def init_qt_clipboard():
    global QApplication
    # $DISPLAYは存在する必要がある.

    # qtpyからのインポートを試すが、失敗した場合はPyQt5、PyQt4を試す.
    try:
        from qtpy.QtWidgets import QApplication
    except:
        try:
            from PyQt5.QtWidgets import QApplication
        except:
            from PyQt4.QtGui import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    def copy_qt(text):
        cb = app.clipboard()
        cb.setText(text)

    def paste_qt():
        cb = app.clipboard()
        return STR_OR_UNICODE(cb.text())

    return copy_qt, paste_qt


def init_xclip_clipboard():
    DEFAULT_SELECTION='c'
    PRIMARY_SELECTION='p'

    def copy_xclip(text, primary=False):
        selection=DEFAULT_SELECTION
        if primary:
            selection=PRIMARY_SELECTION
        p = subprocess.Popen(['xclip', '-selection', selection],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode(ENCODING))

    def paste_xclip(primary=False):
        selection=DEFAULT_SELECTION
        if primary:
            selection=PRIMARY_SELECTION
        p = subprocess.Popen(['xclip', '-selection', selection, '-o'],
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE,
                             close_fds=True)
        stdout, stderr = p.communicate()
        # クリップボードが空の場合は標準エラーに出力するが、余計なものとして扱い意図的に無視する.
        return stdout.decode(ENCODING)

    return copy_xclip, paste_xclip


def init_xsel_clipboard():
    DEFAULT_SELECTION='-b'
    PRIMARY_SELECTION='-p'

    def copy_xsel(text, primary=False):
        selection_flag = DEFAULT_SELECTION
        if primary:
            selection_flag = PRIMARY_SELECTION
        p = subprocess.Popen(['xsel', selection_flag, '-i'],
                             stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=text.encode(ENCODING))

    def paste_xsel(primary=False):
        selection_flag = DEFAULT_SELECTION
        if primary:
            selection_flag = PRIMARY_SELECTION
        p = subprocess.Popen(['xsel', selection_flag, '-o'],
                             stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()
        return stdout.decode(ENCODING)

    return copy_xsel, paste_xsel


def init_klipper_clipboard():
    def copy_klipper(text):
        p = subprocess.Popen(
            ['qdbus', 'org.kde.klipper', '/klipper', 'setClipboardContents',
             text.encode(ENCODING)],
            stdin=subprocess.PIPE, close_fds=True)
        p.communicate(input=None)

    def paste_klipper():
        p = subprocess.Popen(
            ['qdbus', 'org.kde.klipper', '/klipper', 'getClipboardContents'],
            stdout=subprocess.PIPE, close_fds=True)
        stdout, stderr = p.communicate()

        # 回避方法: https://bugs.kde.org/show_bug.cgi?id=342874
        # TODO: https://github.com/asweigart/pyperclip/issues/43
        clipboardContents = stdout.decode(ENCODING)
        # 空であっても、Klipperは最後に改行を追加する.
        assert len(clipboardContents) > 0
        # 改行を入れる.
        assert clipboardContents.endswith('\n')
        if clipboardContents.endswith('\n'):
            clipboardContents = clipboardContents[:-1]
        return clipboardContents

    return copy_klipper, paste_klipper


def init_dev_clipboard_clipboard():
    def copy_dev_clipboard(text):
        if text == '':
            warnings.warn('Pyperclip cannot copy a blank string to the clipboard on Cygwin. This is effectively a no-op.')
        if '\r' in text:
            warnings.warn('Pyperclip cannot handle \\r characters on Cygwin.')

        fo = open('/dev/clipboard', 'wt')
        fo.write(text)
        fo.close()

    def paste_dev_clipboard():
        fo = open('/dev/clipboard', 'rt')
        content = fo.read()
        fo.close()
        return content

    return copy_dev_clipboard, paste_dev_clipboard


def init_no_clipboard():
    class ClipboardUnavailable(object):

        def __call__(self, *args, **kwargs):
            raise PyperclipException(EXCEPT_MSG)

        if PY2:
            def __nonzero__(self):
                return False
        else:
            def __bool__(self):
                return False

    return ClipboardUnavailable(), ClipboardUnavailable()




# Windows関連のクリップボード機能.
class CheckedCall(object):
    def __init__(self, f):
        super(CheckedCall, self).__setattr__("f", f)

    def __call__(self, *args):
        ret = self.f(*args)
        if not ret and get_errno():
            raise PyperclipWindowsException("Error calling " + self.f.__name__)
        return ret

    def __setattr__(self, key, value):
        setattr(self.f, key, value)


def init_windows_clipboard():
    global HGLOBAL, LPVOID, DWORD, LPCSTR, INT, HWND, HINSTANCE, HMENU, BOOL, UINT, HANDLE
    from ctypes.wintypes import (HGLOBAL, LPVOID, DWORD, LPCSTR, INT, HWND,
                                 HINSTANCE, HMENU, BOOL, UINT, HANDLE)

    windll = ctypes.windll
    msvcrt = ctypes.CDLL('msvcrt')

    safeCreateWindowExA = CheckedCall(windll.user32.CreateWindowExA)
    safeCreateWindowExA.argtypes = [DWORD, LPCSTR, LPCSTR, DWORD, INT, INT,
                                    INT, INT, HWND, HMENU, HINSTANCE, LPVOID]
    safeCreateWindowExA.restype = HWND

    safeDestroyWindow = CheckedCall(windll.user32.DestroyWindow)
    safeDestroyWindow.argtypes = [HWND]
    safeDestroyWindow.restype = BOOL

    OpenClipboard = windll.user32.OpenClipboard
    OpenClipboard.argtypes = [HWND]
    OpenClipboard.restype = BOOL

    safeCloseClipboard = CheckedCall(windll.user32.CloseClipboard)
    safeCloseClipboard.argtypes = []
    safeCloseClipboard.restype = BOOL

    safeEmptyClipboard = CheckedCall(windll.user32.EmptyClipboard)
    safeEmptyClipboard.argtypes = []
    safeEmptyClipboard.restype = BOOL

    safeGetClipboardData = CheckedCall(windll.user32.GetClipboardData)
    safeGetClipboardData.argtypes = [UINT]
    safeGetClipboardData.restype = HANDLE

    safeSetClipboardData = CheckedCall(windll.user32.SetClipboardData)
    safeSetClipboardData.argtypes = [UINT, HANDLE]
    safeSetClipboardData.restype = HANDLE

    safeGlobalAlloc = CheckedCall(windll.kernel32.GlobalAlloc)
    safeGlobalAlloc.argtypes = [UINT, c_size_t]
    safeGlobalAlloc.restype = HGLOBAL

    safeGlobalLock = CheckedCall(windll.kernel32.GlobalLock)
    safeGlobalLock.argtypes = [HGLOBAL]
    safeGlobalLock.restype = LPVOID

    safeGlobalUnlock = CheckedCall(windll.kernel32.GlobalUnlock)
    safeGlobalUnlock.argtypes = [HGLOBAL]
    safeGlobalUnlock.restype = BOOL

    wcslen = CheckedCall(msvcrt.wcslen)
    wcslen.argtypes = [c_wchar_p]
    wcslen.restype = UINT

    GMEM_MOVEABLE = 0x0002
    CF_UNICODETEXT = 13

    @contextlib.contextmanager
    def window():
        """
        有効なWindows hwndを提供するコンテキスト.
        """
        # 実際にはhwndが必要なので、
        # 事前に定義されたlpClassとして"STATIC"を設定するだけで十分である.
        hwnd = safeCreateWindowExA(0, b"STATIC", None, 0, 0, 0, 0, 0,
                                   None, None, None, None)
        try:
            yield hwnd
        finally:
            safeDestroyWindow(hwnd)

    @contextlib.contextmanager
    def clipboard(hwnd):
        """
        クリップボードを開き、
        他のアプリケーションをがクリップボードの内容を変更できないようにするコンテキストマネージャー.
        """
        # 他のアプリケーションがアクセスしているため、
        # クリップボードのハンドルをすぐに取得できない場合がある.
        # クリップボードを取得するために、少なくとも500ミリ秒の時間をかけている.
        t = time.time() + 0.5
        success = False
        while time.time() < t:
            success = OpenClipboard(hwnd)
            if success:
                break
            time.sleep(0.01)
        if not success:
            raise PyperclipWindowsException("Error calling OpenClipboard")

        try:
            yield
        finally:
            safeCloseClipboard()

    def copy_windows(text):
        # この関数は、次の機能に大きく依存しています.
        # http://msdn.com/ms649016#_win32_Copying_Information_to_the_Clipboard
        with window() as hwnd:
            # http://msdn.com/ms649048
            # アプリケーションがhwndをNULLに設定してOpenClipboardを呼び出すと、
            # EmptyClipboardはクリップボードの所有者をNULLに設定する.
            # これはSetClipboardDataが失敗する原因になる.
            # => 何かをコピーするには、有効なhwndが必要である.
            with clipboard(hwnd):
                safeEmptyClipboard()

                if text:
                    # http://msdn.com/ms649051
                    # hMemパラメーターがメモリーオブジェクトを識別するなら、
                    # メモリーオブジェクトはGMEM_MOVEABLEフラグを持つ関数を使用して
                    # 割り当てられていなければならない.
                    count = wcslen(text) + 1
                    handle = safeGlobalAlloc(GMEM_MOVEABLE,
                                             count * sizeof(c_wchar))
                    locked_handle = safeGlobalLock(handle)

                    ctypes.memmove(c_wchar_p(locked_handle), c_wchar_p(text), count * sizeof(c_wchar))

                    safeGlobalUnlock(handle)
                    safeSetClipboardData(CF_UNICODETEXT, handle)

    def paste_windows():
        with clipboard(None):
            handle = safeGetClipboardData(CF_UNICODETEXT)
            if not handle:
                # クリップボードが空なら、
                # GetClipboardDataはerrno == NO_ERRORでNULLを返すことがある.
                # （また、空のバッファへのハンドルを返すこともあるが、
                # 技術的に空ではない）
                return ""
            return c_wchar_p(handle).value

    return copy_windows, paste_windows




# クリップボード機能の自動検出とインポートは、deteremine_clipboard()で行う.
def determine_clipboard():
    '''
    OS・プラットフォームはを決定し、
    それに応じてcopy()とpaste()の関数を設定する.
    '''

    global Foundation, AppKit, gtk, qtpy, PyQt4, PyQt5

    # CYGWINプラットフォーム向けのセットアップ.
    if 'cygwin' in platform.system().lower(): # Cygwinはplatform.system()が返す値の中に'CYGWIN_NT-6.1'のような様々な値を持っている.
        # FIXME: pyperclipは現在Cygwinをサポートしていない.
        # https://github.com/asweigart/pyperclip/issues/55 を参照.
        if os.path.exists('/dev/clipboard'):
            warnings.warn('Pyperclip\'s support for Cygwin is not perfect, see https://github.com/asweigart/pyperclip/issues/55')
            return init_dev_clipboard_clipboard()

    # WINDOWSプラットフォーム向けのセットアップ.
    elif os.name == 'nt' or platform.system() == 'Windows':
        return init_windows_clipboard()

    # macOSプラットフォーム向けのセットアップ.
    if os.name == 'mac' or platform.system() == 'Darwin':
        try:
            import Foundation  # pyobjcがインストールされているかを確認する.
            import AppKit
        except ImportError:
            return init_osx_pbcopy_clipboard()
        else:
            return init_osx_pyobjc_clipboard()

    # LINUXプラットフォーム向けのセットアップ.
    if HAS_DISPLAY:
        try:
            import gtk  # gtkがインストールされているかどうかを確認する.
        except ImportError:
            pass # ImportError以外の全例外に対して、高速に失敗させたいと考えている.
        else:
            return init_gtk_clipboard()

        if _executable_exists("xclip"):
            return init_xclip_clipboard()
        if _executable_exists("xsel"):
            return init_xsel_clipboard()
        if _executable_exists("klipper") and _executable_exists("qdbus"):
            return init_klipper_clipboard()

        try:
            # qtpyは小さな抽象化レイヤーで、PyQtやPySideへの単一のAPI呼び出しを使ってアプリケーションを書ける.
            # https://pypi.python.org/pypi/QtPy
            import qtpy  # qtpyがインストールされているかを確認する.
        except ImportError:
            # qtpyがインストールされていないなら、PyQt4のインポートに頼る.
            try:
                import PyQt5  # PyQt5がインストールされているかを確認する.
            except ImportError:
                try:
                    import PyQt4  # PyQt4がインストールされているかを確認する.
                except ImportError:
                    pass # ImportError以外の全例外に対して、高速に失敗させたいと考えている.
                else:
                    return init_qt_clipboard()
            else:
                return init_qt_clipboard()
        else:
            return init_qt_clipboard()


    return init_no_clipboard()


def set_clipboard(clipboard):
    '''
    クリップボード機構を明示的に設定する.
    クリップボード機構とは、コピー・ペースト機能を実装するために、copy()およびpaste()関数がOSとどのように相互に作用するかということである.
    クリップボードのパラメータは次のいずれかでなければならない.
        - pbcopy
        - pbobjc （macOSでのデフォルト）
        - gtk
        - qt
        - xclip
        - xsel
        - klipper
        - windows（Windowsでのデフォルト）
        - no（これはクリップボード機構が見つからない場合に設定される）
    '''
    global copy, paste

    clipboard_types = {'pbcopy': init_osx_pbcopy_clipboard,
                       'pyobjc': init_osx_pyobjc_clipboard,
                       'gtk': init_gtk_clipboard,
                       'qt': init_qt_clipboard, # TODO - これを'qtpy'、'pyqt4'、'pyqt5'に分割する.
                       'xclip': init_xclip_clipboard,
                       'xsel': init_xsel_clipboard,
                       'klipper': init_klipper_clipboard,
                       'windows': init_windows_clipboard,
                       'no': init_no_clipboard}

    if clipboard not in clipboard_types:
        raise ValueError('Argument must be one of %s' % (', '.join([repr(_) for _ in clipboard_types.keys()])))

    # pyperclipのcopy()とpaste()関数を設定する.
    copy, paste = clipboard_types[clipboard]()


def lazy_load_stub_copy(text):
    '''
    copy()のスタブ関数であり、
    本物のcopy()関数を最後に呼び出すために使用する.

    これによりクリップボード機構が選択したdetermine_clipboard()を自動的に実行せずに、
    pyperclipをインポートできるようになる.
    これは、例えばメモリーを多用するPyQt4モジュールを選択したとしても、
    ユーザーがすぐにset_clipboard()を呼び出して
    別のクリップボード機構を使おうとしている場合に問題になる可能性がある.

    このスタブ関数が実装する遅延ロードは、
    ユーザーにset_clipboard()を呼び出して別のクリップボード機構を選択する機会を与える.
    あるいは、ユーザーがset_clipboard()を最初に呼び出さずに
    copy()やpaste()を単純に呼び出した場合は、
    determine_clipboard()が自動的に選択するクリップボード機構にフォールバックする.
    '''
    global copy, paste
    copy, paste = determine_clipboard()
    return copy(text)


def lazy_load_stub_paste():
    '''
    paste()のスタブ関数であり、
    本物のpaste()関数を最後に呼び出すために使用する.

    これによりクリップボード機構が選択したdetermine_clipboard()を自動的に実行せずに、
    pyperclipをインポートできるようになる.
    これは、例えばメモリーを多用するPyQt4モジュールを選択したとしても、
    ユーザーがすぐにset_clipboard()を呼び出して
    別のクリップボード機構を使おうとしている場合に問題になる可能性がある.

    このスタブ関数が実装する遅延ロードは、
    ユーザーにset_clipboard()を呼び出して別のクリップボード機構を選択する機会を与える.
    あるいは、ユーザーがset_clipboard()を最初に呼び出さずに
    copy()やpaste()を単純に呼び出した場合は、
    determine_clipboard()が自動的に選択するクリップボード機構にフォールバックする.
    '''
    global copy, paste
    copy, paste = determine_clipboard()
    return paste()


def is_available():
    return copy != lazy_load_stub_copy and paste != lazy_load_stub_paste


# 最初にset_clipboard()またはdetermine_clipboard()が呼び出されない限り、
# copy()とpaste()は遅延ロードラッパーに設定され、
# 初めて使用されたときに`copy`と`paste`が本物の関数に設定される.
copy, paste = lazy_load_stub_copy, lazy_load_stub_paste


__all__ = ['copy', 'paste', 'set_clipboard', 'determine_clipboard']


