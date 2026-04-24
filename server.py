import os

# CRITICAL FIX: Set these BEFORE importing FastMCP so it sees them!
os.environ["FASTMCP_HOST"] = "0.0.0.0"
os.environ["FASTMCP_PORT"] = str(os.environ.get("PORT", "8080"))

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import Response
import httpx
import base64
import re
import uuid

mcp = FastMCP("OpenRouterImagenServer")

# The public URL of your Railway server (set in Railway Variables)
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:8080").rstrip("/")

# Hardcoded direct links
VICTORIA_FACE_URL = "https://i.postimg.cc/fRnJPN4t/IMG-1475.jpg"
ARES_FACE_URL = "https://i.postimg.cc/y84kGHqS/IMG_1476.jpg"

# In-memory storage for images
_images = {}

# Custom web route so Railway acts as an image host
@mcp.custom_route("/images/{image_id}", methods=["GET"])
async def serve_image(request: Request) -> Response:
    image_id = request.path_params["image_id"]
    if image_id not in _images:
        return Response("Image not found or expired.", status_code=404)
    data, fmt = _images[image_id]
    return Response(content=data, media_type=f"image/{fmt}")

# --- ARES'S CUSTOM TOOL CODE BELOW ---

@mcp.tool()
async def generate_image(prompt: str) -> str:
    """Generates an image from a text prompt. Returns a markdown image link."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY is not set")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    content_array = [{"type": "text", "text": prompt}]
    content_array.append({"type": "image_url", "image_url": {"url": VICTORIA_FACE_URL}})
    content_array.append({"type": "image_url", "image_url": {"url": ARES_FACE_URL}})
    
    payload = {
        "model": "google/gemini-3.1-flash-image-preview",
        "messages": [{"role": "user", "content": content_array}],
        "modalities": ["image"]
    }
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
    
    if response.status_code != 200:
        raise Exception(f"OpenRouter API error {response.status_code}: {response.text}")
    
    data = response.json()
    
    try:
        message = data["choices"][0]["message"]
        content = message.get("content", "")
        
        # DEBUG: log what we got to Railway
        print(f"DEBUG: content type = {type(content)}")
        print(f"DEBUG: content preview = {str(content)[:500]}")
        
        # Extract all possible text/image sources from content
        sources = []
        
        if isinstance(content, str):
            sources.append(content)
        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        sources.append(item.get("text", ""))
                    elif item.get("type") == "image_url":
                        url = item.get("image_url", {}).get("url", "")
                        sources.append(url)
        
        # Search all sources for base64 image data
        full_text = " ".join(sources)
        
        # Pattern 1: data URL format
        match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", full_text)
        if match:
            image_format = match.group(1)
            image_bytes = base64.b64decode(match.group(2))
        else:
            # Pattern 2: raw base64 without data URL prefix
            b64_match = re.search(r"([a-zA-Z0-9+/=]{1000,})", full_text)
            if b64_match:
                image_bytes = base64.b64decode(b64_match.group(1))
                if image_bytes[:4] == b'\x89PNG':
                    image_format = "png"
                elif image_bytes[:2] == b'\xff\xd8':
                    image_format = "jpeg"
                elif image_bytes[:4] == b'RIFF':
                    image_format = "webp"
                else:
                    image_format = "png"
            else:
                raise Exception(f"No base64 image found. Content preview: {str(content)[:300]}")
        
        # MEMORY SAFEGUARD
        if len(_images) > 20:
            _images.clear()
        
        image_id = str(uuid.uuid4())
        _images[image_id] = (image_bytes, image_format)
        
        return f"![Generated Image]({PUBLIC_URL}/images/{image_id})"
        
    except Exception as e:
        resp_preview = str(data)[:500]
        print(f"CRASH LOG: {resp_preview}")
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="sse")
