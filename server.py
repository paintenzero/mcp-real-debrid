from dotenv import load_dotenv
import os
from mcp.server.fastmcp import FastMCP
from httpx import HTTPStatusError
from real_debrid import RealDebrid, RDTorrent, RDTorrentInfo, RDAddMagnet


load_dotenv()

rd_token = os.environ["RD_TOKEN"]
if not rd_token:
    raise ValueError("RD_TOKEN environment variable is not set.")

mcp = FastMCP("Read-Debrid")
rd = RealDebrid(token=rd_token)


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
    Returns the torrents.

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
    Returns details of a specific torrent.

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
def add_magnet_link(magnet_link: str) -> RDAddMagnet:
    """
    Adds a magnet link to Real-Debrid.

    Parameters:
        magnet_link (str): Magnet link to add.

    Returns:
        RDAddMagnet: Response from Real-Debrid API.
    """
    try:
        response = rd.add_magnet(magnet_link)
        return response
    except HTTPStatusError as e:
        if e.response.status_code == 400:
            return "Invalid magnet link."
        else:
            return f"Error adding magnet link: {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@mcp.tool()
def delete_torrent(torrent_id: str) -> str:
    """
    Deletes a torrent.

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
