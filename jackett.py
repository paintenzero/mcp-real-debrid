import xml.etree.ElementTree as ET
from typing import List, Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ValidationError, field_validator
import httpx

# --- Pydantic Models ---

# Define namespaces for easier parsing with ElementTree
NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "torznab": "http://torznab.com/schemas/2015/feed",
}


class Enclosure(BaseModel):
    """Represents the <enclosure> element data."""

    url: str
    length: int
    type: str


class SearchItem(BaseModel):
    """Represents an <item> in the Torznab RSS feed."""

    title: str
    guid: str
    indexer_id: str  # From <jackettindexer id="...">
    indexer_name: str  # From <jackettindexer>...</jackettindexer> text
    item_type: str = Field(alias="type")  # Renamed from 'type' as it's a keyword
    comments: Optional[str] = None
    pub_date: datetime = Field(alias="pubDate")
    size: int
    grabs: int
    description: Optional[str] = None
    link: str  # The download link
    categories: List[str] = Field(default_factory=list)
    enclosure: Optional[Enclosure] = None
    torznab_attrs: Dict[str, str] = Field(default_factory=dict)

    # Pydantic validator to handle potential parsing issues or type conversions if needed
    # Example: Ensure size and grabs are non-negative (optional validation)
    @field_validator("size", "grabs", mode="before")
    @classmethod
    def check_non_negative(cls, value):
        v = int(value)
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v

    @field_validator("pub_date", mode="before")
    @classmethod
    def parse_pub_date(cls, value):
        if isinstance(value, str):
            try:
                # Use dateutil.parser for robust parsing of various date formats
                return datetime.strptime(value, "%a, %d %b %Y %H:%M:%S %z")
            except ValueError as e:
                raise ValueError(f"Invalid date format: {value}") from e
        return value  # Already a datetime object


class JackettAuth(httpx.Auth):
    """Custom authentication class for Jackett API using an API key."""

    def __init__(self, apikey):
        self.apikey = apikey

    def auth_flow(self, request):
        # Send the request, with a custom `X-Authentication` header.
        request.url = request.url.copy_add_param("apikey", self.apikey)
        yield request


