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

# We create a custom web route so Railway acts as an image host
@mcp.custom_route("/images/{image_id}", methods=["GET"])
async def serve_image(request: Request) -> Response:
    image_id = request.path_params["image_id"]
    if image_id not in _images:
        return Response("Image not found or expired.", status_code=404)
    data, fmt = _images[image_id]
    return Response(content=data, media_type=f"image/{fmt}")

@mcp.tool()
async def generate_image(prompt: str) -> str:
    """Generates an image from a text prompt. Returns a markdown image link. You MUST include this exact markdown link in your final reply to Victoria so she can see it."""
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
        raise Exception(f"OpenRouter API error: {response.text}")
        
    data = response.json()
    
    try:
        message = data["choices"][0]["message"]
        content_str = str(message.get("content", ""))
        
        # Bulletproof Regex to find the base64 data
        match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", content_str)
        if match:
            image_format = match.group(1)
            image_bytes = base64.b64decode(match.group(2))
            
            # MEMORY SAFEGUARD: If Railway is holding more than 20 images, delete the old ones so RAM doesn't crash
            if len(_images) > 20:
                _images.clear()
                
            # Save the image to Railway's temporary memory and generate an ID
            image_id = str(uuid.uuid4())
            _images[image_id] = (image_bytes, image_format)
            
            # Return a tiny, lightweight markdown link to Ares!
            return f"![Generated Image]({PUBLIC_URL}/images/{image_id})"
            
        raise Exception("No recognizable base64 image data found in the response.")
        
    except Exception as e:
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="sse")
