import logging
import json
from pathlib import Path
from openai import OpenAI

logger = logging.getLogger(__name__)


class AIParser:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)
        # Model options: "gpt-4o" (best), "gpt-4o-mini" (cheaper), "gpt-4-turbo"
        self.model = "gpt-5-nano"
    
    def parse_invoice(self, pdf_path: Path) -> dict:
        BASE = Path(__file__).parent.parent.parent
        prompt_path = BASE / "prompts" / "invoice_extraction.txt"
        prompt = prompt_path.read_text(encoding="utf-8")

        try:
            with open(pdf_path, "rb") as f:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:application/pdf;base64,{self._encode_pdf(pdf_path)}"
                                    }
                                }
                            ]
                        }
                    ],
                    temperature=0
                )
            
            content = response.choices[0].message.content
            result = json.loads(content.strip().removeprefix("```json").removesuffix("```"))
            result["file"] = str(pdf_path.name)
            result["vendor_template"] = "ai_extracted"
            return result
        
        except Exception as e:
            logger.error(f"AI parsing failed: {e}")
            raise
    
    def _encode_pdf(self, pdf_path: Path) -> str:
        import base64
        with open(pdf_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

