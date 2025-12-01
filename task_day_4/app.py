import os
import json
import re
import fitz  
from datetime import datetime
from flask import Flask, jsonify, request


with open('./config.json', "r", encoding="utf-8") as cfg:
    data = json.load(cfg)

UPLOADS = data["upload"]
# ICD_REGEX_9 = data["icd_pattern_9"]
ICD_REGEX_10 = data["icd_pattern_10"]

os.makedirs(UPLOADS, exist_ok=True)
os.makedirs("logs", exist_ok=True)



def write_log(msg):
    log_file = os.path.join("logs", "app.log")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"[{timestamp}] {msg}\n")



def parse_pdf(pdf_file):
    results = []

    try:
        doc = fitz.open(pdf_file)

        for page_num in range(len(doc)):
            page = doc[page_num]

            
            extracted_text = page.get_text("text") or ""

            
            # codes_9 = set(re.findall(ICD_REGEX_9, extracted_text))
            codes_10 = set(re.findall(ICD_REGEX_10, extracted_text))

           
            words_raw = page.get_text("words")
            coords = []
            for w in words_raw:
                x0, y0, x1, y1, word = w[0], w[1], w[2], w[3], w[4]
                coords.append({
                    "text": word,
                    "x0": round(x0, 2),
                    "y0": round(y0, 2),
                    "x1": round(x1, 2),
                    "y1": round(y1, 2),
                })

            
            page_output = {
                "page": page_num + 1,
                "width": page.rect.width,
                "height": page.rect.height,
                "snippet": extracted_text[:150],
                "codes_10": list(codes_10),
                "words": coords
            }

            results.append(page_output)

        doc.close()
        write_log(f"Success: processed PDF {pdf_file}")
        return results

    except Exception as err:
        write_log(f"ERROR parsing PDF: {err}")
        raise



app = Flask(__name__)

@app.route("/extract", methods=["POST"])
def extract_api():
    try:
        req = request.get_json()
        pdf_name = req.get("filename")

        if not pdf_name or not pdf_name.lower().endswith(".pdf"):
            return jsonify({"status": "error", "message": "Invalid PDF filename"}), 400

        full_path = os.path.join(UPLOADS, pdf_name)

        if not os.path.exists(full_path):
            return jsonify({"status": "error", "message": "File not found in uploads/"}), 404

        parsed = parse_pdf(full_path)

        return jsonify({"status": "success", "data": parsed})

    except Exception as exc:
        write_log(f"API Error: {exc}")
        return jsonify({"status": "error", "message": str(exc)}), 500


if __name__ == "__main__":
    app.run()
