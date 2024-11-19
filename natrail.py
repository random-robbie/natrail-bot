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
import os
import json
import random

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


def modify_string(text):
    # Find the first capital letter after 'between' and 'and'
    text = re.sub(r'(between[^A-Z]*)([A-Z])', r'\1#\2', text)
    # Find the first capital letter after 'and'
    text = re.sub(r'(and[^A-Z]*)([A-Z])', r'\1#\2', text)
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

def fetch_disruptions():
    """Scrape the disruptions from National Rail page."""
    try:
    
        # Define the User Agent
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'}

        # Send a request to fetch the HTML content of the page
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception if there's an error
        logger.info("Successfully fetched data from National Rail website.")

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

def post_to_bluesky(message: str, facets: List[models.AppBskyRichtextFacet.Main] = None):
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

            # Send the post to Bluesky
            response = client.send_post(
                text=message,
                facets=facets  # Add the facets for URL embedding
            )

            
            # Log the full response to inspect the structure
            logger.debug(f"Response from Bluesky: {response}")
            
            # Check if the response contains the necessary fields ('did' or 'uri')
            if 'did' not in str(response) or 'uri' not in str(response):
                logger.error(f"Failed to post message. Response missing expected fields: {response}")
                exit()
                break

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
    disruptions = fetch_disruptions()  # Fetch disruptions from wherever it's sourced

    if disruptions:
        for description, link in disruptions:
            # Add hashtags
            description = modify_string(description)
            # Format the message to include the disruption description and the URL
            message = f"{description}\n\n{link}"
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
            post_to_bluesky(message, facets=facets)
            
            # Wait between posts to avoid spamming
            time.sleep(20)

        # Save the updated seen disruptions to the file to track posted disruptions
        save_seen_disruptions(seen_disruptions)

    else:
        logger.info("No new disruptions to post.")

if __name__ == "__main__":
    main()
