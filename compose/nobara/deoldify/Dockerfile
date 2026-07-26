# DeOldify: colorization for old B&W photos. Repo is archived (no more upstream fixes),
# so pinned to a specific commit rather than master - see repo CLAUDE.md security note.
# Base image matches the CUDA/torch version the pinned fastai==1.0.60 actually needs.
FROM pytorch/pytorch:1.11.0-cuda11.3-cudnn8-runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg libgl1 libglib2.0-0 curl build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/jantic/DeOldify.git . \
    && git checkout 5f86c28923799036ad4b1bf7af8c629ac65efd75

# Inference-only deps, trimmed from upstream requirements.txt:
# - dropped wandb (cloud telemetry, unused for local inference)
# - dropped jupyterlab/ipywidgets/tornado (notebook-server-only, not imported by the
#   deoldify package - unlike yt-dlp/ipython below, which visualize.py imports unconditionally)
# - Pillow bumped past 9.3.0 (CVE-2023-50447 RCE, CVE-2023-44271, CVE-2024-28219)
RUN pip install --no-cache-dir \
    fastai==1.0.60 tensorboardX opencv-python-headless "Pillow>=10" ffmpeg-python \
    yt-dlp ipython

# Official weights only - do not substitute a third-party mirror.
# ponytail: no known-good sha256 published upstream to pin against; if that changes, verify here.
RUN mkdir -p models \
    && curl -fL --retry 8 --retry-delay 3 -C - \
       https://data.deepai.org/deoldify/ColorizeArtistic_gen.pth -o models/ColorizeArtistic_gen.pth

COPY colorize.py .

# Build-time smoke test: synthetic image, just to prove the pipeline (weights, imports,
# GPU codepath) runs end-to-end. Not a quality check. Fails the build if wiring breaks.
RUN python -c "from PIL import Image; Image.new('RGB', (64, 64)).save('/tmp/smoke.jpg')" \
    && python colorize.py /tmp/smoke.jpg /tmp/smoke_out.jpg \
    && rm -f /tmp/smoke.jpg /tmp/smoke_out.jpg

ENTRYPOINT ["python", "colorize.py"]
