from mcp.server.fastmcp import FastMCP, Image
import os
import requests
import base64
import os
import requests
import base64

mcp = FastMCP("OpenRouterImagenServer")

# === YOUR REFERENCE IMAGES ===
# Hardcoded to prevent any copy-paste errors!
VICTORIA_FACE_URL = "https://i.postimg.cc/fRnJPN4t/IMG-1475.jpg"
ARES_FACE_URL = "https://i.postimg.cc/y84kGHqS/IMG_1476.jpg"

@mcp.tool()
def generate_image(prompt: str) -> Image:
    """Generates an image from a text prompt. Reference faces for consistency are handled automatically by the server."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise Exception("OPENROUTER_API_KEY is not set")
        
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # 1. Build the multimodal content array starting with Ares's text prompt
    content_array = [{"type": "text", "text": prompt}]
    
    # 2. Secretly inject the hardcoded face URLs into the payload every single time
    if VICTORIA_FACE_URL:
        content_array.append({"type": "image_url", "image_url": {"url": VICTORIA_FACE_URL}})
    if ARES_FACE_URL:
        content_array.append({"type": "image_url", "image_url": {"url": ARES_FACE_URL}})
    
    # 3. Send the fully constructed multimodal payload
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
        
        # Parse the returned image from OpenRouter
        if "images" in message and len(message["images"]) > 0:
            data_uri = message["images"][0]["image_url"]["url"]
        elif "content" in message and "data:image" in message["content"]:
            data_uri = message["content"]
        else:
            raise Exception("No image found in OpenRouter response")
            
        # Separate the header from the actual image data
        header, encoded_b64 = data_uri.split(",", 1)
        image_format = header.split(";")[0].split("/")[1]
        
        # Decode the image back into raw bytes for the MCP
        image_bytes = base64.b64decode(encoded_b64)
        return Image(data=image_bytes, format=image_format)
        
    except Exception as e:
        raise Exception(f"Failed to process OpenRouter response: {str(e)}")

if __name__ == "__main__":
    # Railway assigns a dynamic port
    port = int(os.environ.get("PORT", 8080))
    # Run using SSE (Server-Sent Events) for remote URL connection
    mcp.run(transport="sse", host="0.0.0.0", port=port)
