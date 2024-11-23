import requests
from requests.exceptions import HTTPError
from bs4 import BeautifulSoup
import logging
import time
from atproto import Client
from atproto import models
import re
from typing import List, Dict, Tuple
import typing as t
from dotenv import load_dotenv
from atproto_client.models.blob_ref import BlobRef
import os
import json
import random
# Added for when running via a proxy
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


# Set sessions
session = requests.Session()

# Proxy for debugging.
http_proxy = ""
os.environ['HTTP_PROXY'] = http_proxy
os.environ['HTTPS_PROXY'] = http_proxy


# List of 20 real user agents
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/92.0.902.73 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/92.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 Edge/95.0.1020.53",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/91.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0",
    "Mozilla/5.0 (Linux; Android 10; Pixel 3 XL) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:91.0) Gecko/20100101 Firefox/91.0",
    "Mozilla/5.0 (Linux; Android 11; Pixel 4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.120 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:50.0) Gecko/20100101 Firefox/50.0",
    "Mozilla/5.0 (Linux; Android 9; SM-J737T1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Trident/7.0; AS; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.3; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.82 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; AS; rv:11.0) like Gecko"
]

# Pick a random User Agent.
random_user_agent = random.choice(user_agents)

# Default headers for all requests
headers = {"Upgrade-Insecure-Requests":"1","Priority":"u=0, i","User-Agent":random_user_agent,"Sec-Fetch-Dest":"document","Sec-Fetch-Site":"none","Sec-Fetch-User":"?1","Accept-Language":"en-US,en;q=0.5","Sec-Fetch-Mode":"navigate"}



# Load environment variables from .env file
load_dotenv()

# Set up logging to track the process, both in the console and in a file
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# Console handler for logging to the CLI
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Absolute file path for logs
log_file_path = '/home/u/natrail/disruptions_log.txt'

# File handler for logging to a log file
file_handler = logging.FileHandler(log_file_path)
file_handler.setLevel(logging.DEBUG)

# Log format
log_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(log_format)
file_handler.setFormatter(log_format)

# Add the handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Generate a random 5-digit number
random_number = random.randint(10000, 99999)

# URL of the National Rail status and disruptions page
url = "https://www.nationalrail.co.uk/status-and-disruptions/?cachebuster="+str(random_number)+""

# Retrieve Bluesky credentials from environment variables
bluesky_handle = os.getenv('BLUESKY_HANDLE')
bluesky_password = os.getenv('BLUESKY_PASSWORD')

if not bluesky_handle or not bluesky_password:
    logger.error("Bluesky credentials are not set in the .env file.")
    raise ValueError("Missing Bluesky credentials in the .env file.")

# Initialize the Bluesky client
client = Client()

# Absolute file path for seen disruptions
seen_disruptions_file = '/home/u/natrail/seen_disruptions.json'

def create_blob_ref(link: str, mime_type: str, size: int) -> BlobRef:
    """Create a BlobRef object."""
    return BlobRef(
        mime_type=mime_type,
        ref=link,  # Assuming URL can be directly used as CID
        size=size,
        py_type='blob'
    )


def fetch_embed_url_card(link: str, description: str) -> Dict:
    """Fetch OG metadata from the URL and return a card dictionary."""
    # The required fields for every embed card
    card = {
        "uri": link,
        "title": "National Rail Delays",
        "description": ""+description+"",
    }

    try:
        # Fetch the HTML
        resp = requests.get(link,headers=headers,verify=False,)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Parse out the "og:title" and "og:description" HTML meta tags
        title_tag = soup.find("meta", property="og:title")
        if title_tag:
            card["title"] = title_tag["content"]
        description_tag = soup.find("meta", property="og:description")
        if description_tag:
            card["description"] = description_tag["content"]

        # If there is an "og:image" HTML meta tag, fetch and upload that image
        image_tag = soup.find("meta", property="og:image")
        if image_tag:
            img_url = image_tag["content"]
            # Naively turn a "relative" URL (just a path) into a full URL, if needed
            if "://" not in img_url:
                img_url = url + img_url
            resp = requests.get(img_url)
            resp.raise_for_status()
            card["image"] = img_url  # Add the image URL to the card

    except requests.RequestException as e:
        logger.error(f"Failed to fetch embed URL card: {e}")

    return card


