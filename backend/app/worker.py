"""Single-worker job runner.

Run from backend/:
    python -m app.worker
"""

from __future__ import annotations

import sys
import time

from .config import Settings
from .db import build_engine, build_sessionmaker
from .llm.client import DeepSeekClient
from .models import ensure_schema
from .services.jobs import process_next_job


def main() -> None:
    settings = Settings()
    settings.ensure_dirs()
    engine = build_engine(settings.db_url)
    ensure_schema(engine)
    session_factory = build_sessionmaker(engine)
    llm = (
        DeepSeekClient(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        if settings.deepseek_api_key
        else None
    )

    print(f"worker started: db={settings.db_url} model={settings.deepseek_model}")
    once = "--once" in sys.argv
    try:
        while True:
            job_id = process_next_job(session_factory, settings, llm)
            if job_id:
                print(f"processed {job_id}")
                if once:
                    break
            elif once:
                print("no queued jobs")
                break
            else:
                time.sleep(2)
    except KeyboardInterrupt:
        print("worker stopped")


if __name__ == "__main__":
    main()
