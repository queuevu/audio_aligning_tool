import os
import time
import json
import base64
import wave
import zipfile
import ipywidgets as widgets

from google import genai
from google.genai import types
from google.colab import files, userdata
from IPython.display import display

# ============================================================
# Configuration
# ============================================================

API_KEY = userdata.get("GEMINI_API_KEY")
MODEL = "gemini-3.1-flash-tts-preview"

client = genai.Client(api_key=API_KEY)

# ============================================================
# Choose JSONL Source
# ============================================================

JSONL_DIR = "/content/jsonl"

jsonl_files = sorted(
    f for f in os.listdir(JSONL_DIR)
    if f.endswith(".jsonl")
)
filename_box = widgets.Text(
    value="generated_audios.zip",
    description="Filename:",
    layout=widgets.Layout(width="450px")
)

source = widgets.ToggleButtons(
    options=[
        ("📂 From Colab", "colab"),
        ("💻 Upload", "upload"),
    ],
    description="Source:",
)

dropdown = widgets.Dropdown(
    options=jsonl_files,
    description="JSONL:",
    layout=widgets.Layout(width="450px"),
)

upload = widgets.FileUpload(
    accept=".jsonl",
    multiple=False,
)

upload.layout.display = "none"

continue_btn = widgets.Button(
    description="🚀 Generate Audio",
    button_style="success",
)

status = widgets.Output()

def change_source(change):
    if source.value == "colab":
        dropdown.layout.display = ""
        upload.layout.display = "none"
    else:
        dropdown.layout.display = "none"
        upload.layout.display = ""

source.observe(change_source, names="value")

display(
    filename_box,
    source,
    dropdown,
    upload,
    continue_btn,
    status,
)

def generate_audio(_):

    with status:

        status.clear_output()

        if source.value == "colab":

            jsonl_file = os.path.join(
                JSONL_DIR,
                dropdown.value,
            )

        else:

            if not upload.value:
                print("Please upload a JSONL file.")
                return

            uploaded_info = next(iter(upload.value.values()))

            jsonl_file = uploaded_info["name"]

            with open(jsonl_file, "wb") as f:
                f.write(uploaded_info["content"])

        # ============================================================
        # Upload to Gemini Files API
        # ============================================================

        print("\nUploading input file...")

        uploaded_file = client.files.upload(
            file=jsonl_file,
            config=types.UploadFileConfig(
                display_name="tts-batch-input",
                mime_type="application/jsonl",
            ),
        )

        print("Uploaded:", uploaded_file.name)

        # ============================================================
        # Create Batch Job
        # ============================================================

        print("\nCreating batch job...")

        batch_job = client.batches.create(
            model=MODEL,
            src=uploaded_file.name,
            config={
                "display_name": "tts-batch-job",
            },
        )

        print("Batch Job:", batch_job.name)

        # ============================================================
        # Wait
        # ============================================================

        completed = {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

        print("\nWaiting for completion...")

        while batch_job.state.name not in completed:
            time.sleep(10)
            batch_job = client.batches.get(name=batch_job.name)
            print("State:", batch_job.state.name)

        print("\nFinal State:", batch_job.state.name)

        if batch_job.state.name != "JOB_STATE_SUCCEEDED":
            raise RuntimeError(f"Batch failed: {batch_job.state.name}")

        # ============================================================
        # Download output JSONL
        # ============================================================

        result_file = batch_job.dest.file_name

        print("\nDownloading batch output...")

        content = client.files.download(file=result_file)

        with open("batch_output.jsonl", "wb") as f:
            f.write(content)

        print("Downloaded batch_output.jsonl")

        # ============================================================
        # Convert JSONL -> WAV
        # ============================================================

        OUTPUT_DIR = "generated_audio"
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        count = 0

        with open("batch_output.jsonl", "r", encoding="utf-8") as f:

            for line in f:

                if not line.strip():
                    continue

                obj = json.loads(line)

                key = obj["key"]

                try:
                    audio_b64 = (
                        obj["response"]
                        ["candidates"][0]
                        ["content"]
                        ["parts"][0]
                        ["inlineData"]["data"]
                    )
                except Exception:
                    print(f"Skipping {key} (no audio)")
                    continue

                pcm = base64.b64decode(audio_b64)

                wav_file = os.path.join(OUTPUT_DIR, f"{key}.wav")

                with wave.open(wav_file, "wb") as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(24000)
                    wav.writeframes(pcm)

                count += 1

        print(f"\nGenerated {count} WAV files.")

        # ============================================================
        # ZIP
        # ============================================================

        zip_name = filename_box.value.strip()

        if not zip_name:
            zip_name = "generated_audio.zip"

        if not zip_name.lower().endswith(".zip"):
            zip_name += ".zip"

        with zipfile.ZipFile(zip_name, "w", zipfile.ZIP_DEFLATED) as z:

            for file in sorted(os.listdir(OUTPUT_DIR)):
                z.write(
                    os.path.join(OUTPUT_DIR, file),
                    arcname=file,
                )

        print("Created ZIP:", zip_name)

        files.download(zip_name)
        print("\nDone!")
continue_btn.on_click(generate_audio)
