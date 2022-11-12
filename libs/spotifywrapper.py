import json
import time
import typing

import requests_oauthlib

from libs import constants, utils
from libs.tokenhandler import TokenHandler, OAuthManager


class Track:
    """
    Wrapper for data related to Spotify tracks
    """

    def __init__(self, json_response):
        self._data = json_response or {}
        self._track_data = self._data.get('item', {})

        self.is_playing = self._data.get('is_playing', False)
        if self.is_playing == False or self._track_data is None:
            self._time_remaining_ms = -1
            self.name = None
            self.id = None
            self.type = None
            self.album = None
            self.album_id = None
            self.artists = []
            self.artist_ids = []

        else:
            self.time_remaining_ms = self._track_data.get('duration_ms', -1) - self._data.get('progress_ms', 0) \
                                     if self.is_playing == True else -1

            self.name       = self._track_data.get('name', None)
            self.id         = self._track_data.get('id',   None)
            self.type       = self._track_data.get('currently_playing_type', None)  # track, episode, ad, unknown
            self.album      = utils._deep_get(self._track_data, ('album', 'name'), None)
            self.album_id   = utils._deep_get(self._track_data, ('album', 'id'),   None)

            _artists        = self._track_data.get('artists', {})
            self.artists    = Track.format_artist_list([a.get('name', None) for a in _artists])
            self.artist_ids = [a.get('id', None) for a in _artists]

        # This is populated externally
        self.track_heartbroken  = None
        self.album_heartbroken  = None
        self.artist_heartbroken = None

    # ====
    def __str__(self) -> str:
        if not self.is_playing:
            return 'Nothing is currently being played'
        return f'"{self.name}" by "{self.artists}"'

    # ====
    def __repr__(self) -> str:
        if not self.is_playing:
            return 'None'
        return f'"{self.name}" by "{self.artists}" - track ID {self.id}'

    # ========
    @staticmethod
    def format_artist_list(artists: typing.List[str]) -> str:
        """
        Turns an array of artist names into a English list
        """

        artists = [a for a in artists if type(a) == str and a != '']

        if len(artists) == 1:
            return artists[0]
        if len(artists) == 2:
            return ' and '.join(artists)
        else:
            return ', '.join(artists[:-1]) + ', and ' + artists[-1]

