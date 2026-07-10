from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_superuser
from app.db.session import get_db
from app.models.api_token import ApiToken
from app.models.repository import Repository
from app.models.tournament_series import TournamentSeries
from app.models.user import User
from app.schemas.streaming import (
    SourcePublic,
    TournamentSeriesCreateRequest,
    TournamentSeriesPublic,
    TournamentSeriesUpdateRequest,
    TournamentSourcesUpdateRequest,
)
from app.schemas.user import UserPublic
from app.schemas.user_management import (
    ApiTokenCreateRequest,
    ApiTokenCreateResponse,
    ApiTokenPublic,
    RepositoryCreateRequest,
    RepositoryPublic,
    UserRoleUpdateRequest,
    UserRepositoriesUpdateRequest,
)
from app.services.user_service import (
    create_api_token_for_user,
    get_or_create_public_repository,
    revoke_api_token_for_user,
)
from app.services.tournament_slug import TournamentSlugProviderError, normalize_provider_slug, resolve_tournament_name

router = APIRouter()


@router.get("", response_model=list[UserPublic])
def list_users(db: Session = Depends(get_db), _: User = Depends(get_superuser)) -> list[UserPublic]:
    users = db.scalars(select(User).order_by(User.id.asc())).all()
    return [UserPublic.model_validate(user) for user in users]


@router.patch("/{user_id}/role", response_model=UserPublic)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdateRequest,
    db: Session = Depends(get_db),
    current_superuser: User = Depends(get_superuser),
) -> UserPublic:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_superuser.id and payload.role != "superuser":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove your own superuser role")

    user.role = payload.role
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


@router.get("/me/api-tokens", response_model=list[ApiTokenPublic])
def list_my_api_tokens(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ApiTokenPublic]:
    tokens = db.scalars(
        select(ApiToken).where(ApiToken.user_id == current_user.id).order_by(ApiToken.created_at.desc())
    ).all()
    return [ApiTokenPublic.model_validate(token) for token in tokens]


@router.post("/me/api-tokens", response_model=ApiTokenCreateResponse)
def create_my_api_token(
    payload: ApiTokenCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ApiTokenCreateResponse:
    if current_user.role not in {"uploader", "superuser"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not approved for upload token generation",
        )

    token_row, raw_token = create_api_token_for_user(
        db,
        current_user,
        payload.source_name,
        payload.repository_ids,
    )
    return ApiTokenCreateResponse(token=raw_token, token_info=ApiTokenPublic.model_validate(token_row))


@router.delete("/me/api-tokens/{token_id}")
def revoke_my_api_token(
    token_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    revoke_api_token_for_user(db, current_user, token_id)
    return {"message": "API token revoked"}


@router.get("/repositories", response_model=list[RepositoryPublic])
def list_repositories(db: Session = Depends(get_db), _: User = Depends(get_superuser)) -> list[RepositoryPublic]:
    repositories = db.scalars(select(Repository).order_by(Repository.name.asc())).all()
    return [RepositoryPublic.model_validate(repo) for repo in repositories]


@router.post("/repositories", response_model=RepositoryPublic)
def create_repository(
    payload: RepositoryCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_superuser),
) -> RepositoryPublic:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository name is required")

    existing = db.scalar(select(Repository).where(Repository.name == name))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository already exists")

    repo = Repository(name=name, is_public=False)
    db.add(repo)
    db.commit()
    db.refresh(repo)
    return RepositoryPublic.model_validate(repo)


@router.put("/{user_id}/repositories", response_model=UserPublic)
def update_user_repositories(
    user_id: int,
    payload: UserRepositoriesUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_superuser),
) -> UserPublic:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    public_repo = get_or_create_public_repository(db)
    unique_ids = set(payload.repository_ids)
    unique_ids.add(public_repo.id)

    repositories = db.scalars(select(Repository).where(Repository.id.in_(unique_ids))).all()
    if len(repositories) != len(unique_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more repositories do not exist")

    user.repositories = repositories
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserPublic.model_validate(user)


@router.get("/sources", response_model=list[SourcePublic])
def list_all_sources(db: Session = Depends(get_db), _: User = Depends(get_superuser)) -> list[SourcePublic]:
    rows = db.execute(
        select(ApiToken, User)
        .join(User, User.id == ApiToken.user_id)
        .order_by(ApiToken.source_name.asc())
    ).all()
    return [
        SourcePublic(
            id=token.id,
            source_name=token.source_name,
            token_prefix=token.token_prefix,
            username=user.username,
        )
        for token, user in rows
    ]


@router.get("/tournaments", response_model=list[TournamentSeriesPublic])
def list_tournaments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[TournamentSeriesPublic]:
    if current_user.role != "superuser":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required")
    tournaments = db.scalars(select(TournamentSeries).order_by(TournamentSeries.name.asc())).all()
    return [TournamentSeriesPublic.model_validate(t) for t in tournaments]


@router.post("/tournaments", response_model=TournamentSeriesPublic)
def create_tournament(
    payload: TournamentSeriesCreateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_superuser),
) -> TournamentSeriesPublic:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament name is required")
    existing = db.scalar(select(TournamentSeries).where(TournamentSeries.name == name))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament already exists")

    existing_repository = db.scalar(select(Repository).where(Repository.name == name))
    if existing_repository:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository with this name already exists")

    try:
        provider, slug = normalize_provider_slug(payload.provider, payload.slug)
    except TournamentSlugProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    repository = Repository(name=name, is_public=payload.is_public)
    db.add(repository)
    db.flush()

    tournament = TournamentSeries(name=name, repository_id=repository.id, provider=provider, slug=slug)
    if provider and slug:
        tournament.current_tournament_name, tournament.current_tournament_name_fetched_at = resolve_tournament_name(
            provider,
            slug,
        )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return TournamentSeriesPublic.model_validate(tournament)


