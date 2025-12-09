import logging
import fitz
import pdfplumber
import json
import re
import tempfile
from pathlib import Path
from dateutil import parser as dateparser
from statistics import mean
import math

from fastapi import UploadFile, HTTPException
from src.handler import persist

logger = logging.getLogger(__name__)

GSTIN_REGEX = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b", re.I)
AMOUNT_REGEX = re.compile(r"\b[0-9]{1,3}(?:[,0-9]{0,})?\.[0-9]{2}\b")
DATE_CANDIDATE = re.compile(r"\b\d{1,2}[\/\-\s]\w+\s?[\/\-\s]?\d{2,4}|\b\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b")

def is_gstin(s):
    if not s: return False
    return bool(GSTIN_REGEX.search(s))


def find_gstin_in_text(text):
    m = GSTIN_REGEX.search(text)
    return m.group(0).upper() if m else None


def normalize_text(s):
    if not s: return ""
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def parse_date_candidate(s):
    try:
        return dateparser.parse(s, dayfirst=True).date().isoformat()
    except Exception:
        return None


def extract_layout_spans(pdf_path):
    spans = []
    doc = fitz.open(pdf_path)
    for page_no, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for b in blocks:
            if "lines" not in b:
                continue
            for line in b["lines"]:
                for span in line["spans"]:
                    text = span.get("text", "").strip()
                    if not text:
                        continue
                    x0, y0, x1, y1 = span["bbox"]
                    spans.append({
                        "text": text,
                        "x0": x0, "y0": y0, "x1": x1, "y1": y1,
                        "cx": (x0 + x1)/2,
                        "cy": (y0 + y1)/2,
                        "font": span.get("font", ""),
                        "size": span.get("size", 0),
                        "page": page_no
                    })
    return spans


def load_templates(templates_folder: Path):
    templates = []
    for p in templates_folder.glob("*.json"):
        try:
            t = json.loads(p.read_text(encoding="utf8"))
            templates.append(t)
        except Exception as e:
            print(f"Warning: failed to load template {p}: {e}")
    return templates


def detect_template(spans, templates):
    text_blob = " ".join([s["text"].lower() for s in spans])
    for t in templates:
        for kw in t.get("vendor_keywords", []):
            if kw.lower() in text_blob:
                return t
    for t in templates:
        if t.get("name","").lower() == "default":
            return t
    return templates[0] if templates else None


def euclid(a,b):
    return math.hypot(a["cx"]-b["cx"], a["cy"]-b["cy"])


def is_label(text, keywords):
    return any(kw.lower() in text.lower() for kw in keywords)


def score_candidate(field, value):
    value = value.strip()
    if not value or len(value) < 2:
        return -10
    if field == "invoice_number":
        return 10 if re.match(r"[A-Za-z0-9/-]{6,}", value) else -5
    if field == "eway_bill":
        return 10 if re.match(r"[0-9]{10,}", value) else -5
    if field == "truck_no":
        return 10 if re.match(r"[A-Z]{2}[0-9]{2}[A-Z]{0,2}[0-9]{3,4}", value) else -5
    if field == "amount_in_words":
        return 10 if "Rupees" in value or "rupees" in value.lower() else -5
    if field == "gstin":
        return 10 if GSTIN_REGEX.search(value) else -5
    return 1


def find_best_match(spans, label_span, field, keywords):
    best_candidate = None
    best_score = -999
    lx, ly = label_span["cx"], label_span["cy"]
    for span in spans:
        if span == label_span:
            continue
        if is_label(span["text"], keywords):
            continue
        dx = span["cx"] - lx
        dy = span["cy"] - ly
        if dx < -5 and dy < -5:
            continue
        distance = math.hypot(dx, dy)
        if distance > 200:
            continue
        score = score_candidate(field, span["text"]) - distance * 0.02
        if score > best_score:
            best_score = score
            best_candidate = span["text"]
    return best_candidate


