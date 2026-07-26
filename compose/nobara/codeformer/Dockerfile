# CodeFormer: blind face restoration, tuned for severely degraded (old/damaged) photos.
# Pinned to a specific commit, not master - see repo CLAUDE.md security note.
FROM pytorch/pytorch:2.1.2-cuda11.8-cudnn8-runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    git libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN git clone https://github.com/sczhou/CodeFormer.git . \
    && git checkout b33cc7d639d6545bfcccc7e0bc6ae51f24e79c2b

# Full upstream requirements.txt, as-is: basicsr's setup.py (below) resolves its own
# transitive deps against whatever's already installed, and trimming "unneeded" packages
# here just makes that legacy easy_install resolver fetch fresh unpinned chains instead -
# more version conflicts, not fewer. numpy pinned <2 to match this base image's torch build.
RUN pip install --no-cache-dir "numpy<2" -r requirements.txt

# basicsr/facelib are vendored in the repo itself (not pip packages) - run from repo root,
# but basicsr still needs its setup.py run once to generate basicsr/version.py.
RUN python basicsr/setup.py develop
# Build-time smoke test that doubles as weight prefetch: downloads codeformer.pth,
# RealESRGAN_x2plus.pth and the face-detection/parsing weights from the official
# GitHub release URLs baked into inference_codeformer.py, then runs on the repo's own
# sample images. If this fails, the build fails - no silent broken image.
RUN python inference_codeformer.py --bg_upsampler realesrgan -w 0.7 \
    -i inputs/whole_imgs -o /tmp/build_check && rm -rf /tmp/build_check

ENTRYPOINT ["python", "inference_codeformer.py"]
