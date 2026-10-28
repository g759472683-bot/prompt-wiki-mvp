from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..deps import get_current_user, get_session
from ..models import Release, User
from ..schemas import LatestReleaseOut, ReleaseOut

router = APIRouter(tags=["releases"])


def _out(release: Release) -> ReleaseOut:
    return ReleaseOut(
        id=release.id,
        version_code=release.version_code,
        version_name=release.version_name,
        notes=release.notes,
        filename=release.filename,
        size_bytes=release.size_bytes,
        sha256=release.sha256,
        active=release.active,
        download_url=f"/v1/app/download/{release.id}",
    )


@router.post("/releases", response_model=ReleaseOut)
async def upload_release(
    request: Request,
    version_code: int = Form(...),
    version_name: str = Form(...),
    notes: str = Form(""),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReleaseOut:
    if session.scalar(select(Release).where(Release.version_code == version_code)):
        raise HTTPException(status_code=409, detail="version_code already exists")
    if not (file.filename or "").lower().endswith(".apk"):
        raise HTTPException(status_code=400, detail="only .apk files are accepted")

    data = await file.read()
    if len(data) > 120 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="APK exceeds 120MB")
    release_id = "rel-" + uuid.uuid4().hex[:12]
    directory = request.app.state.settings.data_dir / "releases"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{release_id}.apk"
    path.write_bytes(data)

    release = Release(
        id=release_id,
        version_code=version_code,
        version_name=version_name.strip(),
        notes=notes.strip() or None,
        filename=file.filename or "promptwiki.apk",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        path=str(path),
        active=False,
    )
    session.add(release)
    session.commit()
    session.refresh(release)
    return _out(release)


@router.get("/releases", response_model=list[ReleaseOut])
def list_releases(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ReleaseOut]:
    releases = session.scalars(
        select(Release).order_by(Release.version_code.desc())
    ).all()
    return [_out(release) for release in releases]


@router.post("/releases/{release_id}/activate", response_model=ReleaseOut)
def activate_release(
    release_id: str,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReleaseOut:
    release = session.get(Release, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="release not found")
    for item in session.scalars(select(Release)).all():
        item.active = item.id == release_id
    session.commit()
    session.refresh(release)
    return _out(release)


@router.get("/app/latest", response_model=LatestReleaseOut)
def latest_release(session: Session = Depends(get_session)) -> LatestReleaseOut:
    release = session.scalar(
        select(Release)
        .where(Release.active.is_(True))
        .order_by(Release.version_code.desc())
    )
    if release is None:
        raise HTTPException(status_code=404, detail="no active release")
    return LatestReleaseOut(
        version_code=release.version_code,
        version_name=release.version_name,
        notes=release.notes,
        download_url=f"/v1/app/download/{release.id}",
        sha256=release.sha256,
    )


@router.get("/app/download/{release_id}")
def download_release(
    release_id: str,
    session: Session = Depends(get_session),
) -> FileResponse:
    release = session.get(Release, release_id)
    if release is None:
        raise HTTPException(status_code=404, detail="release not found")
    path = Path(release.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="APK file missing")
    return FileResponse(
        path,
        media_type="application/vnd.android.package-archive",
        filename=release.filename,
    )
