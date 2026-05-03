#!/usr/bin/env python3
"""Start a vLLM server for ibm-granite/granite-docling-258M.

Usage (on a CUDA machine):
    python scripts/serve_docling.py
    python scripts/serve_docling.py --port 8001 --max-num-seqs 8

The script kills any existing vLLM process on the target port, launches a new
one, and blocks until the server is ready (or times out).

Once running, set in webapp/.env:
    VLLM_BASE_URL=http://localhost:<port>/v1
    VLLM_MODEL=ibm-granite/granite-docling-258M
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

MODEL = "models/ibm-granite/granite-docling-258M"
MODEL_NAME = "ibm-granite/granite-docling-258M"
REVISION = "untied"
READY_MSG = "Application startup complete"
MAX_WAIT_S = 300


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Serve Granite Docling via vLLM")
    p.add_argument("--model", default=MODEL)
    p.add_argument("--model-name", default=MODEL_NAME)
    p.add_argument("--revision", default=REVISION)
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8001)
    p.add_argument(
        "--gpu-memory-utilization", type=float, default=0.90, dest="gpu_mem"
    )
    p.add_argument(
        "--max-model-len", type=int, default=6144, dest="max_model_len"
    )
    p.add_argument("--max-num-seqs", type=int, default=1, dest="max_num_seqs")
    p.add_argument(
        "--max-num-batched-tokens",
        type=int,
        default=6144,
        dest="max_num_batched_tokens",
    )
    p.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Path for the vLLM log file (default: granite_docling_<port>.log)",
    )
    return p.parse_args()


def kill_existing(port: int) -> None:
    subprocess.run(
        f'pkill -f "vllm.entrypoints.openai.api_server .*--port {port}" || true',
        shell=True,
        check=False,
    )
    time.sleep(2)


def launch(args: argparse.Namespace, log_path: Path) -> subprocess.Popen:
    cmd = [
        "vllm",
        "serve",
        args.model,
        "--served-model-name",
        args.model_name,
        "--revision",
        args.revision,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--gpu-memory-utilization",
        str(args.gpu_mem),
        "--max-model-len",
        str(args.max_model_len),
        "--max-num-seqs",
        str(args.max_num_seqs),
        "--max-num-batched-tokens",
        str(args.max_num_batched_tokens),
        "--disable-log-stats",
        "--enable-prefix-caching",
        "--trust-remote-code",
    ]
    env = {**os.environ, "TOKENIZERS_PARALLELISM": "true"}
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=log, env=env)
    return proc


def wait_for_ready(log_path: Path, max_wait: int) -> bool:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if log_path.exists() and READY_MSG in log_path.read_text():
            return True
        time.sleep(3)
        print(".", end="", flush=True)
    return False


def main() -> None:
    args = parse_args()
    log_path = args.log_file or Path(f"granite_docling_{args.port}.log")

    print(f"Stopping any existing vLLM on port {args.port} …")
    kill_existing(args.port)

    print(f"Starting {args.model} on {args.host}:{args.port}")
    print(f"Log → {log_path.resolve()}")
    proc = launch(args, log_path)

    print(f"Waiting for startup (up to {MAX_WAIT_S}s)", end="", flush=True)
    if wait_for_ready(log_path, MAX_WAIT_S):
        print(f"\nReady!  http://{args.host}:{args.port}/v1")
        print("\nAdd to webapp/.env:")
        print(f"  VLLM_BASE_URL=http://localhost:{args.port}/v1")
        print(f"  VLLM_MODEL={args.model}")
        try:
            proc.wait()
        except KeyboardInterrupt:
            print("\nShutting down …")
            proc.terminate()
    else:
        print(f"\nTimeout after {MAX_WAIT_S}s — check {log_path}")
        proc.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
