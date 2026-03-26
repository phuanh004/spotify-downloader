import spotapi


class Spotify:
    """
    Wrapper that makes SpotAPI behave like Spotipy.
    Only implements commonly used methods but can be expanded.

    Vendored from spotipyfree 1.0.7 with search fix for spotapi >= 1.2.x
    (spotapi.Search was removed; replaced with spotapi.Public().song_search).
    """

    def __init__(self, username=None, password=None):
        self.user_auth = False
        self.use_cache_file = False
        self.no_cache = True
        self._next = None
        if username is not None:
            self.user_auth = True
            raise Exception("Login not yet implemented")

    @staticmethod
    def init(*args, **kwargs):
        return

    def urlToId(self, url):
        return url.split("/")[-1].split("?")[0]

    def isUrl(self, test):
        return (
            test.startswith("spotify:")
            or test.startswith("https://open.spotify.com/")
            or test.startswith("open.spotify")
        )

    def _getArtists(self, artists):
        for artist in artists:
            artist["name"] = artist["profile"]["name"]
            artist["external_urls"] = {"spotify": artist["uri"]}
            artist["genres"] = [""]
            artist.pop("profile", None)
            artist.pop("discography", None)
            artist.pop("visuals", None)
            artist.pop("relatedContent", None)
        return artists

    def _formatAlbum(self, items, total, limit, offset, end):
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "next": False,
            "previous": offset - limit if offset - limit >= 0 else None,
        }

    def _formatTracks(self, tracks):
        allTracks = []
        for track in tracks:
            track = track["track"]
            trackId = track["uri"].removeprefix("spotify:track:")
            url = "https://open.spotify.com/track/" + trackId
            meta = {
                "name": track["name"],
                "id": trackId,
                "song_id": trackId,
                "url": url,
                "external_urls": {"spotify": url},
                "duration_ms": track["duration"]["totalMilliseconds"],
                "disc_number": track["discNumber"],
                "track_number": track["trackNumber"],
                "artists": self._getArtists(track["artists"]["items"]),
                "explicit": track["contentRating"]["label"] == "EXPLICIT",
            }
            allTracks.append(meta)
        return allTracks

    def next(self, *args, **kwargs):
        return self._next(*args, **kwargs)

    def album(self, albumId, *args, **kwargs):
        if self.isUrl(albumId):
            albumId = self.urlToId(albumId)

        album = spotapi.PublicAlbum(albumId).get_album_info()["data"]["albumUnion"]
        artists = self._getArtists(album["artists"]["items"])
        tracks = self._formatTracks(album["tracksV2"]["items"])
        album["id"] = album["uri"].removeprefix("spotify:album:")
        album["artists"] = artists
        album["tracks"] = {"items": tracks}
        album["total_tracks"] = len(album["tracks"]["items"])
        album["images"] = album["coverArt"]["sources"]
        album["release_date"] = album["date"]["isoString"].split("T")[0]
        album["album_type"] = "album"
        album["copyrights"] = [{"text": "", "type": ""}]
        album["genres"] = [""]
        return album

    def album_tracks(self, albumId, limit=-1, offset=0, *args, **kwargs):
        if self.isUrl(albumId):
            albumId = self.urlToId(albumId)

        allTracks = []
        for tracks in spotapi.PublicAlbum(albumId).paginate_album():
            allTracks.extend(tracks)
        allTracks = self._formatTracks(allTracks)

        total = len(allTracks)
        if limit == -1:
            limit = total
        end = offset + limit
        return self._formatAlbum(allTracks, total, limit, offset, end)

    def artist(self, artistId, *args, **kwargs):
        if self.isUrl(artistId):
            artistId = self.urlToId(artistId)

        artist = spotapi.Artist().get_artist(artistId)["data"]["artistUnion"]
        artist["name"] = artist["profile"]["name"]
        artist["genres"] = [""]
        return artist

    def artist_albums(
        self, artistId, limit=-1, offset=0, include_groups="album", *args, **kwargs
    ):
        allowed = set(include_groups.split(","))
        discog = spotapi.Artist().get_artist(artistId)["data"]["artistUnion"][
            "discography"
        ]

        merged = []
        for group_name, group_data in discog.items():
            if group_name in allowed:
                if isinstance(group_data, dict) and "items" in group_data:
                    merged.extend(group_data["items"])

        total = len(merged)
        if limit == -1:
            limit = total
        end = offset + limit
        return self._formatAlbum(merged, total, limit, offset, end)

    def playlist(self, playlistId, limit=-1, offset=0, *args, **kwargs):
        playlist = spotapi.PublicPlaylist(playlistId).get_playlist_info()["data"][
            "playlistV2"
        ]
        playlist["owner"] = playlist["ownerV2"]["data"]
        playlist.pop("ownerV2", None)
        playlist["owner"]["display_name"] = playlist["owner"]["name"]
        playlist["external_urls"] = {}
        playlist["external_urls"]["spotify"] = playlist["owner"]["uri"]
        try:
            playlist["images"] = playlist["images"]["items"][-1]["sources"]
        except Exception:
            playlist["images"] = []
        return playlist

    def playlist_items(self, playlistId, limit=50, offset=0, *args, **kwargs):
        if self.isUrl(playlistId):
            playlistId = self.urlToId(playlistId)

        allTracks = []
        for chunk in spotapi.PublicPlaylist(playlistId).paginate_playlist():
            for track in chunk["items"]:
                try:
                    trackV3 = track["itemV3"]["data"]
                    trackV2 = track["itemV2"]["data"]
                    trackType = "None"
                    if trackV2["mediaType"] == "AUDIO":
                        trackType = "track"

                    meta = {
                        "track": {
                            "name": trackV3["identityTrait"]["name"],
                            "id": trackV3["uri"].removeprefix("spotify:track:"),
                            "duration_ms": trackV2["trackDuration"][
                                "totalMilliseconds"
                            ],
                            "description": trackV3["identityTrait"]["description"],
                            "artists": trackV3["identityTrait"]["contributors"][
                                "items"
                            ],
                            "album": {},
                            "type": trackType,
                            "external_urls": {
                                "spotify": "https://open.spotify.com/track/"
                                + trackV2["uri"].removeprefix("spotify:track:")
                            },
                            "is_local": False,
                            "disc_number": trackV2["discNumber"],
                            "track_number": trackV2["trackNumber"],
                            "explicit": trackV2["contentRating"]["label"]
                            == "EXPLICIT",
                            "external_ids": {"isrc": ""},
                        }
                    }
                    allTracks.append(meta)
                except Exception:
                    pass

        total = len(allTracks)
        if limit == -1:
            limit = total
        end = offset + limit
        return self._formatAlbum(allTracks, total, limit, offset, end)

    def track(self, trackId, *args, **kwargs):
        if self.isUrl(trackId):
            trackId = self.urlToId(trackId)

        track = spotapi.Song().get_track_info(trackId)["data"]["trackUnion"]
        artists = track["firstArtist"]["items"]
        artists.extend(track["otherArtists"]["items"])
        artists = self._getArtists(artists)
        meta = {
            "name": track["name"],
            "id": track["id"],
            "disc_number": track["trackNumber"],
            "track_number": track["trackNumber"],
            "duration_ms": track["duration"]["totalMilliseconds"],
            "artists": artists,
            "album": track["albumOfTrack"],
            "explicit": track["contentRating"]["label"] == "EXPLICIT",
            "external_urls": {"spotify": track["uri"]},
            "popularity": 10,
            "type": "track",
            "external_ids": {"isrc": ""},
        }
        return meta

    def search(self, query, limit=50, offset=0, type="track", *args, **kwargs):
        p = spotapi.Public()
        all_items = []
        for page in p.song_search(query):
            if isinstance(page, list):
                all_items.extend(page)
            elif isinstance(page, dict):
                all_items.append(page)

        tracks = []
        for item in all_items:
            data = item.get("item", {}).get("data", {})
            if not data:
                continue
            track_id = data.get("id", "")
            url = "https://open.spotify.com/track/" + track_id
            artists = self._getArtists(data.get("artists", {}).get("items", []))
            track = {
                "name": data.get("name", ""),
                "id": track_id,
                "external_urls": {"spotify": url},
                "duration_ms": data.get("duration", {}).get("totalMilliseconds", 0),
                "artists": artists,
                "album": data.get("albumOfTrack", {}),
                "explicit": data.get("contentRating", {}).get("label", "")
                == "EXPLICIT",
                "type": "track",
                "external_ids": {"isrc": ""},
            }
            tracks.append(track)

        total = len(tracks)
        if limit == -1:
            limit = total
        end = offset + limit
        sliced = tracks[offset:end]

        self._next = lambda: self.search(
            query, limit=limit, offset=end, type=type
        )
        return {
            "tracks": {
                "items": sliced,
                "total": total,
                "limit": limit,
                "offset": offset,
            }
        }

    def current_user_saved_tracks(self, limit=-1, offset=0, *args, **kwargs):
        self._next = lambda: self.current_user_saved_tracks(
            limit=limit, offset=offset + limit
        )
        return

    def user_playlists(self, limit=-1, offset=0, *args, **kwargs):
        self._next = lambda: self.user_playlists(
            limit=limit, offset=offset + limit
        )
        return

    def current_user_playlists(self, limit=-1, offset=0, *args, **kwargs):
        self._next = lambda: self.current_user_playlists(
            limit=limit, offset=offset + limit
        )
        return

    def current_user_followed_artists(self, limit=-1, offset=0, *args, **kwargs):
        self._next = lambda: self.current_user_followed_artists(
            limit=limit, offset=offset + limit
        )
        return