@router.patch("/tournaments/{tournament_id}", response_model=TournamentSeriesPublic)
def update_tournament(
    tournament_id: int,
    payload: TournamentSeriesUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_superuser),
) -> TournamentSeriesPublic:
    tournament = db.get(TournamentSeries, tournament_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    if payload.name is not None:
        updated_name = payload.name.strip()
        if not updated_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament name is required")
        existing = db.scalar(
            select(TournamentSeries).where(
                TournamentSeries.name == updated_name,
                TournamentSeries.id != tournament_id,
            )
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament already exists")

        repository_name_conflict = db.scalar(
            select(Repository).where(
                Repository.name == updated_name,
                Repository.id != tournament.repository_id,
            )
        )
        if repository_name_conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository with this name already exists")

        tournament.name = updated_name
        tournament.repository.name = updated_name

    if payload.is_public is not None:
        tournament.repository.is_public = payload.is_public

    provider_input = tournament.provider if payload.provider is None else payload.provider
    slug_input = tournament.slug if payload.slug is None else payload.slug

    try:
        provider, slug = normalize_provider_slug(provider_input, slug_input)
    except TournamentSlugProviderError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    changed_provider_slug = provider != tournament.provider or slug != tournament.slug
    tournament.provider = provider
    tournament.slug = slug

    if not provider or not slug:
        tournament.current_tournament_name = None
        tournament.current_tournament_name_fetched_at = None
    elif changed_provider_slug or payload.refresh_current_tournament_name:
        tournament.current_tournament_name, tournament.current_tournament_name_fetched_at = resolve_tournament_name(
            provider,
            slug,
            cached_name=tournament.current_tournament_name,
            cached_at=tournament.current_tournament_name_fetched_at,
            force_refresh=payload.refresh_current_tournament_name,
        )

    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return TournamentSeriesPublic.model_validate(tournament)


@router.put("/tournaments/{tournament_id}/sources", response_model=TournamentSeriesPublic)
def update_tournament_sources(
    tournament_id: int,
    payload: TournamentSourcesUpdateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_superuser),
) -> TournamentSeriesPublic:
    tournament = db.get(TournamentSeries, tournament_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")

    unique_ids = list(dict.fromkeys(payload.source_ids))
    if unique_ids:
        sources = db.scalars(select(ApiToken).where(ApiToken.id.in_(unique_ids))).all()
        if len(sources) != len(unique_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more sources do not exist")
        tournament.sources = sources
    else:
        tournament.sources = []

    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return TournamentSeriesPublic.model_validate(tournament)


@router.get("/tournaments/{tournament_id}/sources", response_model=list[int])
def get_tournament_source_ids(
    tournament_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_superuser),
) -> list[int]:
    tournament = db.get(TournamentSeries, tournament_id)
    if not tournament:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tournament not found")
    return [token.id for token in tournament.sources]
