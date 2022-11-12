from argparse import ArgumentError
import typing

from libs.tokenhandler import TokenHandler
from libs.database import HeartbrokenDatabase
from libs.spotifywrapper import SpotifyWrapper


# ========
def skip_if_heartbroken(spotify: SpotifyWrapper) -> typing.Union[None, bool]:
    """
    Takes a Spotify wrapper instance and checks inside a loop if tracks are disliked.
    That is, if multiple tracks in a row are disliked, all will be skipped with this
    function.

    NECESSARY SIDE EFFECT: This also updates the current track
    """

    spotify.update_current_track()

    current_track  = spotify.current_track
    previous_track = spotify.previous_track

    if current_track is None:
        return None

    if previous_track is not None and current_track.id == previous_track.id:
        return False

    tracks_skipped = set()
    while True:
        is_heartbroken, what_heartbroken = HeartbrokenDatabase.is_heartbroken(spotify.current_track)

        spotify.current_track.track_heartbroken  = what_heartbroken == 'track'
        spotify.current_track.album_heartbroken  = what_heartbroken == 'album'
        spotify.current_track.artist_heartbroken = what_heartbroken == 'artist'

        if not is_heartbroken:
            break

        print('Skipping disliked {}: {}'.format(
            what_heartbroken,
            {'track':  current_track.name,
             'album':  current_track.album,
             'artist': current_track.artists
            }[what_heartbroken]
        ))

        tracks_skipped.add(current_track.id)

        next_track = spotify.skip_current_track()
        if next_track == -1:
            print(f'Something went wrong while skipping disliked {what_heartbroken}')
            return None

        elif next_track is None:
            return None

        # Prevent infinite loops
        if spotify.current_track.id in tracks_skipped:
            print('Current track has been skipped previously in the current queue; stopping playback to prevent an infinite loop')
            spotify.stop_playback()
            return None

    return is_heartbroken

# ========
def handle_heartbreak(track:  bool = False, artist: bool = False, album:  bool = False) -> None:
    """
    Writes dislike information to the database. Arguments determine what is disliked and are mutually exclusive.
    NECESSARY SIDE EFFECT: This also updates the current track
    """

    arg_true_count = len([arg for arg in (track, artist, album) if arg])
    if   arg_true_count > 1:  raise ArgumentError('Only one argument to handle_heartbreak() can be True')
    elif arg_true_count == 0: raise ArgumentError('One argument to handle_heartbreak() must be True')

    current_track = SpotifyWrapper.get_current_track_static(TokenHandler.client_id)

    item_type = "track" if track else "artist" if artist else "album"
    if current_track is None:
        print(f'Cannot dislike {item_type}, nothing is playing!')
        return

    track_id   = current_track.id         if track  else None
    artist_ids = current_track.artist_ids if artist else []
    album_id   = current_track.album_id   if album  else None

    if artist:
        db_success = True
        for artist_id in artist_ids:
            db_success = db_success and HeartbrokenDatabase.save_heartbreak(artist_id=artist_id)

    elif album:
        db_success = HeartbrokenDatabase.save_heartbreak(album_id=album_id)
    else:
        db_success = HeartbrokenDatabase.save_heartbreak(track_id=track_id)

    if not db_success:
        print(f'Sorry, something went wrong while disliking the {item_type}')
        return

    print(f'Sucessfully disliked {item_type}, skipping...')

    api_success = SpotifyWrapper.skip_current_track_static(TokenHandler.client_id)
    if not api_success:
        print(f'Sorry, something went wrong while skipping the current {item_type}')

# ========
def handle_clear_heartbreak(track: bool = False, artist: bool = False, album:  bool = False) -> None:
    """
    Deletes dislikes from the database. Arguments determine what is disliked and are mutually exclusive.
    NECESSARY SIDE EFFECT: This also updates the current track
    """

    arg_true_count = len([arg for arg in (track, artist, album) if arg])
    if   arg_true_count > 1:  raise ArgumentError('Only one argument to handle_clear_heartbreak() can be True')
    elif arg_true_count == 0: raise ArgumentError('One argument to handle_clear_heartbreak() must be True')

    current_track = SpotifyWrapper.get_current_track_static(TokenHandler.client_id)

    track_id   = current_track.id         if track  else None
    artist_ids = current_track.artist_ids if artist else []
    album_id   = current_track.album_id   if album  else None

    item_type = "track" if track else "artist(s)" if artist else "album"

    if current_track is None:
        print(f'Cannot un-dislike {item_type}, nothing is playing!')
        return

    if artist:
        db_success = True
        for artist_id in artist_ids:
            db_success = db_success and HeartbrokenDatabase.remove_heartbreak(artist_id=artist_id)

    else:
        db_success = HeartbrokenDatabase.remove_heartbreak(track_id=track_id,
                                                           album_id=album_id)

    if db_success:
        print(f'Sucessfully un-disliked {item_type}')
    else:
        print(f'Sorry, something went wrong while un-disliking the {item_type}')
