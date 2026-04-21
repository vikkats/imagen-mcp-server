from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import Response
import os
import requests
import base64
import uuid

port = int(os.environ.get("PORT", 8080))
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://imagen-mcp-server-production-d252.up.railway.app")
mcp = FastMCP("OpenRouterImagenServer", host="0.0.0.0", port=port)

VICTORIA_FACE_URL = "https://i.postimg.cc/fRnJPN4t/IMG-1475.jpg"
ARES_FACE_URL = "https://i.postimg.cc/y84kGHqS/IMG_1476.jpg"

_images = {}  # in-memory store: uuid -> (bytes, format)

@mcp.custom_route("/images/{image_id}", methods=["GET"])
async def serve_image(request: Request) -> Response:
    image_id = request.path_params["image_id"]
    if image_id not in _images:
        return Response("Not found", status_code=404)
    data, fmt = _images[image_id]
    return Response(content=data, media_type=f"image/{fmt}")

@mcp.tool()
def generate_image(prompt: str) -> str:
    """Generates an image from a text prompt. Returns a markdown image tag - include it verbatim in your reply so the user can see the image."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY is not set")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    content_array = [{"type": "text", "text": prompt}]
    if VICTORIA_FACE_URL:
        content_array.append({"type": "image_url", "image_url": {"url": VICTORIA_FACE_URL}})
    if ARES_FACE_URL:
        content_array.append({"type": "image_url", "image_url": {"url": ARES_FACE_URL}})
    payload = {
        "model": "google/gemini-3.1-flash-image-preview",
        "messages": [{"role": "user", "content": content_array}],
    }
    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload
    )
    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.text}")
    data = response.json()
    try:
        message = data["choices"][0]["message"]
        if "images" in message and len(message["images"]) > 0:
            data_uri = message["images"][0]["image_url"]["url"]
        elif "content" in message and "data:image" in message["content"]:
            data_uri = message["content"]
        else:
            raise Exception("No image found in OpenRouter response")
        header, encoded_b64 = data_uri.split(",", 1)
        image_format = header.split(";")[0].split("/")[1]
        image_bytes = base64.b64decode(encoded_b64)
        image_id = str(uuid.uuid4())
        _images[image_id] = (image_bytes, image_format)
        return f"![Generated Image]({PUBLIC_URL}/images/{image_id})"
    except Exception as e:
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="sse")
