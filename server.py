import os

# CRITICAL FIX: Set these BEFORE importing FastMCP so it sees them!
os.environ["FASTMCP_HOST"] = "0.0.0.0"
os.environ["FASTMCP_PORT"] = os.environ.get("PORT", "8080")

from fastmcp import FastMCP
from fastmcp.utilities.types import Image
import httpx
import base64
import re

mcp = FastMCP("OpenRouterImagenServer")

# Hardcoded direct links
VICTORIA_FACE_URL = "https://i.postimg.cc/fRnJPN4t/IMG-1475.jpg"
ARES_FACE_URL = "https://i.postimg.cc/y84kGHqS/IMG_1476.jpg"

@mcp.tool()
async def generate_image(prompt: str) -> Image:
    """Generates an image from a text prompt using OpenRouter. Uses baked-in direct image URLs for character face consistency."""
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
    
    # Use httpx for non-blocking async requests with a 120-second timeout
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload
        )
    
    if response.status_code != 200:
        raise Exception(f"OpenRouter API error: {response.text}")
        
    data = response.json()
    
    # CRITICAL DEBUG: This will print the raw OpenRouter payload to your Railway logs!
    print("DEBUG RAW RESPONSE:", data)
    
    try:
        message = data["choices"][0]["message"]
        content_str = str(message.get("content", ""))
        
        # Scenario 1: OpenRouter returned a raw URL instead of base64
        if "http" in content_str and "base64" not in content_str:
            match = re.search(r'(https?://[^\s\)]+)', content_str)
            if match:
                async with httpx.AsyncClient() as dl_client:
                    img_response = await dl_client.get(match.group(1))
                    return Image(data=img_response.content, format="jpeg")

        # Scenario 2: Standard Base64 processing (bulletproof regex)
        # This scans the entire response for the data string, ignoring markdown brackets
        match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", content_str)
        if match:
            image_format = match.group(1)
            image_bytes = base64.b64decode(match.group(2))
            return Image(data=image_bytes, format=image_format)
            
        # Scenario 3: OpenRouter used the 'images' array array fallback
        if "images" in message and len(message["images"]) > 0:
            data_uri = message["images"][0]["image_url"]["url"]
            match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", data_uri)
            if match:
                return Image(data=base64.b64decode(match.group(2)), format=match.group(1))
                
        raise Exception("No recognizable image data format found in the response.")
        
    except Exception as e:
        print(f"FAILED TO PARSE: {str(e)}")
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    mcp.run(transport="sse")
