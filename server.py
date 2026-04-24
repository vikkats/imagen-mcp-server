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
        
        # DEBUG: log full message structure
        print(f"DEBUG: message keys = {list(message.keys())}")
        
        # NEW: Check message.images first (OpenRouter format)
        images = message.get("images", [])
        if images and len(images) > 0:
            img_data = images[0]
            # Handle both formats: {image_url: {url: "data:..."}} and {url: "data:..."}
            img_url = img_data.get("image_url", {}).get("url", "") if isinstance(img_data, dict) else ""
            if not img_url and isinstance(img_data, dict):
                img_url = img_data.get("url", "")
            
            if img_url.startswith("data:image"):
                match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", img_url)
                if match:
                    image_format = match.group(1)
                    image_bytes = base64.b64decode(match.group(2))
                else:
                    raise Exception(f"Malformed data URL: {img_url[:100]}")
            else:
                raise Exception(f"Unexpected image URL format: {img_url[:100]}")
        
        # FALLBACK: Check message.content (old format or text-only)
        else:
            content = message.get("content", "")
            print(f"DEBUG: content type = {type(content)}, value = {content}")
            
            if not content:
                raise Exception("No images array and no content in response")
            
            # Try to find base64 in content string
            content_str = str(content)
            match = re.search(r"data:image/([^;]+);base64,([a-zA-Z0-9+/=]+)", content_str)
            if match:
                image_format = match.group(1)
                image_bytes = base64.b64decode(match.group(2))
            else:
                # Try raw base64
                b64_match = re.search(r"([a-zA-Z0-9+/=]{1000,})", content_str)
                if b64_match:
                    image_bytes = base64.b64decode(b64_match.group(1))
                    if image_bytes[:4] == b'\x89PNG':
                        image_format = "png"
                    elif image_bytes[:2] == b'\xff\xd8':
                        image_format = "jpeg"
                    else:
                        image_format = "png"
                else:
                    raise Exception(f"No image data found in content: {content_str[:300]}")
        
        # MEMORY SAFEGUARD
        if len(_images) > 20:
            _images.clear()
        
        image_id = str(uuid.uuid4())
        _images[image_id] = (image_bytes, image_format)
        
        return f"![Generated Image]({PUBLIC_URL}/images/{image_id})"
        except Exception as e:
        resp_preview = str(data)[:500]
        raise Exception(f"Failed to process OpenRouter response: {str(e)}. Response preview: {resp_preview}")
