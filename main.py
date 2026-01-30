from pyscript import display
from js import document, Uint8Array
import re
import unicodedata
import asyncio
import openai
from urllib.parse import quote as encodeURIComponent

# Street suffixes for redaction
street_suffixes = ["Street","St","Avenue","Ave","Road","Rd","Lane","Ln","Drive","Dr",
                   "Court","Ct","Circle","Cir","Boulevard","Blvd","Place","Pl",
                   "Terrace","Ter","Parkway","Pkwy","Way","Trail","Trl"]

def normalize_text(text):
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    text = re.sub(r'[\x00-\x1F\x7F]', '', text)
    text = re.sub(r'[_–—]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def redact_text(text):
    text = normalize_text(text)
    # Name redaction
    words = re.findall(r'\b[A-Z][a-z]+\b', text)
    for w in set(words):
        text = re.sub(r'\b'+re.escape(w)+r'\b', "[NAME]", text)
    # Address redaction
    suffix_pattern = r'(?:' + '|'.join(street_suffixes) + r')\.?'
    address_pattern = re.compile(r'\d{1,5}\s+(?:[A-Z][a-z]+(?:\s+)){1,4}'+suffix_pattern, flags=re.MULTILINE)
    text = re.sub(address_pattern, "[ADDRESS]", text)
    # Age redaction
    text = re.sub(r'\b\d+\s*(?:year|years|yr|yrs|y/o|yo|old|month|months|mo|mos|week|weeks|wk|wks|day|days)\b',
                  "[AGE]", text, flags=re.IGNORECASE)
    # Date redaction
    text = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', "[DATE]", text)
    text = re.sub(r'\b\d{4}[/-]\d{1,2}[/-]\d{1,2}\b', "[DATE]", text)
    return text

async def read_file(file):
    buf = await file.arrayBuffer()  # JS Promise
    uint8_array = Uint8Array.new(buf)
    return bytes(uint8_array).decode("utf-8", errors="ignore")

async def process_files(event):
    api_key = document.getElementById("api-key").value
    files = document.getElementById("file-upload").files
    problem = document.getElementById("problem").value

    if not api_key or files.length == 0 or not problem:
        display("⚠ Please provide API key, file(s), and a problem description.", target="output")
        return

    redacted_texts = []
    for i in range(files.length):
        f = files[i]
        content = await read_file(f)
        redacted = redact_text(content)
        redacted_texts.append(redacted)

    combined_redacted = "\n\n".join(redacted_texts)
    display(combined_redacted, target="output")

    # GPT-4o request
    openai.api_key = api_key
    prompt = f"Patient Problem:\n{problem}\n\nPAST CHARTS:\n{combined_redacted}\n\nRecommendation:"

    response = await openai.chat.completions.acreate(
        model="gpt-4o",
        messages=[{"role":"user","content":prompt}],
        temperature=0.2
    )
    result = response.choices[0].message.content
    display(result, target="gpt-output")

    # Save combined redacted for download
    global last_redacted
    last_redacted = combined_redacted

# Download function
def download_redacted(event):
    try:
        data = last_redacted
    except NameError:
        display("⚠ No redacted text to download.", target="output")
        return
    a = document.createElement("a")
    a.href = "data:text/plain;charset=utf-8," + encodeURIComponent(data)
    a.download = "redacted.txt"
    a.click()

# Bind buttons
document.getElementById("process-btn").addEventListener("click", lambda e: asyncio.create_task(process_files(e)))
document.getElementById("download-btn").addEventListener("click", download_redacted)
