import re
import json
import os
from typing import List, Union, Generator, Iterator
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from youtube_transcript_api import YouTubeTranscriptApi
import logging

class Tools:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_video_id(self, url: str) -> Union[str, None]:
        """
        Extract video ID from a YouTube URL.

        :param url: The YouTube URL.
        :return: The video ID if found, otherwise None.
        """
        pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
        match = re.search(pattern, url)
        return match.group(1) if match else None

    def get_comments(self, youtube, video_id: str) -> List[str]:
        """
        Fetch comments for a YouTube video.

        :param youtube: The YouTube API client.
        :param video_id: The video ID.
        :return: A list of comments.
        """
        comments = []

        try:
            request = youtube.commentThreads().list(
                part="snippet,replies",
                videoId=video_id,
                textFormat="plainText",
                maxResults=100
            )

            while request:
                response = request.execute()
                for item in response['items']:
                    topLevelComment = item['snippet']['topLevelComment']['snippet']['textDisplay']
                    comments.append(topLevelComment)

                    if 'replies' in item:
                        for reply in item['replies']['comments']:
                            replyText = reply['snippet']['textDisplay']
                            comments.append("    - " + replyText)

                if 'nextPageToken' in response:
                    request = youtube.commentThreads().list_next(
                        previous_request=request, previous_response=response)
                else:
                    request = None

        except HttpError as e:
            self.logger.error(f"Failed to fetch comments: {e}")

        return comments

    def parse_duration(self, duration: str) -> int:
        """
        Parse the duration of a YouTube video in ISO 8601 format.

        :param duration: The duration string in ISO 8601 format.
        :return: The duration in minutes.
        """
        duration_regex = re.compile(r'PT(\d+H)?(\d+M)?(\d+S)?')
        match = duration_regex.match(duration)
        if match:
            hours = int(match.group(1)[:-1]) if match.group(1) else 0
            minutes = int(match.group(2)[:-1]) if match.group(2) else 0
            seconds = int(match.group(3)[:-1]) if match.group(3) else 0
            return hours * 60 + minutes + seconds // 60
        else:
            return 0

    def extract_video_metadata(self, url: str, options: dict) -> str:
        """
        Extract metadata from a YouTube video.

        :param url: The YouTube URL.
        :param options: A dictionary of options for extracting metadata.
        :return: A JSON string containing the extracted metadata.
        """
        api_key = os.getenv("YOUTUBE_API_KEY")
        if not api_key:
            return json.dumps({"error": "YOUTUBE_API_KEY not found in environment variable"})

        video_id = self.get_video_id(url)
        if not video_id:
            return json.dumps({"error": "Invalid YouTube URL"})

        try:
            youtube = build("youtube", "v3", developerKey=api_key)

            video_response = youtube.videos().list(
                id=video_id, part="contentDetails,snippet").execute()

            duration_iso = video_response["items"][0]["contentDetails"]["duration"]
            duration_minutes = self.parse_duration(duration_iso)

            metadata = {
                'id': video_response['items'][0]['id'],
                'title': video_response['items'][0]['snippet']['title'],
                'channel': video_response['items'][0]['snippet']['channelTitle'],
                'published_at': video_response['items'][0]['snippet']['publishedAt'],
            }

            try:
                transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=[options.get('lang', 'en')])
                transcript_text = " ".join([item["text"] for item in transcript_list])
                transcript_text = transcript_text.replace("\n", " ")
            except Exception as e:
                transcript_text = f"Transcript not available in the selected language ({options.get('lang', 'en')}). ({e})"

            comments = []
            if options.get('comments', False):
                comments = self.get_comments(youtube, video_id)

            output = {
                "transcript": transcript_text,
                "duration": duration_minutes,
                "comments": comments,
                "metadata": metadata
            }

            return json.dumps(output, indent=2)
        except HttpError as e:
            return json.dumps({"error": f"Failed to access YouTube API. Please check your YOUTUBE_API_KEY and ensure it is valid: {e}"})