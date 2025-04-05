import datetime
import logging
from typing import Optional
import httpx
from pydantic import BaseModel, ValidationError

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class RDAuth(httpx.Auth):
    def __init__(self, token):
        self.token = token

    def auth_flow(self, request):
        print("Authenticating...")
        # Send the request, with a custom `X-Authentication` header.
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


class RDHost(BaseModel):
    """Represents a host on Real-Debrid."""

    host: str  # Host main domain
    max_file_size: int  # Max split size possible


class RDAddMagnet(BaseModel):
    """Represents the response of the add magnet request."""

    id: str
    uri: str  # URL of the created ressource


class RDTorrent(BaseModel):
    """
    Represents a torrent on Real-Debrid.
    """

    id: str
    filename: str
    hash: str  # SHA1 Hash of the torrent
    bytes: int  # Size of selected files only
    host: str  # Host main domain
    split: int  # Split size of links
    progress: int  # Possible values: 0 to 100
    status: str  # Current status of the torrent
    added: str  # jsonDate
    links: list[str]
    ended: Optional[str] = None  # !! Only present when finished, jsonDate
    speed: Optional[int] = (
        None  # !! Only present in "downloading", "compressing", "uploading" status
    )
    seeders: Optional[int] = (
        None  # !! Only present in "downloading", "magnet_conversion" status
    )


class RDFileInTorrent(BaseModel):
    """
    Represents a file in a torrent on Real-Debrid.
    """

    id: int
    path: str  # Path to the file inside the torrent, starting with "/"
    bytes: int  # Size of the file
    selected: int  # 0 or 1


class RDTorrentInfo(BaseModel):
    """
    Represents detailed information about a torrent on Real-Debrid.
    This includes the torrent's files and links.
    """

    id: str
    filename: str
    original_filename: str  # Original name of the torrent
    hash: str  # SHA1 Hash of the torrent
    bytes: int  # Size of selected files only
    original_bytes: int  # Total size of the torrent
    host: str  # Host main domain
    split: int  # Split size of links
    progress: int  # Possible values: 0 to 100
    status: str  # Current status of the torrent
    added: str  # jsonDate
    files: list[RDFileInTorrent]  # List of files in the torrent
    links: list[str]
    ended: Optional[str] = None  # !! Only present when finished, jsonDate
    speed: Optional[int] = (
        None  # !! Only present in "downloading", "compressing", "uploading" status
    )
    seeders: Optional[int] = (
        None  # !! Only present in "downloading", "magnet_conversion" status
    )