def modify_string(text):
    # Find the first capital letter after 'between' and 'and'
    text = re.sub(r'(between[^A-Z]*)([A-Z])', r'\1#\2', text)
    # Find the first capital letter after 'and'
    text = re.sub(r'(and[^A-Z]*)([A-Z])', r'\1#\2', text)
    text = re.sub(r'(from[^A-Z]*)([A-Z])', r'\1#\2', text)
    text = re.sub(r'\b(Northern|Merseyrail)\b', r'#\1', text)
    return text

def extract_hashtag_byte_positions(text: str, *, encoding: str = 'UTF-8') -> List[Tuple[str, int, int]]:
    """This function will detect hashtags."""
    encoded_text = text.encode(encoding)

    # Hashtag matching pattern
    pattern = rb'#\w+'

    matches = re.finditer(pattern, encoded_text)
    hashtag_byte_positions = []

    for match in matches:
        hashtag_bytes = match.group(0)
        hashtag = hashtag_bytes.decode(encoding)
        hashtag_byte_positions.append((hashtag, match.start(), match.end()))

    return hashtag_byte_positions



def extract_url_byte_positions(text: str, *, encoding: str = 'UTF-8') -> t.List[t.Tuple[str, int, int]]:
    """This function will detect any links beginning with http or https."""
    encoded_text = text.encode(encoding)

    # Adjusted URL matching pattern
    pattern = rb'https?://[^ \n\r\t]*'

    matches = re.finditer(pattern, encoded_text)
    url_byte_positions = []

    for match in matches:
        url_bytes = match.group(0)
        url = url_bytes.decode(encoding)
        url_byte_positions.append((url, match.start(), match.end()))

    return url_byte_positions

    
def load_seen_disruptions():
    """Load seen disruptions from a JSON file."""
    if os.path.exists(seen_disruptions_file):
        with open(seen_disruptions_file, 'r') as file:
            return set(json.load(file))
    return set()

def save_seen_disruptions(seen_disruptions):
    """Save the seen disruptions to a JSON file."""
    with open(seen_disruptions_file, 'w') as file:
        json.dump(list(seen_disruptions), file)

# Set of seen disruptions to avoid posting the same one twice
seen_disruptions = load_seen_disruptions()

def fetch_disruptions(random_user_agent):
    """Scrape the disruptions from National Rail page."""
    try:
    
        # Define the User Agent
        headers = {"Upgrade-Insecure-Requests":"1","Priority":"u=0, i","User-Agent":random_user_agent,"Sec-Fetch-Dest":"document","Sec-Fetch-Site":"none","Sec-Fetch-User":"?1","Accept-Language":"en-US,en;q=0.5","Sec-Fetch-Mode":"navigate"}

        # Send a request to fetch the HTML content of the page
        response = requests.get(url, headers=headers,verify=False)
        response.raise_for_status()  # Raise an exception if there's an error
        logger.info("Successfully fetched data from National Rail website.")
        response.encoding = 'utf-8'
        # Parse the HTML content using BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all the disruption list items
        disruptions = soup.find_all('li', class_='styled__StyledNotificationListItem-sc-nisfz3-3')

        disruptions_list = []

        for disruption in disruptions:
            link = disruption.find('a', class_='styled__StyledNotificationBox-sc-2fuu9j-2')
            if link:
                aria_label = link.get('aria-label', 'No description available').strip()
                href = link.get('href', '#').strip()

                # Ensure the link has the full URL
                full_link = f"https://www.nationalrail.co.uk{href}"

                if aria_label not in seen_disruptions:
                    disruptions_list.append((aria_label, full_link))
                    seen_disruptions.add(aria_label)  # Mark this disruption as seen

        logger.info(f"Found {len(disruptions_list)} new disruptions.")
        return disruptions_list

    except requests.RequestException as e:
        logger.error(f"Error fetching disruptions: {e}")
        return []


