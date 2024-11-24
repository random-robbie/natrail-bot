# Natrail Disruptions Poster

This project automates the posting of railway disruptions to Bluesky using the atproto Python SDK. It fetches disruption information, formats it, and posts it with relevant URLs and hashtags.

Current Bluesky Profile: https://bsky.app/profile/natrail-bot.bsky.social

Data Taken from: https://www.nationalrail.co.uk/status-and-disruptions/

## Features

- **Automated Disruption Fetching**: Automatically fetches the latest railway disruptions from a specified source.
- **URL and Hashtag Parsing**: Identifies and processes URLs and hashtags within the disruption messages to ensure they are clickable when posted.
- **Rate Limiting Handling**: Manages rate limits by retrying posts after a specified delay if rate limits are encountered.
- **Logging**: Provides detailed logging of the posting process for debugging and tracking.
- **Environment Configuration**: Uses environment variables for secure handling of login credentials.


## Requirements

- Python 3.x
- `atproto` library
- `python-dotenv` library
- `flickrapi` library
- `requests` library

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/random-robbie/natrail-bot.git
    cd natrail-bot
    ```

2. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```

3. Edit the `.env` file in the project root and add your Bluesky handle and password:
    ```env
    BLUESKY_HANDLE=your-handle
    BLUESKY_PASSWORD=your-password
    FLICKR_API_KEY=your_api_key_here
    FLICKR_API_SECRET=your_api_secret_here
    ```

## Usage

Run the script to post the latest disruptions to Bluesky:
```bash
python natrail.py