class JackettAPI:
    """Class to interact with the Jackett API using Torznab format."""

    def __init__(self, base_url: str, apikey: str):
        self.base_url = base_url
        self.apikey = apikey
        auth = JackettAuth(apikey)
        self.client = httpx.Client(base_url=base_url, auth=auth)

    def search(self, query: str) -> List[SearchItem]:
        """
        Perform a search using the Torznab API.

        :param query: The search query string.
        :return: The response from the API.
        """
        response = self.client.get(
            "/api", params={"t": "search", "q": query}, timeout=120
        )
        print(f"{response.text}")
        items = self.parse_torznab_xml(response.text)
        items.sort(key=lambda x: x.torznab_attrs["seeders"], reverse=True)
        return items

    def search_show(
        self, name: str, season: Optional[int] = None, quality: str = "1080p"
    ) -> List[SearchItem]:
        """
        Perform a search for a tv show using the Torznab API.

        :param query: The search query string.
        :return: The response from the API.
        """
        params = {"t": "tvsearch", "q": f"{name} {quality}"}
        if season is not None and season > 0:
            params["season"] = season
        response = self.client.get("/api", params=params, timeout=120)
        items = self.parse_torznab_xml(response.text)
        items.sort(key=lambda x: x.torznab_attrs["seeders"], reverse=True)
        return items

    def search_movie(self, name: str, quality: str = "1080p") -> List[SearchItem]:
        """
        Perform a search for a movie using the Torznab API.

        :param query: The search query string.
        :return: The response from the API.
        """
        params = {"t": "movie", "q": f"{name} {quality}"}
        response = self.client.get("/api", params=params, timeout=120)
        items = self.parse_torznab_xml(response.text)
        items.sort(key=lambda x: x.torznab_attrs["seeders"], reverse=True)
        return items

    @staticmethod
    def parse_torznab_xml(xml_string: str) -> List[SearchItem]:
        """
        Parses a Torznab RSS XML string and returns a list of SearchItem objects.
        """
        items = []
        try:
            root = ET.fromstring(xml_string)
            channel = root.find("channel")
            if channel is None:
                print("Warning: <channel> tag not found in XML.")
                return items

            for item_elem in channel.findall("item"):
                data = {}

                # --- Extract standard elements ---
                data["title"] = item_elem.findtext("title")
                data["guid"] = item_elem.findtext("guid")
                data["type"] = item_elem.findtext(
                    "type"
                )  # Will be mapped to item_type via alias
                data["comments"] = item_elem.findtext("comments")
                data["pubDate"] = item_elem.findtext(
                    "pubDate"
                )  # Will be parsed by validator
                data["size"] = item_elem.findtext("size")
                data["grabs"] = item_elem.findtext("grabs")
                data["description"] = item_elem.findtext("description")
                data["link"] = item_elem.findtext("link")

                # --- Extract jackettindexer info ---
                indexer_elem = item_elem.find("jackettindexer")
                if indexer_elem is not None:
                    data["indexer_id"] = indexer_elem.get("id")
                    data["indexer_name"] = (
                        indexer_elem.text.strip() if indexer_elem.text else None
                    )
                else:
                    data["indexer_id"] = None
                    data["indexer_name"] = None

                # --- Extract categories (multiple possible) ---
                data["categories"] = [
                    cat.text for cat in item_elem.findall("category") if cat.text
                ]

                # --- Extract enclosure info ---
                enclosure_elem = item_elem.find("enclosure")
                if enclosure_elem is not None:
                    try:
                        enclosure_data = {
                            "url": enclosure_elem.get("url"),
                            "length": int(
                                enclosure_elem.get("length", 0)
                            ),  # Default to 0 if missing
                            "type": enclosure_elem.get("type"),
                        }
                        data["enclosure"] = Enclosure(**enclosure_data)
                    except (ValueError, TypeError, ValidationError) as e:
                        print(
                            f"Warning: Could not parse enclosure for item '{data.get('title')}': {e}"
                        )
                        data["enclosure"] = None
                else:
                    data["enclosure"] = None

                # --- Extract torznab:attr elements ---
                torznab_attributes = {}
                for attr_elem in item_elem.findall("torznab:attr", NAMESPACES):
                    name = attr_elem.get("name")
                    value = attr_elem.get("value")
                    if name and value is not None:  # Ensure both name and value exist
                        torznab_attributes[name] = value
                data["torznab_attrs"] = torznab_attributes

                # --- Create Pydantic model instance ---
                try:
                    # Filter out None values for fields that are not Optional in the model
                    # or handle them appropriately before creating the model instance.
                    # Pydantic v2 handles required fields better, but explicit checks can be clearer.
                    required_fields = {
                        "title",
                        "guid",
                        "type",
                        "pubDate",
                        "size",
                        "grabs",
                        "link",
                        "indexer_id",
                        "indexer_name",
                    }
                    missing_required = {
                        f for f in required_fields if data.get(f) is None
                    }
                    if missing_required:
                        print(
                            f"Warning: Skipping item due to missing required fields: {missing_required}. Item title: '{data.get('title')}'"
                        )
                        continue  # Skip this item if essential data is missing

                    search_item = SearchItem(**data)
                    items.append(search_item)
                except ValidationError as e:
                    print(
                        f"Warning: Validation failed for item '{data.get('title', 'N/A')}':\n{e}\nRaw data: {data}\n"
                    )
                except Exception as e:
                    print(
                        f"Warning: Unexpected error creating SearchItem for '{data.get('title', 'N/A')}': {e}\nRaw data: {data}\n"
                    )

        except ET.ParseError as e:
            print(f"Error parsing XML: {e}")
        except Exception as e:
            print(f"An unexpected error occurred during parsing: {e}")

        return items
