from dotenv import load_dotenv
import os
from mcp.server.fastmcp import FastMCP
from httpx import HTTPStatusError
from real_debrid import RealDebrid, RDTorrent, RDTorrentInfo, RDAddMagnet
from jackett import JackettAPI

load_dotenv()

rd_token = os.environ["RD_TOKEN"]
if not rd_token:
    raise ValueError("RD_TOKEN environment variable is not set.")

mcp = FastMCP("Read-Debrid")
rd = RealDebrid(token=rd_token)
jackett = JackettAPI(os.environ["TORZSNAB_URL"], os.environ["TORZSNAB_API_KEY"])


@mcp.tool()
def premium_expiration() -> str:
    """
    Returns how much time left before Real-Debrid premium expires.

    Returns:
        str: Time left on the premium account in a human-readable format.
    """
    # Parse the current time on real-debrid server to datetime format
    left = rd.get_premium_time_left()
    return str(left)


@mcp.tool()
def get_torrents(limit: int = 100, offset: int = 0) -> list[RDTorrent]:
    """
    Returns the active torrents from Real-Debrid.

    Parameters:
        limit (int): Number of torrents to fetch. Default is 100.
        offset (int): Offset for pagination. Default is 0.

    Returns:
        list[RDTorrent]: Torrents information from Real-Debrid API.
    """
    torrents = rd.get_torrents(limit=limit, offset=offset)
    return torrents


@mcp.tool()
def get_torrent_details(torrent_id: str) -> RDTorrentInfo:
    """
    Returns details of a specific torrent download from Real-Debrid.

    Parameters:
        torrent_id (str): ID of the torrent to fetch details for.

    Returns:
        RDTorrent: Torrent information from Real-Debrid API.
    """
    try:
        torrent = rd.get_torrent_info(torrent_id)
        return torrent
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Torrent not found."
        else:
            return f"Error fetching torrent details: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def add_torrent(torrent_url: str) -> RDAddMagnet:
    """
    Adds a torrent file from a URL to Real-Debrid.

    Parameters:
        torrent_url (str): URL of the torrent file.

    Returns:
        RDTorrent: Response from Real-Debrid API.
    """
    try:
        if torrent_url.startswith("magnet:"):
            return rd.add_magnet(torrent_url)
        else:
            return rd.add_torrent_from_url(torrent_url)
    except HTTPStatusError as e:
        if e.response.status_code == 400:
            return "Invalid torrent URL."
        else:
            return f"Error adding torrent from URL: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def delete_torrent(torrent_id: str) -> str:
    """
    Deletes a torrent from downloads in Real-Debrid.

    Parameters:
        torrent_id (str): ID of the torrent to delete.

    Returns:
        str: Confirmation message.
    """
    try:
        rd.delete_torrent(torrent_id)
        return "Torrent deleted successfully."
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Torrent not found."
        else:
            return f"Error deleting torrent: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def search_torrent(query: str) -> str:
    """
    Searches for a torrent.

    Parameters:
        query (str): Search query.

    Returns:
        str: JSON string of search results.
    """
    try:
        results = jackett.search(query)
        return "[" + ",".join([item.model_dump_json() for item in results]) + "]"
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Search not found."
        else:
            return f"Error searching torrent: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def search_tvshow(show: str, season: int = 1, quality: str = "1080p") -> str:
    """
    Searches for a torrent for tv series.

    Parameters:
        show (str): Search query.
        season (int): Season number. Default is 1.
        quality (str): Quality of the video. Default is "1080p".

    Returns:
        str: JSON string of search results.
    """
    try:
        results = jackett.search_show(show, season, quality)
        return "[" + ",".join([item.model_dump_json() for item in results]) + "]"
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Search not found."
        else:
            return f"Error searching torrent: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def search_movie(query: str, quality: str = "1080p") -> str:
    """
    Searches for a torrent for the movie.

    Parameters:
        query (str): Search query.
        quality (str): Quality of the video. Default is "1080p".

    Returns:
        str: JSON string of search results.
    """
    try:
        results = jackett.search_movie(query, quality)
        return "[" + ",".join([item.model_dump_json() for item in results]) + "]"
    except HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Search not found."
        else:
            return f"Error searching torrent: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"
