# pytotray.py
#   Create a Windows tray icon and hook the menu options to Python functions
#
#   Based on Simon Brunning's SysTrayIcon and Mark Hammond's win32gui_taskbar
#   Cleaned up, modified, lost, found, subjected to public inquiry, lost again,
#   and finally buried in soft peat for three months.
#   Luke Jones, 2016; Simon Brunning; Mark Hammond
# ------
         
import os
import sys
from collections import OrderedDict

import pywintypes
import win32api
import win32con
import win32gui_struct
import win32gui


# ------
class SysTrayIcon(object):
    QUIT = 'QUIT'
    SPECIAL_ACTIONS = [QUIT]
    
    FIRST_ID = 1023
    
    def __init__(self,
                 icon,
                 hover_text,
                 menu_options,
                 on_quit=None,
                 default_menu_index=None,
                 window_class_name=None):
        
        self.icon = icon
        self.hover_text = hover_text
        self.on_quit = on_quit

        menu_options += ( ('Quit', self.QUIT, True), )
        
        self._next_action_id = self.FIRST_ID
        
        self.menu_actions_by_id = [ ]
        self.menu_options = self._add_ids_to_menu_options(menu_options)
        self.menu_actions_by_id = OrderedDict(self.menu_actions_by_id)
        
        del self._next_action_id
        
        self.default_menu_index = (default_menu_index or 0)
        self.window_class_name = window_class_name or "PytoTrayApp"
        
        message_map = {win32gui.RegisterWindowMessage("TaskbarCreated"): self.restart,
                       win32con.WM_DESTROY: self.destroy,
                       win32con.WM_COMMAND: self.command,
                       win32con.WM_USER+20: self.notify
                       }
      
        # Register the Window class.
        window_class = win32gui.WNDCLASS()
        hinst = window_class.hInstance = win32gui.GetModuleHandle(None)
        
        window_class.lpszClassName = self.window_class_name
        window_class.style = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        window_class.hCursor = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground = win32con.COLOR_WINDOW
        window_class.lpfnWndProc = message_map # could also specify a wndproc.
        
        # Don't blow up if class already registered to make testing easier
        try:
            classAtom = win32gui.RegisterClass(window_class)
            
        except win32gui.error as err_info:
            #if err_info.winerror != winerror.ERROR_CLASS_ALREADY_EXISTS:
            raise
        
        # Create the window.
        style = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(classAtom,
                                          self.window_class_name,
                                          style, 0, 0,
                                          win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT,
                                          0, 0, hinst, None)
                                          
        win32gui.UpdateWindow(self.hwnd)
        self.notify_id = None
        self.refresh_icon()
        
        win32gui.PumpMessages()

    # ----
    def _add_ids_to_menu_options(self, menu_options):
        result = [ ]

        for menu_option in menu_options:
            option_text, option_action, option_enabled = menu_option

            if callable(option_action) or option_action in self.SPECIAL_ACTIONS:
                self.menu_actions_by_id.append( (self._next_action_id, option_action) )
                result.append(menu_option + ( self._next_action_id, ))

            # Submenu creation
            elif non_string_iterable(option_action):
                result.append(tuple(
                                    (
                                    option_text,
                                    option_enabled,
                                    self._add_ids_to_menu_options(option_action),
                                    self._next_action_id
                                    )
                                )
                            )
                            
            else:
                print('Unknown item', option_text, str(option_enabled), option_action)

            self._next_action_id += 1
        
        return tuple(result)
        
    # ----
    def refresh_icon(self):
        # Try and find a custom icon
        hinst = win32gui.GetModuleHandle(None)

        if os.path.isfile(self.icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(hinst, self.icon,
                                       win32con.IMAGE_ICON,
                                       0, 0, icon_flags)
                                       
        else:
            print("Can't find icon file - using default.")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        message = win32gui.NIM_MODIFY if not self.notify_id is None else win32gui.NIM_ADD
        
        self.notify_id = (self.hwnd, 0,
                          win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                          win32con.WM_USER + 20,
                          hicon, self.hover_text)
                          
        win32gui.Shell_NotifyIcon(message, self.notify_id)

    # ----
    def restart(self, hwnd, msg, wparam, lparam):
        self.refresh_icon()

    # ----
    def destroy(self, hwnd, msg, wparam, lparam):
        if not self.on_quit is None: self.on_quit(self)
        
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0) # Terminate the app.
        
    # ----
    def notify(self, hwnd, msg, wparam, lparam):
##        if lparam == win32con.WM_LBUTTONDBLCLK:
##            self.execute_menu_option(self.default_menu_index + self.FIRST_ID)

        if lparam == win32con.WM_RBUTTONUP:
            self.show_menu()
            
        elif lparam == win32con.WM_LBUTTONUP:
            self.execute_menu_option(self.default_menu_index + self.FIRST_ID)
            
        return True
        
    # ----
    def show_menu(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu, self.menu_options)
        
        pos = win32gui.GetCursorPos()
        
        # This error happens for unknown reasons; ignorning it doesn't seem to cause any harm
        try:
            # See http://msdn.microsoft.com/library/default.asp?url=/library/en-us/winui/menus_0hdi.asp
            win32gui.SetForegroundWindow(self.hwnd)

        except pywintypes.error as ex:
            if str(ex) == "(0, 'SetForegroundWindow', 'No error message is available')":
                return
            raise

        win32gui.TrackPopupMenu(menu,
                                win32con.TPM_LEFTALIGN,
                                pos[0], pos[1], 0,
                                self.hwnd, None)
                                
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)
    
    # ----
    def create_menu(self, menu, menu_options):
        for option_text, option_action, option_enabled, option_id in menu_options[::-1]:
            fstate = 0x3 if option_enabled == False else 0x0

            if option_id in self.menu_actions_by_id:
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                fState=fstate,
                                                                wID=option_id)  # fMask=0x40 | 0x1 | 0x2,
                win32gui.InsertMenuItem(menu, 0, 1, item)

            else:
                submenu = win32gui.CreatePopupMenu()
                self.create_menu(submenu, option_action)
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                fState=fstate,
                                                                hSubMenu=submenu)  # fMask=0x40 | 0x1 | 0x4,
                win32gui.InsertMenuItem(menu, 0, 1, item)

    # ----
    def change_menu_item_text(self, index, new_text):
        _, option_action, option_enabled, option_id = self.menu_options[index]

        new_menu_items = list(self.menu_options)
        new_menu_items[index] = (new_text, option_action, option_enabled, option_id)
        self.menu_options = tuple(new_menu_items)

    # ----
    def _set_menu_item_state(self, index, is_enabled):
        option_text, option_action, _, option_id = self.menu_options[index]

        new_menu_items = list(self.menu_options)
        new_menu_items[index] = (option_text, option_action, is_enabled, option_id)
        self.menu_options = tuple(new_menu_items)

    def disable_menu_item(self, index):
        self._set_menu_item_state(index, False)

    def enable_menu_item(self, index):
        self._set_menu_item_state(index, True)

    # ----
    def command(self, hwnd, msg, wparam, lparam):
        m_id = win32gui.LOWORD(wparam)
        self.execute_menu_option(m_id)
        
    # ----
    def execute_menu_option(self, m_id):
        menu_action = self.menu_actions_by_id[m_id]
        
        if menu_action == self.QUIT:
            win32gui.DestroyWindow(self.hwnd)
        else:
            menu_action(self)
            
# ------
def non_string_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return not isinstance(obj, str)
