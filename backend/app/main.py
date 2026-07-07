from __future__ import annotations

import uuid

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .jobs import JOB_STORE, run_pipeline
from .schemas import AnalyzeAccepted, AnalyzeRequest, JobStatus

app = FastAPI(title="DAWpro Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeAccepted)
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    persona_id: str = Form(...),
    sonic_intention: str = Form(...),
    source: str = Form(...),
    genre: str | None = Form(None),
    bpm: float | None = Form(None),
    time_signature: str | None = Form(None),
) -> AnalyzeAccepted:
    if source not in ("plugin_capture", "reference_upload"):
        raise HTTPException(400, "source must be 'plugin_capture' or 'reference_upload'")

    request = AnalyzeRequest(
        session_id=session_id,
        persona_id=persona_id,
        sonic_intention=sonic_intention,
        genre=genre,
        source=source,  # type: ignore[arg-type]
        bpm=bpm,
        time_signature=time_signature,
    )
    job_id = str(uuid.uuid4())
    audio_bytes = await file.read()

    JOB_STORE[job_id] = JobStatus(job_id=job_id, status="queued", progress=0.0)
    background_tasks.add_task(run_pipeline, job_id, request, audio_bytes, file.filename or "audio.wav")

    return AnalyzeAccepted(job_id=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    job = JOB_STORE.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job