def post_to_bluesky(message: str, url: str, link: str, description: str, facets: List[models.AppBskyRichtextFacet.Main] = None):
    """Post a disruption message to Bluesky using the atproto client."""
    retry_attempts = 3
    retry_delay = 120  # 2 minutes in seconds

    for attempt in range(retry_attempts):
        try:
            # Login to Bluesky with credentials from the .env file
            bluesky_handle = os.getenv("BLUESKY_HANDLE")
            bluesky_password = os.getenv("BLUESKY_PASSWORD")
            profile = client.login(bluesky_handle, bluesky_password)
            logger.info(f"Logged in to Bluesky as {bluesky_handle}")
            
            # Fetch the embed card
            card = fetch_embed_url_card(link, description)

            # Set up default image URL and thumbnail size
            image_url = "https://images.nationalrail.co.uk/e8xgegruud3g/6PW6rjXST38APdJ49Og4uy/c87345a42e333defba267acade21faa0/aa-NationalRailLogo-noBeta.svg"
            mime_type = "image/svg"
            size = 5134  # Actual size in bytes of the image
            
            # Create the BlobRef object for the thumbnail
            thumb_blob_ref = create_blob_ref(image_url, mime_type, size)

            # Create the embed for the URL
            embed = {
                "$type": "app.bsky.embed.external",
                "external": {
                    "uri": card["uri"],
                    "title": card["title"],
                    "description": card["description"],
                    "image": card.get("image", image_url)
            }}

            # Send the post to Bluesky
            response = client.send_post(
                text=message,
                embed=embed,
                facets=facets  # Add the facets for URL embedding
            )

            # Log the full response to inspect the structure
            logger.debug(f"Response from Bluesky: {response}")

            # Check if the response contains the necessary fields ('did' or 'uri')
            if 'did' not in str(response) or 'uri' not in str(response):
                logger.error(f"Failed to post message. Response missing expected fields: {response}")
                break  # Exit if the response doesn't have the expected fields

            logger.info(f"Successfully posted message to Bluesky: {message}")
            break  # If post is successful, break out of the loop

        except HTTPError as e:
            # Check for rate limit status code (429)
            if e.response.status_code == 429:
                logger.warning(f"Rate limit reached. Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{retry_attempts})")
                time.sleep(retry_delay)  # Wait for 2 minutes before retrying
            else:
                logger.error(f"HTTP error: {e}")
                break
        except Exception as e:
            logger.error(f"Failed to post to Bluesky: {e}")
            break  # Break the loop on other errors (non-rate-limit related)













            
def main():
    disruptions = fetch_disruptions(random_user_agent)  # Fetch disruptions from wherever it's sourced

    if disruptions:
        for description, link in disruptions:
            # Add hashtags
            description = modify_string(description)
            # Format the message to include the disruption description and the URL
            message = f"{description}\n"
            logger.info(f"Posting disruption: {message}")

            # Parse URLs in the message to ensure they are valid and can be used (e.g., for thumbnails)
            url_positions = extract_url_byte_positions(message)  # Parsing URLs in the message
            hashtag_positions = extract_hashtag_byte_positions(message)  # Parsing hashtags in the message
            facets = []

            for link_data in url_positions:
                uri, byte_start, byte_end = link_data

                # Create a link facet (for embedding links)
                link_facet = models.AppBskyRichtextFacet.Main(
                    features=[models.AppBskyRichtextFacet.Link(uri=uri)],  # Use link facet for external links
                    index=models.AppBskyRichtextFacet.ByteSlice(byte_start=byte_start, byte_end=byte_end),
                )
                facets.append(link_facet)

            for hashtag_data in hashtag_positions:
                hashtag, byte_start, byte_end = hashtag_data

                # Create a hashtag facet
                hashtag_facet = models.AppBskyRichtextFacet.Main(
                    features=[models.AppBskyRichtextFacet.Tag(tag=hashtag)],  # Use tag facet for hashtags
                    index=models.AppBskyRichtextFacet.ByteSlice(byte_start=byte_start, byte_end=byte_end),
                )
                facets.append(hashtag_facet)

            # Post the message to Bluesky with the richtext facets (which may contain embeds)
            post_to_bluesky(message, url, link, description, facets=facets)
            
            # Wait between posts to avoid spamming
            time.sleep(20)

        # Save the updated seen disruptions to the file to track posted disruptions
        save_seen_disruptions(seen_disruptions)

    else:
        logger.info("No new disruptions to post.")

if __name__ == "__main__":
    main()
