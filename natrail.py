import flickrapi
from groq import Groq
import httpx
import json
import logging
import os
import random
import re
import requests
import sqlite3
import time
import typing as t
from atproto import Client
from atproto import models
from atproto_client.models.blob_ref import BlobRef
from bs4 import BeautifulSoup
from datetime import datetime
from dotenv import load_dotenv
from requests.exceptions import HTTPError
from typing import List, Dict, Tuple
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


# Patterns for Og title etc
_META_PATTERN = re.compile(r'<meta property="og:.*?>')
_CONTENT_PATTERN = re.compile(r'<meta[^>]+content="([^"]+)"')



def extract_first_operator_link(url):
    # Send a GET request to the specified URL
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all <a> tags
        links = soup.find_all('a', href=True)
        
        # Filter links that contain '/travel-information/operators/'
        operator_links = [link['href'] for link in links if '/travel-information/operators/' in link['href']]
        
        # Check if any links were found
        if operator_links:
            # Get the first link and strip '/travel-information/operators/' from it
            first_link = operator_links[0].replace('/travel-information/operators/', '')
            first_link = first_link.replace('/','')
            logger.info(f"Operater Found: {first_link}")
            return first_link
        else:
            print("No links found containing '/travel-information/operators/'")
            return "Merseyrail"
    else:
        print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
        return "Merseyrail"




def search_random_image(link):
    # Get API key and secret from environment variables
    api_key = os.getenv('FLICKR_API_KEY')
    api_secret = os.getenv('FLICKR_API_SECRET')
    search_string = ''+extract_first_operator_link(link)+' Train photo'
    # Initialize the Flickr API
    flickr = flickrapi.FlickrAPI(api_key, api_secret, format='parsed-json')

    # Search for photos using the provided search string
    response = flickr.photos.search(text=search_string, per_page=10)  # Fetch 10 images

    # Extract photos from the response
    photos = response['photos']['photo']
    
    # Check if any photos were found
    if photos:
        # Choose a random photo from the list
        random_photo = random.choice(photos)
        # Construct the URL for the image
        image_url = f"https://live.staticflickr.com/{random_photo['server']}/{random_photo['id']}_{random_photo['secret']}.jpg"
        logger.info(f"Image URL: {image_url}")
        return image_url
    else:
        return None