# ========
class SpotifyWrapper:
    """
    Provides an interface for interacting with the Spotify API
    """

    api_url = "https://api.spotify.com/v1"

    def __init__(self):
        self.client_id = TokenHandler.client_id

        self.client  = None
        self.backoff = SpotifyWrapper.not_playing_backoff()
        self.backing_off = False

        self.previous_track = None
        self.current_track  = None

    # ====
    def initialize_spotify_client(self) -> typing.Union[None, requests_oauthlib.OAuth2Session]:
        """
        Refreshes the access token and returns either an OAuth instance or None if the refresh failed

        Side effect: initializes self.client (duh ;))
        """

        access_token = TokenHandler.refresh_access_token()

        if access_token is None:
            return None

        self.client = OAuthManager.build_oauth_session(self.client_id, access_token)

        return self.client

   # ====
    def needs_initialized_client(func: typing.Callable) -> typing.Callable:
        """
        Decorator to automatically check if the client has been initialized before calling a method that needs it
        """

        def initialized_checker(self, *func_arguments):
            if self.client is None:
                print(f'Oops! Spotify client was uninitialized while trying to call {func.__name__}!')
                return
            return func(self, *func_arguments)

        return initialized_checker

    # ====
    @needs_initialized_client
    def update_current_track(self) -> typing.Union[Track, None, int]:
        """
        Gets the current track from the Spotify API, creates a Track object for it, and returns it.

        Returns None if nothing is playing and -1 on failure

        Side effect: sets self.current_track and self._previous track
            Note: self.previous_track is not overwritten if it is the same as self.current_track
        """

        response = self.client.get(f"{SpotifyWrapper.api_url}/me/player/currently-playing")

        if response.status_code >= 300 or response.status_code < 200:
            print('Something went wrong while requesting the current song:')
            print(f'HTTP {response.status_code} : {response.text}')
            return -1

        try:
            track = Track(response.json())

        except json.JSONDecodeError:
            if response.status_code == 204:
                return None
            else:
                print('Something unexpected happened while requesting the current song:')
                print(f'HTTP {response.status_code} : {response.text}')
                return -1

        # A podcast or nothing is being listened to
        if track.type == 'show' or not track.is_playing:
            self.current_track = None
            return None

        # Do not wipe out previous track if song is on repeat
        if self.current_track is not None and self.current_track.id != track.id:
            self.previous_track = self.current_track

        self.current_track = track

        return track

    # ====
    @needs_initialized_client
    def skip_current_track(self) -> typing.Union[Track, int]:
        """
        Skips the track that is currently playing
        Returns either a Track for the new track or -1 on failure

        SIDE EFFECT: Updates the current track
        """

        response = self.client.post(f"{SpotifyWrapper.api_url}/me/player/next")

        if response.status_code == 403:
            error_message = response.json().get('error', {}).get('message', None)

            # User interacted with Spotify (skip, pause) while we were processing,
            # so wait for things to settle and then return the current track
            if error_message == 'Player command failed: Restriction violated':
                time.sleep(constants.SpotifyAPI.REQUEST_DELAY_COMPENSATION_MS / 1000)
                return self.update_current_track()

        if response.status_code >= 300 or response.status_code < 200:
            print('Something went wrong while trying to skip the current song:')
            print(f'HTTP {response.status_code} : "{response.text or "<no message>"}"')
            return -1

        time.sleep(constants.SpotifyAPI.REQUEST_DELAY_COMPENSATION_MS / 1000)

        return self.update_current_track()

    # ====
    @needs_initialized_client
    def stop_playback(self) -> typing.Union[bool, int]:
        """
        Stops (really pauses) Spotify playback
        Returns True on success and -1 on failure

        Side effect: sets self.previous_track and self.current_track (the latter to None)
        """

        response = self.client.put(f"{SpotifyWrapper.api_url}/me/player/pause")

        if response.status_code >= 300 or response.status_code < 200:
            print('Something went wrong while trying to stop playback:')
            print(f'HTTP {response.status_code} : "{response.text or "<no message>"}"')
            return -1

        self.previous_track = self.current_track
        self.current_track  = None

        return True

    # ========
    @staticmethod
    def get_current_track_static(client_id: str) -> typing.Union[Track, bool, None]:
        """
        Provides an encapsulated method for getting the current track from threads without access to the wrapper instance.
        Returns a Track for the current track, None if nothing is playing, or False on failure
        """

        access_token = TokenHandler.refresh_access_token()

        # Something went wrong during the oauth process
        if access_token is None:
            print('Could not establish OAuth session with Spotify; is your account connected?')
            return False

        client = OAuthManager.build_oauth_session(client_id, access_token)
        response = client.get(f"{SpotifyWrapper.api_url}/me/player/currently-playing")

        if response.status_code >= 300 or response.status_code < 200:
            print('Something went wrong while trying to skip the current song:')
            print(f'HTTP {response.status_code} : "{response.text or "<no message>"}"')
            return False

        # Gotta love consistent APIs
        if response.status_code == 204:
            return None

        json_data = response.json()
        track = Track(json_data)

        if track.type == 'show' or not track.is_playing:
            return None

        return track

    # ========
    @staticmethod
    def skip_current_track_static(client_id: str) -> bool:
        """
        Provides an encapsulated method for skipping the current track from threads without access to the wrapper instance.
        Returns True on success and False on failure
        """

        access_token = TokenHandler.refresh_access_token()

        # Something went wrong during the oauth process
        if access_token is None:
            print('Could not establish oauth session; is your account connected?')
            return False

        client = OAuthManager.build_oauth_session(client_id, access_token)
        response = client.post(f"{SpotifyWrapper.api_url}/me/player/next")

        if response.status_code >= 300 or response.status_code < 200:
            print('Something went wrong while trying to skip the current song:')
            print(f'HTTP {response.status_code} : "{response.text or "<no message>"}"')
            return False

        return True

    # ========
    def get_backoff(self) -> int:
        """
        Get number of seconds to wait for before trying the next API call, which increases with time
        """
        self.backing_off = True
        return next(self.backoff)

    # ====
    def reset_backoff(self) -> None:
        """
        Set API call attempt wait time back to its initial value
        """
        self.backing_off = False
        self.backoff = SpotifyWrapper.not_playing_backoff()

    # ====
    @staticmethod
    def not_playing_backoff():
        """
        Tracks the number of seconds to wait for before trying the next API call, which increases with time.
        This is handled internally, use get_backoff() and reset_backoff() to access it.

        1*4 => 2*4 => 5*2 => 10 => 15 => 30 => 45 => 60 forever
        """

        for _ in range(4): yield 1
        for _ in range(4): yield 2
        for _ in range(2): yield 5

        for val in (10, 15, 30, 45):
            yield val

        while True:
            yield 60
