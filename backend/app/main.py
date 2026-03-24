import jwt
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth import create_access_token, decode_access_token, verify_password
from app.ergonomics import analyze_pose, build_calibration_profile
from app.schemas import (
    AnalyzeRequest,
    CalibrationProfile,
    CalibrationRequest,
    LoginRequest,
    TokenResponse,
    UserPublic,
)
from app.storage import (
    get_recent_events,
    get_user_by_email,
    init_db,
    insert_risk_event,
    seed_demo_user_if_empty,
)

app = FastAPI(title="ErgoPilot Prototype API", version="0.1.0")

bearer_scheme = HTTPBearer(auto_error=False)

# In prototype mode we allow localhost browser origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

calibration_profiles: dict[str, CalibrationProfile] = {}


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    seed_demo_user_if_empty()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UserPublic:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please sign in again.",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )
    email = payload.get("sub")
    display_name = payload.get("name")
    if not email or not isinstance(email, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )
    return UserPublic(email=email, display_name=str(display_name or ""))


@app.get("/")
def root() -> dict[str, str]:
    """Landing JSON when someone opens the API base URL in a browser."""
    return {
        "service": app.title,
        "version": app.version,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = get_user_by_email(payload.email)
    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(
        subject_email=user["email"],
        display_name=user["display_name"],
    )
    return TokenResponse(access_token=token)


@app.get("/api/auth/me", response_model=UserPublic)
def me(current: UserPublic = Depends(get_current_user)) -> UserPublic:
    return current


@app.post("/api/calibrate")
def calibrate(payload: CalibrationRequest) -> dict[str, object]:
    profile = build_calibration_profile(payload.landmarks)
    calibration_profiles[payload.worker_id] = profile
    return {
        "worker_id": payload.worker_id,
        "calibration": profile.model_dump(),
        "message": "Calibration saved for worker.",
    }


@app.post("/api/analyze")
def analyze(payload: AnalyzeRequest) -> dict[str, object]:
    profile = calibration_profiles.get(payload.worker_id)
    result = analyze_pose(
        worker_id=payload.worker_id,
        landmarks=payload.landmarks,
        load_kg=payload.load_kg,
        frequency_lifts_per_min=payload.frequency_lifts_per_min,
        calibration=profile,
    )

    if result.risk_level in {"warning", "danger"}:
        # Persist only skeletal points and derived risk metadata.
        insert_risk_event(
            worker_id=result.worker_id,
            risk_level=result.risk_level,
            rula_score=result.rula_score,
            reba_score=result.reba_score,
            rwl_kg=result.rwl_kg,
            niosh_ratio=result.niosh_ratio,
            landmarks_payload=[lm.model_dump() for lm in payload.landmarks],
        )

    return result.model_dump()


@app.get("/api/events")
def events(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, object]:
    return {"count": limit, "items": get_recent_events(limit)}
