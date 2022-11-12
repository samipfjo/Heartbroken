from libs.utils import StaticClass


class SpotifyAPI (StaticClass):
    """
    Static class that stores constants related to interacting with the Spotify API
    """

    REQUEST_INTERVAL_SECONDS: int = 1
    REQUEST_DELAY_COMPENSATION_MS: int = 500