# Initialize the SQLite database
def create_db():
    # Connect to SQLite database (or create it if it doesn't exist)
    conn = sqlite3.connect('disruptions.db')
    cursor = conn.cursor()

    # Create table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS disruptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        disruption TEXT NOT NULL,
        link TEXT NOT NULL,
        posted INTEGER DEFAULT 0,
        date TEXT NOT NULL
    )
    ''')

    # Commit and close
    conn.commit()
    conn.close()

def insert_disruption(description, link, date):
    """Inserts a new disruption into the database."""
    conn = sqlite3.connect('disruptions.db')
    cursor = conn.cursor()

    # Use INSERT OR IGNORE to ensure no duplicates are added based on the description and link
    cursor.execute('''
        INSERT OR IGNORE INTO disruptions (disruption, link, posted, date)
        VALUES (?, ?, 0, ?)
    ''', (description, link, date))

    conn.commit()
    conn.close()


def update_posted(link):
    conn = sqlite3.connect('disruptions.db')
    cursor = conn.cursor()

    # Update the 'posted' column to 1 where the disruption and link match
    cursor.execute('''
    UPDATE disruptions
    SET posted = 1
    WHERE link = ?
    ''', (link,))  # Ensure link is passed as a tuple

    conn.commit()
    conn.close()
    logger.debug(link)
    logger.info(f"Updated 'posted' to 1 for disruption with link: {link}")
    
    
# Function to fetch all unposted disruptions from the database
def get_unposted_disruptions():
    conn = sqlite3.connect('disruptions.db')
    cursor = conn.cursor()

    # Retrieve all disruptions where posted = 0
    cursor.execute('''
    SELECT disruption, link FROM disruptions WHERE posted = 0
    ''')

    # Fetch all the unposted disruptions
    unposted_disruptions = cursor.fetchall()

    conn.close()

    return unposted_disruptions


def fetch_disruptions(random_user_agent):
    """Scrape the disruptions from National Rail page and save to SQLite database."""
    try:
        # Define the User Agent
        headers = {
            "Upgrade-Insecure-Requests": "1",
            "Priority": "u=0, i",
            "User-Agent": random_user_agent,
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Accept-Language": "en-US,en;q=0.5",
            "Sec-Fetch-Mode": "navigate"
        }

        # Send a request to fetch the HTML content of the page
        response = requests.get(url, headers=headers, verify=False)
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

                # Get the current date for the disruption
                date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Save disruption to the database
                insert_disruption(aria_label, full_link, date)

                # Add the disruption to the list
                disruptions_list.append((aria_label, full_link, date))

        # Log the number of new disruptions
        logger.info(f"Found {len(disruptions_list)} new disruptions.")
        return disruptions_list

    except requests.RequestException as e:
        logger.error(f"Error fetching disruptions: {e}")
        return []


def _find_tag(og_tags: t.List[str], search_tag: str) -> t.Optional[str]:
    for tag in og_tags:
        if search_tag in tag:
            return tag

    return None


def _get_tag_content(tag: str) -> t.Optional[str]:
    match = _CONTENT_PATTERN.match(tag)
    if match:
        return match.group(1)

    return None


def _get_og_tag_value(og_tags: t.List[str], tag_name: str) -> t.Optional[str]:
    tag = _find_tag(og_tags, tag_name)
    if tag:
        return _get_tag_content(tag)

    return None


def get_og_tags(url: str) -> t.Tuple[t.Optional[str], t.Optional[str], t.Optional[str]]:
    response = httpx.get(url)
    response.raise_for_status()

    og_tags = _META_PATTERN.findall(response.text)

    og_image = _get_og_tag_value(og_tags, 'og:image')
    og_title = _get_og_tag_value(og_tags, 'og:title')
    og_description = _get_og_tag_value(og_tags, 'og:description')

    return og_image, og_title, og_description




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




def post_to_bluesky(message: str, url: str, link: str, linkz: str, description: str, facets: List[models.AppBskyRichtextFacet.Main] = None):
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
            img_url, title, descriptionx = get_og_tags(link)
            if title is None:
               title = "National Rail Disruptions"
            if descriptionx is None:
               descriptionx = description
            
            thumb_blob = None
            img_url = search_random_image(link)
            if img_url:
               # Download image from og:image url and upload it as a blob
               logger.debug(f"{img_url}")
               img_data = httpx.get(img_url).content
               thumb_blob = client.upload_blob(img_data).blob
            logger.debug(f"Posting to Bluesky with message: {message}")
            logger.debug(f"Link: {link}")
            logger.debug(f"Description: {description}")
            if facets:
               logger.debug(f"Facets: {facets}")
            # AppBskyEmbedExternal is the same as "link card" in the app
            embed_external = models.AppBskyEmbedExternal.Main(external=models.AppBskyEmbedExternal.External(title=title, description=descriptionx, uri=link, thumb=thumb_blob))
            response = client.send_post(text=message, embed=embed_external, facets=facets)
            # Log the full response to inspect the structure
            logger.debug(f"Response from Bluesky: {response}")

            # Check if the response contains the necessary fields ('did' or 'uri')
            if 'did' not in str(response) or 'uri' not in str(response):
                logger.error(f"Failed to post message. Response missing expected fields: {response}")
                break  # Exit if the response doesn't have the expected fields

            logger.info(f"Successfully posted message to Bluesky: {message}")
            # Mark the disruption as posted in the database
            update_posted(link)
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


def main_loop():
    while True:
        try:
            if not os.path.exists('disruptions.db'):
                create_db()  # Ensure the database and table are created if they don't exist
            
            fetch_disruptions(random_user_agent)
            # Fetch unposted disruptions from the database
            unposted_disruptions = get_unposted_disruptions()
            
            if unposted_disruptions:
                for description, link in unposted_disruptions:
                    try:
                        # Add hashtags and prepare the message
                        description = modify_string(description)
                        message = f"{description}\n"
                        logger.info(f"Posting disruption: {message}")
                        # Unaltered Link
                        linkz = link
                        
                        # Parse URLs and hashtags
                        url_positions = extract_url_byte_positions(message)
                        hashtag_positions = extract_hashtag_byte_positions(message)
                        facets = []
                        
                        for link_data in url_positions:
                            uri, byte_start, byte_end = link_data
                            link_facet = models.AppBskyRichtextFacet.Main(
                                features=[models.AppBskyRichtextFacet.Link(uri=uri)],
                                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=byte_start, byte_end=byte_end),
                            )
                            facets.append(link_facet)
                            
                        for hashtag_data in hashtag_positions:
                            hashtag, byte_start, byte_end = hashtag_data
                            hashtag_facet = models.AppBskyRichtextFacet.Main(
                                features=[models.AppBskyRichtextFacet.Tag(tag=hashtag)],
                                index=models.AppBskyRichtextFacet.ByteSlice(byte_start=byte_start, byte_end=byte_end),
                            )
                            facets.append(hashtag_facet)
                            
                        # Post the message to Bluesky with the richtext facets
                        post_to_bluesky(message, url, link, linkz, description, facets=facets)
                        time.sleep(120)  # Keep the 2-minute delay between posts
                        
                    except Exception as e:
                        logger.error(f"Error processing disruption: {e}")
                        continue  # Continue to next disruption if one fails
                        
            else:
                logger.info("No new disruptions to post.")
                
            logger.info("Sleeping for 20 minutes before next check...")
            time.sleep(1200)  # 20 minutes sleep between full runs
            
        except Exception as e:
            logger.error(f"Major error in main loop: {e}")
            logger.info("Sleeping for 20 minutes before retry...")
            time.sleep(1200)  # Sleep even if there's an error, then retry

if __name__ == "__main__":
    try:
        logger.info("Starting continuous monitoring...")
        main_loop()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
