import os
import json
import re
import fitz
from datetime import datetime
from flask import Flask, jsonify, request

CONFIG = {
    "upload_directory": r"D:\ai basics",
    "icd_pattern": r"(?:ICD-(?:10|9)-CM):?\s*\[?([A-Z\d]\d{1,2}(?:\.\d+)?(?:,\s*[A-Z\d]\d{1,2}(?:\.\d+)?)*)\]?"
}

UPLOADS = CONFIG["upload_directory"]
ICD_PATTERN = CONFIG["icd_pattern"]

os.makedirs("logs", exist_ok=True)

def write_log(msg):
    log_file = os.path.join("logs", "app.log")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def parse_pdf(pdf_file):
    results = []

    try:
        doc = fitz.open(pdf_file)

        for page_num, page in enumerate(doc):
            text = page.get_text("text") or ""

           
            codes = set(re.findall(ICD_PATTERN, text, flags=re.IGNORECASE))

            
            words_raw = page.get_text("words")
            coords = []
            for w in words_raw:
                x0, y0, x1, y1, word = w[0], w[1], w[2], w[3], w[4]
                coords.append({
                    "text": word,
                    "x0": round(x0, 2),
                    "y0": round(y0, 2),
                    "x1": round(x1, 2),
                    "y1": round(y1, 2)
                })

            results.append({
                "page": page_num + 1,
                "snippet": text[:150],
                "codes": list(codes),
                "words": coords,
                "width": page.rect.width,
                "height": page.rect.height
            })

        doc.close()
        write_log(f"PDF parsed: {pdf_file}")

        return results

    except Exception as e:
        write_log(f"ERROR parsing PDF: {e}")
        raise


def extract_and_highlight(pdf_path):

    doc = fitz.open(pdf_path)
    pdf_data = []

    for page_num, page in enumerate(doc):
        text = page.get_text("text")
        extracted_codes = []

        for match in re.finditer(ICD_PATTERN, text, re.IGNORECASE):
            codes_str = match.group(1)
            codes = [c.strip() for c in codes_str.split(",")]
            extracted_codes.extend(codes)

            for code in codes:
                for inst in page.search_for(code):
                    annot = page.add_highlight_annot(inst)

                    
                    if "ICD-10" in match.group(0).upper():
                        annot.set_colors(stroke=(1, 0.8, 0.8)) 
                    else:
                        annot.set_colors(stroke=(0.6, 0.8, 1))  

                    annot.update()

        pdf_data.append({
            "page": page_num + 1,
            "codes": extracted_codes
        })

    base_name = pdf_path.rsplit(".", 1)[0]
    highlighted_pdf = f"{base_name}_highlighted.pdf"
    json_file = f"{base_name}_words.json"

    
    doc.save(highlighted_pdf)
    doc.close()


    with open(json_file, "w") as f:
        json.dump(pdf_data, f, indent=4)

    write_log(f"Highlighted PDF saved: {highlighted_pdf}")
    write_log(f"JSON saved: {json_file}")

    return highlighted_pdf, json_file


app = Flask(__name__)

@app.route("/")
def home():
    return "PDF Extraction API running. POST /extract to process a PDF."

@app.route("/extract", methods=["POST"])
def extract_api():
    try:
        req = request.get_json()
        pdf_name = req.get("filename")

        if not pdf_name or not pdf_name.lower().endswith(".pdf"):
            return jsonify({"status": "error", "message": "Invalid PDF filename"}), 400

        full_path = os.path.join(UPLOADS, pdf_name)

        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": "File not found"}), 404

        parsed_data = parse_pdf(full_path)
        highlighted_pdf, json_file = extract_and_highlight(full_path)

        return jsonify({
            "status": "success",
            "parsed": parsed_data,
            "highlighted_pdf": highlighted_pdf,
            "json_output": json_file
        })

    except Exception as e:
        write_log(f"API Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run()
