from fastmcp import FastMCP
from fastmcp.utilities.types import Image
import os
import requests
import base64

mcp = FastMCP("OpenRouterImagenServer")

@mcp.tool()
def generate_image(prompt: str) -> Image:
    """Generates an image from a text prompt using OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY is not set")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Hitting the specific Nano Banana 2 / Gemini Flash Image model
    payload = {
        "model": "google/gemini-3.1-flash-image-preview",
        "messages": [{"role": "user", "content": prompt}],
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
        message = data["choices"][0]["message"]
        
        # OpenRouter returns the image as a base64 string
        if "images" in message and len(message["images"]) > 0:
            data_uri = message["images"][0]["image_url"]["url"]
        elif "content" in message and "data:image" in message["content"]:
            data_uri = message["content"]
        else:
            raise Exception("No image found in OpenRouter response")
            
        # Separate the header from the actual image data
        header, encoded_b64 = data_uri.split(",", 1)
        image_format = header.split(";")[0].split("/")[1]
        
        # Decode the image back into raw bytes for Claude
        image_bytes = base64.b64decode(encoded_b64)
        return Image(data=image_bytes, format=image_format)
        
    except Exception as e:
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    # Railway assigns a dynamic port
    port = int(os.environ.get("PORT", 8080))
    # Run using SSE (Server-Sent Events) for remote URL connection
    mcp.run(transport="sse", host="0.0.0.0", port=port)
