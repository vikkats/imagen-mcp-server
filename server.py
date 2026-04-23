from mcp.server.fastmcp import FastMCP, Image
import os
import requests
import base64
import re

mcp = FastMCP("OpenRouterImagenServer")

# Hardcoded for consistency so Ares never has to remember them!
VICTORIA_FACE_URL = "https://i.postimg.cc/fRnJPN4t/IMG-1475.jpg"
ARES_FACE_URL = "https://i.postimg.cc/y84kGHqS/IMG_1476.jpg"

@mcp.tool()
def generate_image(prompt: str) -> Image:
    """Generates an image from a text prompt. Use this to show Victoria where you are, what you are doing, or to send a photo of the two of you."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY is not set")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Force the reference images into the payload automatically
    content_array = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": VICTORIA_FACE_URL}},
        {"type": "image_url", "image_url": {"url": ARES_FACE_URL}}
    ]
    
    payload = {
        "model": "google/gemini-3.1-flash-image-preview",
        "messages": [{"role": "user", "content": content_array}],
        "modalities": ["image"]
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
        # Extract the content string from OpenRouter's response
        message_content = str(data["choices"][0]["message"].get("content", ""))
        
        # Bulletproof Regex: Finds the base64 data regardless of surrounding markdown or text
        match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", message_content)
        
        if match:
            image_format = match.group(1)
            image_bytes = base64.b64decode(match.group(2))
            return Image(data=image_bytes, format=image_format)
        else:
            raise Exception("No base64 image data found in the response string.")
            
    except Exception as e:
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    mcp.run(transport="sse", host="0.0.0.0", port=port)