def extract_kv_fields(spans, template):
    results = {}
    for field, keywords in template["fields"].items():
        best_match = None
        for span in spans:
            if is_label(span["text"], keywords):
                candidate = find_best_match(spans, span, field, keywords)
                if candidate:
                    best_match = candidate
                    break
        results[field] = normalize_text(best_match) if best_match else None
    return results


def extract_table_rows(pdf_path, table_keywords):
    items = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            try:
                tables = page.extract_tables()
            except Exception:
                tables = []
            for table in tables:
                cleaned = [[c.strip() if isinstance(c, str) else "" for c in row] for row in table]
                header = " ".join(cleaned[0]).lower() if cleaned else ""
                if any(kw.lower() in header for kw in table_keywords):
                    for row in cleaned[1:]:
                        if not any(cell for cell in row):
                            continue
                        row = row + [""] * (5 - len(row))
                        hsn_candidate = row[1]
                        qty_candidate = row[2]
                        rate_candidate = row[3]
                        amount_candidate = row[4] if len(row) > 4 else ""
                        is_hsn = bool(re.match(r"^\d{3,6}$", hsn_candidate.replace(" ", "")))
                        is_qty = bool(re.match(r"^[0-9\.\,]+$", qty_candidate))
                        is_amt = bool(AMOUNT_REGEX.search(amount_candidate) or AMOUNT_REGEX.search(rate_candidate))
                        if is_hsn or is_qty or is_amt:
                            items.append({
                                "description": normalize_text(row[0]),
                                "hsn_code": normalize_text(row[1]),
                                "quantity": normalize_text(row[2]),
                                "rate": normalize_text(row[3]),
                                "amount": normalize_text(row[4])
                            })
    return items


def extract_amount_in_words_from_text(text):
    m = re.search(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,15}\s+Rupees.*?Paise)", text, re.I)
    if m:
        return normalize_text(m.group(1))
    m2 = re.search(r"(Rupees[\s\S]{1,100}Paise)", text, re.I)
    return normalize_text(m2.group(1)) if m2 else None


def compute_confidence(result):
    mandatory = ["invoice_number", "invoice_date", "gstin", "items"]
    score = 0
    for k in mandatory:
        v = result.get(k)
        if v:
            if k == "items":
                score += 1 if isinstance(v, list) and len(v) > 0 else 0
            else:
                score += 1
    return int(score / len(mandatory) * 100)


def parse_invoice_file(pdf_path: Path, templates):
    spans = extract_layout_spans(str(pdf_path))
    template = detect_template(spans, templates)
    kv = extract_kv_fields(spans, template)
    items = extract_table_rows(str(pdf_path), template.get("table_keywords", []))
    flat_text = " ".join([s["text"] for s in spans])
    if not kv.get("gstin"):
        kv["gstin"] = find_gstin_in_text(flat_text)
    if not kv.get("amount_in_words"):
        kv["amount_in_words"] = extract_amount_in_words_from_text(flat_text)
    result = {
        "file": str(pdf_path.name),
        "vendor_template": template.get("name"),
        **kv,
        "items": items
    }
    result["confidence"] = compute_confidence(result)
    return result


def prepare_parsing(file, templates_folder: Path, out_folder: Path):
    templates = load_templates(templates_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    result = parse_invoice_file(file, templates)
    persist.PersistHandler.save(result)
    out_path = out_folder / (file.stem + ".json")
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf8")
    logger.info(f"Processed {file.name} -> confidence {result['confidence']}%")
    (out_folder / "results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf8")
    return result


class ParseHandler:
    @staticmethod
    async def handle_parse(file: UploadFile) -> dict:
        file_path = None
        try:
            content = await file.read()
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(content)
                file_path = Path(tmp.name)
            
            BASE = Path(__file__).parent.parent.parent
            templates_folder = BASE / "templates"
            out_folder = BASE / "output"
            result = prepare_parsing(file_path, templates_folder, out_folder)
            return result
        except Exception as e:
            logger.error(f"Error parsing file: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if file_path and file_path.exists():
                file_path.unlink()