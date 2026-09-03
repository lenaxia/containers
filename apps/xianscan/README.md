# xianscan

[xianscan-rust](https://github.com/ArbenApura/xianscan-rust) packaged from the
upstream self-contained release binary — a local-first translation studio for
manga, manhwa, and manhua (speech-bubble detection, multi-language OCR, LLM
translation, LaMa inpainting, typesetting) served as a web UI.

## Usage

```yaml
services:
  xianscan:
    image: ghcr.io/lenaxia/containers/xianscan:0.5.0-beta.2
    ports:
      - "8124:8124"
    volumes:
      - ./xianscan-config:/config
```

Open `http://localhost:8124`. The first launch extracts the embedded web assets
into `/config` and loads the ONNX models into memory; expect a slow start
(~30s).

## Storage

Everything persistent lives under `/config` (`XDG_DATA_HOME`):

| Path | Contents |
| :--- | :--- |
| `/config/xianscan/app` | Extracted SvelteKit web UI + Node runtime (first run) |
| `/config/xianscan/data` | SQLite library, book/chapter image caches, covers |

## Notes

- **amd64 only** — upstream publishes linux-x86_64 binaries only.
- **CPU-first**: runs multi-threaded CPU inference out of the box. The binary
  carries the ONNX Runtime CUDA execution providers; to enable GPU inference,
  run with the NVIDIA Container Toolkit and provide cuDNN 9 on
  `LD_LIBRARY_PATH` (otherwise it silently falls back to CPU).
- **Translation LLM is external** — point the in-app settings at Ollama, LM
  Studio, or a cloud API. From another container use
  `http://ollama:11434`-style service addresses.
- The internal ML engine listens on loopback `:8123` inside the container; only
  `:8124` needs publishing.
