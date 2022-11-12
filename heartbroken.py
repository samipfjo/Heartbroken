import atexit
import ctypes
import multiprocessing
import os
import time
import typing

from libs import pytotray, hbcontrol, constants
from libs.database import HeartbrokenDatabase
from libs.tokenhandler import TokenHandler, OAuthManager
from libs.spotifywrapper import SpotifyWrapper


TRAY_PROCESS         = None
OAUTH_SERVER_PROCESS = None

# ========
def app_loop(app_loop_should_run: multiprocessing.Event, gui_process_terminated: multiprocessing.Event) -> int:
    """
    The main body of Heartbroken. Controls program initialization as well as the scheduling of calls to the
    Spotify API.

    Returns exit codes 0, 1, or 2 
    """

    spotify = SpotifyWrapper()

    if spotify.initialize_spotify_client() is None:
        print('No account credentials found, running Spotify OAuth flow...')
        global OAUTH_SERVER_PROCESS

        oauth_handler_generator = OAuthManager.do_spotify_oauth()
        OAUTH_SERVER_PROCESS    = next(oauth_handler_generator)
        oauth_result            = next(oauth_handler_generator)

        if oauth_result is None:
            print('\nSomething went wrong while trying to connect your account. Please run Heartbroken again.\n')
            return 1

        spotify.initialize_spotify_client()

    spotify.update_current_track()
    last_logged_track = None
    backing_off = False

    while True:
        if gui_process_terminated.is_set():
            return 0

        app_loop_should_run.wait()

        if TokenHandler.is_token_expired():
            if spotify.initialize_spotify_client() is None:
                print('\nSomething went wrong while trying to connect your account. Please run Heartbroken again.\n')
                return 2

        # Nothing is playing or a network error was encountered
        if hbcontrol.skip_if_heartbroken(spotify) is None:
            if not spotify.backing_off:
                print('\nNothing is currently playing, waiting (ctrl+c to exit)...')

            time.sleep(spotify.get_backoff())

        elif last_logged_track is None or spotify.current_track.id != last_logged_track.id:
            print(f'Currently playing: {spotify.current_track}')
            last_logged_track = spotify.current_track
            spotify.reset_backoff()

        # Keep things nice rate-limiting-wise. Rely on back-off delay otherwise.
        if not backing_off:
            time.sleep(constants.SpotifyAPI.REQUEST_INTERVAL_SECONDS)

# ========
def toggle_auto_skip(menu: pytotray.SysTrayIcon, app_loop_should_run: multiprocessing.Event) -> None:
    """
    GUI callback that handles both altering the system tray menu and setting the main loop's Event
    to its paused state
    """

    # App is currently running, so let's pause it
    if app_loop_should_run.is_set():
        app_loop_should_run.clear()

        menu.icon = './resources/heartbroken-paused.ico'
        menu.refresh_icon()

        menu.change_menu_item_text(0, 'Resume auto-skip')
        menu.enable_menu_item(4)
        menu.enable_menu_item(5)
        menu.enable_menu_item(6)

        print('Heartbroken auto-skip paused')

    # App is currently paused, so let's resume it
    else:
        app_loop_should_run.set()

        menu.icon = './resources/heartbroken.ico'
        menu.refresh_icon()

        menu.change_menu_item_text(0, 'Pause auto-skip')
        menu.disable_menu_item(4)
        menu.disable_menu_item(5)
        menu.disable_menu_item(6)

        print('Heartbroken auto-skip resumed')

# ========
def on_quit_cleanup(app_loop_should_run: multiprocessing.Event, gui_process_terminated: multiprocessing.Event) -> None:
    """
    Handler that sets the program's core Events to their shutdown state
    """

    gui_process_terminated.set()
    app_loop_should_run.set()

# ========
def toggle_console_visibility(forced_visibility_state: typing.Union[None, bool] = None) -> None:
    """
    Toggles the visibility of the Heartbroken console based on either force_visibility_state or
    the global console_is_visible. This is called from the GUI thread, so the global is a workaround
    to maintain that state.

    If :forced_visiblity_state is a boolean, that is the state that the console visibility will be set to
    (True = shown, False = hidden)
    """

    global console_is_visible

    console_is_visible = (not console_is_visible) if forced_visibility_state is None else forced_visibility_state
    visible_flag = 4 if console_is_visible else 0
    ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), visible_flag)

# ========
def gui_runner(app_loop_should_run: multiprocessing.Event, gui_process_terminated: multiprocessing.Event) -> typing.NoReturn:
    """
    Target of the GUI thread. This is where the system tray icon is initialized and its loop runs.
    """

    global console_is_visible
    console_is_visible = False

    icon = './heartbroken.ico' if os.path.isfile('./heartbroken.ico') else './resources/heartbroken.ico'
    hover_text= 'Heartbroken - Dislike for Spotify'

    # A quit option is automatically injected by pytotray
    menu = (
        ('Pause auto-skip',           (lambda menu: toggle_auto_skip(menu, app_loop_should_run)), True),
        ('Dislike current track',     (lambda _: hbcontrol.handle_heartbreak(track=True)),  True),
        ('Dislike current artist',    (lambda _: hbcontrol.handle_heartbreak(artist=True)), True),
        ('Dislike current album',     (lambda _: hbcontrol.handle_heartbreak(album=True)),  True),
        ('Un-dislike current track',  (lambda _: hbcontrol.handle_clear_heartbreak(track=True)),  False),
        ('Un-dislike current artist', (lambda _: hbcontrol.handle_clear_heartbreak(artist=True)), False),
        ('Un-dislike current album',  (lambda _: hbcontrol.handle_clear_heartbreak(album=True)),  False),
        ('Hide/show console',         (lambda _: toggle_console_visibility()), True)
    )

    try:
        tray = pytotray.SysTrayIcon(icon, hover_text, menu,
                                    on_quit=lambda _: on_quit_cleanup(app_loop_should_run, gui_process_terminated))
    except KeyboardInterrupt:
        tray.destroy()

# ========
def main() -> int:
    print('~ HEARTBROKEN FOR SPOTIFY ~\n')

    global TRAY_PROCESS

    if HeartbrokenDatabase.maybe_create_table() == False:
        return 3

    # Set == running
    app_loop_should_run = multiprocessing.Event()
    app_loop_should_run.set()

    tray_process_terminated = multiprocessing.Event()

    TRAY_PROCESS = multiprocessing.Process(target=gui_runner,
                                           args=(app_loop_should_run, tray_process_terminated))
    TRAY_PROCESS.start()
    atexit.register(TRAY_PROCESS.terminate)

    return app_loop(app_loop_should_run, tray_process_terminated)

# ====
if __name__ == '__main__':
    multiprocessing.freeze_support()  # Required for cx_freeze

    try:
        toggle_console_visibility(forced_visibility_state=False)
        exit_code = main()
        print('\nThanks for using Heartbroken!\n')

    except KeyboardInterrupt:
        print('\nThanks for using Heartbroken!\n')
        pass

    except Exception as ex:
        print('\n\n!!! HEARTBROKEN ENCOUNTERED A FATAL ERROR: !!!\n')
        raise

    finally:
        # Ensure processes get cleaned up
        if TRAY_PROCESS is not None and TRAY_PROCESS.is_alive():
            TRAY_PROCESS.terminate()

        if OAUTH_SERVER_PROCESS is not None and OAUTH_SERVER_PROCESS.is_alive():
            OAUTH_SERVER_PROCESS.terminate()
