import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.limiter import limiter
from app.core.security import get_current_user
from app.models.project import Project
from app.models.signal import Signal
from app.models.signal_chunk import SignalChunk
from app.models.user import User
from app.schemas.signals import SignalOut, SignalPasteRequest
from app.services.chunking import chunk_text
from app.services.embeddings import embed_texts
from app.services.pdf import extract_text

router = APIRouter(prefix="/projects", tags=["signals"])


async def _get_project_or_404(
    project_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if project is None or project.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


async def _ingest_signal(
    raw_text: str,
    source_type: str,
    filename: str | None,
    project: Project,
    db: AsyncSession,
) -> Signal:
    chunks = chunk_text(raw_text)
    if not chunks:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No usable content after chunking")

    embeddings = await embed_texts(chunks)

    signal = Signal(
        project_id=project.id,
        source_type=source_type,
        filename=filename,
        raw_text=raw_text,
    )
    db.add(signal)
    await db.flush()  # get signal.id without committing

    db.add_all([
        SignalChunk(
            signal_id=signal.id,
            chunk_index=i,
            content=text,
            embedding=vec,
        )
        for i, (text, vec) in enumerate(zip(chunks, embeddings))
    ])
    await db.commit()
    await db.refresh(signal)
    return signal


@router.post("/{project_id}/signals/text", response_model=SignalOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def ingest_text(
    request: Request,
    project_id: uuid.UUID,
    body: SignalPasteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignalOut:
    project = await _get_project_or_404(project_id, current_user, db)
    signal = await _ingest_signal(body.content, "text", None, project, db)
    chunk_count = await _count_chunks(signal.id, db)
    return _to_signal_out(signal, chunk_count)


@router.post("/{project_id}/signals/upload", response_model=SignalOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def ingest_pdf(
    request: Request,
    project_id: uuid.UUID,
    file: UploadFile,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignalOut:
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Only PDF files are accepted")
    project = await _get_project_or_404(project_id, current_user, db)
    file_bytes = await file.read()
    try:
        raw_text = extract_text(file_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    if not raw_text:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Could not extract text from PDF")
    signal = await _ingest_signal(raw_text, "pdf", file.filename, project, db)
    chunk_count = await _count_chunks(signal.id, db)
    return _to_signal_out(signal, chunk_count)


@router.get("/{project_id}/signals", response_model=list[SignalOut])
async def list_signals(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SignalOut]:
    await _get_project_or_404(project_id, current_user, db)
    result = await db.execute(select(Signal).where(Signal.project_id == project_id))
    signals = result.scalars().all()
    out: list[SignalOut] = []
    for s in signals:
        count = await _count_chunks(s.id, db)
        out.append(_to_signal_out(s, count))
    return out


@router.get("/{project_id}/signals/{signal_id}", response_model=SignalOut)
async def get_signal(
    project_id: uuid.UUID,
    signal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SignalOut:
    await _get_project_or_404(project_id, current_user, db)
    result = await db.execute(
        select(Signal).where(Signal.id == signal_id, Signal.project_id == project_id)
    )
    signal = result.scalar_one_or_none()
    if signal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Signal not found")
    count = await _count_chunks(signal.id, db)
    return _to_signal_out(signal, count)


async def _count_chunks(signal_id: uuid.UUID, db: AsyncSession) -> int:
    result = await db.execute(
        select(func.count()).select_from(SignalChunk).where(SignalChunk.signal_id == signal_id)
    )
    return result.scalar_one()


def _to_signal_out(signal: Signal, chunk_count: int) -> SignalOut:
    return SignalOut(
        id=signal.id,
        project_id=signal.project_id,
        source_type=signal.source_type,
        filename=signal.filename,
        created_at=signal.created_at,
        chunk_count=chunk_count,
    )
