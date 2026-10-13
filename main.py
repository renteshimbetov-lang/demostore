import os
import sys
from dotenv import load_dotenv
import higgsfield_client
from higgsfield_client.exceptions import HiggsfieldClientError

# Load environment variables from .env.local
load_dotenv(".env.local")


def on_queue_update(status):
    status_name = status.__class__.__name__
    print(f"Status update: {status_name}")


def main():
    model = "bytedance/seedance-2.5/text-to-video"
    prompt = "A cinematic scene at sunset"

    arguments = {
        "prompt": prompt,
        "duration": 5,
        "resolution": "720p",
        "aspect_ratio": "16:9",
    }

    print(f"Submitting request to {model}...")
    try:
        result = higgsfield_client.subscribe(
            model,
            arguments=arguments,
            on_queue_update=on_queue_update,
        )
    except HiggsfieldClientError as e:
        print(f"Request failed with client error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Request failed with unexpected error: {e}")
        sys.exit(1)

    status = str(result.get("status", "")).lower()

    if status in ("failed", "error"):
        error_msg = result.get("error") or "Unknown error"
        print(f"Request failed: {error_msg}")
        sys.exit(1)
    elif status in ("canceled", "cancelled"):
        print("Request was canceled.")
        sys.exit(1)
    elif status in ("nsfw", "moderated"):
        print("Request was moderated (flagged content).")
        sys.exit(1)
    elif status == "completed" or not status:
        video_url = None
        if isinstance(result.get("video"), dict):
            video_url = result["video"].get("url")
        elif isinstance(result.get("video"), str):
            video_url = result["video"]
        elif result.get("videos") and isinstance(result["videos"], list):
            first = result["videos"][0]
            video_url = first.get("url") if isinstance(first, dict) else str(first)
        elif result.get("url"):
            video_url = result.get("url")

        if video_url:
            print(f"Generated Video URL: {video_url}")
            return video_url
        else:
            print(f"Completed but no video URL found in output: {result}")
            sys.exit(1)
    else:
        print(f"Request ended with unhandled status '{status}': {result}")
        sys.exit(1)


if __name__ == "__main__":
    main()