class RealDebrid:
    """
    A class to interact with the Real-Debrid API.
    """

    def __init__(self, token: str):
        auth = RDAuth(token)
        self.client = httpx.Client(
            base_url="https://api.real-debrid.com/rest/1.0", auth=auth, timeout=10
        )

    def get_time(self) -> Optional[datetime.datetime]:
        """
        Returns the current date and time.

        Returns:
            str: Current date and time in Y-m-d H:i:s format.
        """
        response = self.client.get("/time")
        if response.status_code == 200:
            # Parse the current time on real-debrid server to datetime format
            server_time = datetime.datetime.strptime(response.text, "%Y-%m-%d %H:%M:%S")
            return server_time
        else:
            return None

    def get_user_info(self) -> dict:
        """
        Returns user information.

        Returns:
            dict: User information from Real-Debrid API.
        """
        response = self.client.get("/user")
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": f"Unable to fetch user information. Status code: {response.status_code}"
            }

    def get_premium_time_left(self) -> Optional[datetime.timedelta]:
        """
        Returns the premium expiration date.

        Returns:
            datetime: Premium expiration date as a datetime object.
        """
        user_info = self.get_user_info()
        if "expiration" in user_info:
            expiration_timestamp = user_info["expiration"]
            # Convert the timestamp in string format 2025-06-04T08:12:49.000Z to datetime
            expiration_date = datetime.datetime.strptime(
                expiration_timestamp, "%Y-%m-%dT%H:%M:%S.%fZ"
            )
            diff = expiration_date - self.get_time()
            return diff
        else:
            return None

    def get_torrents(self, limit: int = 100, offset: int = 0) -> list[RDTorrent]:
        """
        Returns the torrents.

        Returns:
            dict: Torrents information from Real-Debrid API.
        """
        url = f"/torrents?limit={limit}"
        if offset > 0:
            url += f"&offset={offset}"
        response = self.client.get(url)
        if response.status_code == 200:
            try:
                torrent_list = [RDTorrent(**item) for item in response.json()]
                return torrent_list
            except ValidationError as e:
                logger.error("Validation error: %s", e)
                return {"error": "Validation error occurred while parsing torrents."}
        else:
            return {
                "error": f"Unable to fetch torrents. Status code: {response.status_code}"
            }

    def delete_torrent(self, torrent_id: str):
        """
        Deletes a torrent by its ID.

        Args:
            id (str): The ID of the torrent to delete.

        Returns:
            dict: Response from the Real-Debrid API.
        """
        response = self.client.delete(f"/torrents/delete/{torrent_id}")
        if response.status_code > 299:
            raise httpx.HTTPStatusError(
                f"Failed to delete torrent. Status code: {response.status_code}",
                request=response.request,
                response=response,
            )

    def available_hosts(self) -> list[RDHost]:
        """
        Returns the available hosts.

        Returns:
            dict: Available hosts from Real-Debrid API.
        """
        response = self.client.get("/torrents/availableHosts")
        if response.status_code == 200:
            try:
                hosts_list = [RDHost(**item) for item in response.json()]
                return hosts_list
            except ValidationError as e:
                logger.error("Validation error: %s", e)
                raise ValueError("Validation error occurred while parsing hosts.")
        else:
            return httpx.HTTPStatusError(
                f"Unable to fetch available hosts. Status code: {response.status_code}",
                request=response.request,
                response=response,
            )

    def add_magnet(self, magnet_url: str) -> RDAddMagnet:
        """
        Adds a magnet link to Real-Debrid.

        Args:
            magnet_url (str): The magnet URL to add.

        Returns:
            RDAddMagnet: Response from the Real-Debrid API.
        """
        response = self.client.post("/torrents/addMagnet", data={"magnet": magnet_url})
        if response.status_code < 299:
            parsed = RDAddMagnet(**response.json())
            self.select_torrent_files(torrent_id=parsed.id, file_ids="all")
            return parsed
        else:
            raise httpx.HTTPStatusError(
                f"Failed to add magnet link. Status code: {response.status_code}",
                request=response.request,
                response=response,
            )

    def get_torrent_info(self, torrent_id: str) -> RDTorrentInfo:
        """
        Returns detailed information about a torrent.

        Parameters:
            torrent_id (str): ID of the torrent.

        Returns:
            RDTorrentInfo: Detailed information about the torrent.
        """
        response = self.client.get(f"/torrents/info/{torrent_id}")
        if response.status_code < 299:
            torrent_info = RDTorrentInfo(**response.json())
            return torrent_info
        else:
            raise httpx.HTTPStatusError(
                f"Failed to fetch torrent info. Status code: {response.status_code}",
                request=response.request,
                response=response,
            )

    def select_torrent_files(self, torrent_id: str, file_ids: str = "all"):
        """
        Selects files to download in a torrent.

        Parameters:
            torrent_id (str): ID of the torrent.
            file_ids (str): Comma-separated list of file IDs to select. Use "all" to select all files.
        """
        response = self.client.post(
            f"/torrents/selectFiles/{torrent_id}", data={"files": file_ids}
        )
        if response.status_code > 299:
            raise httpx.HTTPStatusError(
                f"Failed to select files for torrent {torrent_id}. Status code: {response.status_code}",
                request=response.request,
                response=response,
            )
