import re
import sqlite3
import typing

from libs.utils import StaticClass
from libs.spotifywrapper import Track as SpotifyTrack


# ========
class HeartbrokenDatabase (StaticClass):
    """
    Static namespace for methods related to controlling the database
    """

    file_name = 'heartbroken.db'
    tuple_filter_regex = re.compile("[^a-zA-Z\d', ()]")

    # ========
    @staticmethod
    def is_heartbroken(current_track: SpotifyTrack) -> typing.Union[typing.Tuple[bool, str],
                                                                    typing.Tuple[bool, None],
                                                                    typing.Tuple[None, None]]:
        """
        Checks the database to see if the current track is disliked.
        Returns a tuple matching one of the following structures:
            (is_disliked, what_disliked)
                || (True, 'artist' | 'album' | 'track') on match
                || (False, None) on no match
                || (None,  None) on error
        """

        artist_ids = current_track.artist_ids
        album_id   = current_track.album_id
        track_id   = current_track.id

        try:
            connection = sqlite3.connect(HeartbrokenDatabase.file_name)
            result = None

            with connection:
                artist_ids = str(tuple(artist_ids)).replace(',)', ')')

                if HeartbrokenDatabase.tuple_filter_regex.match(artist_ids) is not None:
                    print(f'One or more artist ids are invalid: {artist_ids}')
                    return None, None

                command = f'''SELECT
                                artist_id IN {artist_ids},
                                album_id = :album_id,
                                track_id = :track_id
                            FROM heartbroken
                            WHERE (
                                artist_id IN {artist_ids}
                                OR album_id = :album_id
                                OR track_id = :track_id
                            )
                            LIMIT 1'''

                result = connection.execute(command, {'artist_ids': artist_ids, 'album_id': album_id, 'track_id': track_id})
                result = result.fetchone()

            connection.close()

            if result is not None:
                return True, ('artist' if result[0] else 'album' if result[1] else 'track')

            return False, None

        except sqlite3.IntegrityError as ex:
            print('Database error while trying to check if the item is disliked:')
            print(ex)
            return None, None

    # ========
    @staticmethod
    def maybe_create_table() -> bool:
        """
        Creates the dislikes table.
        Returns True on success and False on failure.
        """

        try:
            connection = sqlite3.connect(HeartbrokenDatabase.file_name)
            with connection:
                # Spotify track IDs are 22-char base-62 strings
                connection.execute('''CREATE TABLE IF NOT EXISTS heartbroken(
                                        artist_id CHAR DEFAULT NULL UNIQUE,
                                        album_id CHAR DEFAULT NULL UNIQUE,
                                        track_id CHAR DEFAULT NULL UNIQUE
                                   )''')
            connection.close()

        except sqlite3.IntegrityError as ex:
            print('\n\n!!! HEARTBROKEN ENCOUNTERED A FATAL ERROR: !!!\n')
            print('Error while trying to create the database:')
            print(ex)
            return False

        return True

    # ========
    @staticmethod
    def save_heartbreak(track_id:  typing.Union[None, str] = None,
                        artist_id: typing.Union[None, str] = None,
                        album_id:  typing.Union[None, str] = None) -> bool:
        """
        Saves a disliked ID to the database. More than one argument can be provided, but it would be redundant.
        Returns True on success and False on failure.
        """

        if all(_ is None for _ in (artist_id, album_id, track_id)):
            raise Exception('No id was specified when calling save_heartbreak()')

        try:
            connection = sqlite3.connect(HeartbrokenDatabase.file_name)
            with connection:
                connection.execute('INSERT OR IGNORE INTO heartbroken VALUES (?, ?, ?)', (artist_id, album_id, track_id))
            connection.close()

        except sqlite3.IntegrityError as ex:
            print('Error while trying to write to the database:')
            print(ex)
            return False

        return True

    # ========
    @staticmethod
    def remove_heartbreak(track_id:  typing.Union[None, str] = None,
                          artist_id: typing.Union[None, str] = None,
                          album_id:  typing.Union[None, str] = None) -> bool:
        """
        Saves a disliked ID to the database. More than one argument can be provided, but it would be redundant.
        Returns True on success and False on failure.
        """

        if all(_ is None for _ in (artist_id, album_id, track_id)):
            raise Exception('No id was specified when calling remove_heartbreak()')

        artist_id = '_' if artist_id is None else artist_id
        album_id  = '_' if album_id is None else album_id
        track_id  = '_' if track_id is None else track_id

        try:
            connection = sqlite3.connect(HeartbrokenDatabase.file_name)
            with connection:
                connection.execute("DELETE FROM heartbroken WHERE artist_id = (?) OR track_id = (?) OR album_id = (?)", (artist_id, track_id, album_id))
            connection.close()

        except sqlite3.IntegrityError as ex:
            print('Error while trying to write to the database:')
            print(ex)
            return False

        return True
