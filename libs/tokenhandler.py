import json
import multiprocessing
import queue
import sys
import time
import typing
import webbrowser
import http.server
import urllib.parse

import requests
import requests_oauthlib

from libs.utils import StaticClass


# ========
class TokenHandler (StaticClass):
    """
    Static class that stores the methods and info necessary for authenticating with the Spotify API.
    """

    client_id    = "{inject_client_id}"  # Spotify API client id
    token_url    = "{inject_token_url}"  # URL from which access tokens will be received (handled remotely to protect client secret)
    auth_scope   = "user-read-currently-playing user-modify-playback-state"
    redirect_uri = "http://127.0.0.1:8551/callback"

    credentials_file_name = 'heartbroken_auth.json'

    # ========
    @staticmethod
    def is_token_expired() -> bool:
        """
        Loads the credentials from their file and returns a boolean indicating if they are expired
        """

        tokens = TokenHandler.load_credentials_from_file()
        return tokens['expires_at'] - time.time() <= 1

    # ========
    @staticmethod
    def refresh_access_token() -> typing.Union[None, str]:
        """
        Load an access token from its file and return it if it is not expired.
            If is are expired, request a new access token from the Heartbroken servers.
                Try 20 times over 60 seconds before forcing the program to exit with code 3.

        Once an access token has been aquired, write the releveant data to its file and return the access token.

        Returns None if the refresh token is missing from its file or the file is missing entirely
        Returns the access token on success

        SIDE EFFECT: Can cause program to exit with error code 3!
        """

        try:
            tokens = TokenHandler.load_credentials_from_file()
            needs_oauth = False
        except FileNotFoundError:
            needs_oauth = True

        if needs_oauth or tokens.get('refresh_token', None) is None:
            return None

        # Access token is not yet expired
        if not TokenHandler.is_token_expired():
            return tokens['access_token']

        print('Access token expired, acquiring new token...')

        data = {
            'auth_key':      '***REMOVED***',
            'refresh_token': tokens['refresh_token']
        }

        for attempt in range(21):
            access_token_request = requests.post(TokenHandler.token_url, json=data)

            if access_token_request.status_code == 200:
                break

            elif access_token_request.status_code != 200 and attempt < 20:
                print(f'Failed to get access token from Heartbroken servers (attempt {attempt}/10)')
                time.sleep(3)

            else:
                print('FATAL: Something went wrong while getting a Spotify access token from the Heartbroken servers:')
                print(f'HTTP {access_token_request.status_code}')
                sys.exit(3)

        access_token_dict = access_token_request.json()
        access_token_dict['refresh_token'] = tokens['refresh_token']
        TokenHandler.save_credentials_to_file(access_token_dict)

        return access_token_dict['access_token']

    # ========
    @staticmethod
    def save_credentials_to_file(access_token_dict) -> dict:
        """
        Write the access token, expiry time info, and refresh token to the credentials file, then return them.
        """

        access_token_dict['expires_at'] = time.time() + int(access_token_dict['expires_in'])
        access_token_json = str(access_token_dict).replace("'", '"')

        with open(TokenHandler.credentials_file_name, 'w') as f:
            print(access_token_json, file=f)

        return access_token_dict

    # ========
    @staticmethod
    def load_credentials_from_file() -> dict:
        """
        Load the access token, expiry time info, and refresh token from the credentials file, then return them.
        """

        with open(TokenHandler.credentials_file_name) as f:
            return json.loads(f.read())


class OAuthManager (StaticClass):
    """
    Static class containing methods for handling Spotify OAuth
    """

    auth_url = "https://accounts.spotify.com/authorize"

    # ========
    @staticmethod
    def do_spotify_oauth() -> typing.Union[dict, None]:
        """
        Run Spotify OAuth flow. Runs a temporary web server in a separate thread to receive the callback.
        """

        auth_code_params = {
            "response_type": "code",
            "client_id":     TokenHandler.client_id,
            "scope":         TokenHandler.auth_scope,
            "redirect_uri":  TokenHandler.redirect_uri
        }

        auth_queue = multiprocessing.Queue()
        server_process = multiprocessing.Process(target=OAuthManager._run_server, args=(auth_queue,))
        server_process.start()

        webbrowser.open_new(f"{OAuthManager.auth_url}?{urllib.parse.urlencode(auth_code_params)}")

        attempt_count = 0
        while attempt_count < 200:
            try:
                auth_code = auth_queue.get(timeout=.5)
                break
            except queue.Empty:
                pass

        # We waited 100 seconds and got no requests
        if attempt_count >= 200:
            print('\n\nTimed out while waiting for OAuth callback from Spotify. Exiting.\n\n')

            # Clean up after OAuth server
            auth_queue.close()
            server_process.terminate()

            return None

        # At this point we have an authorization code we can use to get the
        # refresh token and a fresh access token
        data = {
            'grant_type'    : 'authorization_code',
            'oauth_code'    : auth_code,          # The auth code we got from the OAuth flow
            'refresh_token' : None,               # We don't have this yet; becomes null in json
            'auth_key'      : '***REMOVED***'  # Internal auth key
        }

        refresh_token_request = requests.post(TokenHandler.token_url, json=data)
        if refresh_token_request.status_code != 200:
            return None

        # Clean up after OAuth server
        auth_queue.close()
        server_process.terminate()

        refresh_token_dict = refresh_token_request.json()
        TokenHandler.save_credentials_to_file(refresh_token_dict)

        return refresh_token_dict

    # ========
    @staticmethod
    def build_oauth_session(client_id: str, access_token: str) -> requests_oauthlib.OAuth2Session:
        """
        Helper function that's a simple wrapper for creating a new requests_oauthlib.OAuth2Session
        """
        return requests_oauthlib.OAuth2Session(client_id=client_id,
                                               token={"access_token": access_token})

    # ========
    @staticmethod
    def _run_server(auth_queue: multiprocessing.Queue) -> typing.NoReturn:
        """
        Waits for a connection, gets the access token token from the request, then tosses it in the auth queue.
        This thread should be laid to rest once the queue has an item.
        """

        httpd = _QueuingHTTPServer(('127.0.0.1', 8551), _AuthRequestHandler, auth_queue)
        httpd.serve_forever()


class _QueuingHTTPServer(http.server.HTTPServer):
    """
    Simple extension of http.server.HTTPServer that allows passing in a queue
    """

    def __init__(self, server_address, RequestHandlerClass,
                 queue: multiprocessing.Queue, bind_and_activate=True):
        http.server.HTTPServer.__init__(self, server_address, RequestHandlerClass, bind_and_activate)
        self.auth_queue = queue


class _AuthRequestHandler(http.server.BaseHTTPRequestHandler):
    """
    Handles receipt of the OAuth token and returns an HTML page that will either exit on its own or instruct the user to do so.
    """

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()

        # Depending on the browser this may or may not auto-close the window after auth has finished.
        self.wfile.write(bytes('<!DOCTYPE html><html><head><script>window.close();</script><style>*{background-color:black;color:white;font-size:24pt;}</head><body>Authentication complete. You may close this page.</body></html>', 'utf8'))

        self.server.auth_queue.put(self.path.strip('/callback?code='))

    # ========
    def log_message(self, format, *args) -> None:
        # Mutes default console logging of requests
        pass
