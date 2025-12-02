import os
import json
import re
import pdfplumber
from datetime import datetime
from flask import Flask, jsonify, request

   
with open('./config.json', "r", encoding="utf-8") as cfg:
        data =  json.load(cfg)


UPLOADS = data["upload"]
ICD_REGEX = data["icd_pattern"]


os.makedirs(UPLOADS, exist_ok=True)
os.makedirs("logs", exist_ok=True)


def write_log(msg):
    log_file = os.path.join("logs", "app.log")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")


def log_exception(e, func_name, logfile="logs/error.log"):
    tb = e.__traceback__
    
    if tb:
        lineno = tb.tb_lineno
    else:
        lineno = "N/A"

    error_message = (
        f"\nIn {func_name} LINE.NO-{lineno} : {type(e).__name__}: {e}\n"
        + ''.join(traceback.format_exception(type(e), e, tb))
    )

    with open(logfile, 'a', encoding='utf-8') as fp:
        fp.write(error_message)

def processLogger(process, logfile="logs/process.log"):
    with open(logfile, 'a', encoding='utf-8') as fp:
        fp.writelines(f"\n{datetime.now()} {process}")


def parse_pdf(pdf_file):
    results = []

    try:
        with pdfplumber.open(pdf_file) as pdf:
            for p in pdf.pages:

               
                extracted_text = p.extract_text(layout=True) or ""

                
                codes_found = set(re.findall(ICD_REGEX, extracted_text))

            
                coords = []
                for word in p.extract_words():
                    coords.append({
                        "text": word.get("text", ""),
                        "x0": round(word.get("x0", 0), 2),
                        "y0": round(word.get("top", 0), 2),
                        "x1": round(word.get("x1", 0), 2),
                        "y1": round(word.get("bottom", 0), 2)
                    })

                
                page_output = {
                    "page": p.page_number,
                    "width": p.width,
                    "height": p.height,
                    "snippet": extracted_text[:150],
                    "codes": list(codes_found),
                    "words": coords
                }

                results.append(page_output)

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
    app.run(host="0.0.0.0", port=9001)

