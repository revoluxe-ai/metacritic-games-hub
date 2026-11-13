from fastapi import Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import APIRouter
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Game, GamePlatform
from app.services.similar import find_similar
from app.template_filters import register_filters

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")
register_filters(templates)


def _best_metascore(game: Game) -> int | None:
    scores = [p.metascore for p in game.platforms if p.metascore is not None]
    return max(scores) if scores else None


@router.get("/", response_class=HTMLResponse)
def games_list(
    request: Request,
    q: str | None = None,
    platform: str | None = None,
    sort: str = Query("rating", pattern="^(rating|title|release)$"),
    db: Session = Depends(get_db),
):
    query = db.query(Game).options(joinedload(Game.platforms))
    if q:
        query = query.filter(
            or_(Game.title.ilike(f"%{q}%"), Game.slug.ilike(f"%{q}%"))
        )
    if platform:
        query = query.join(GamePlatform).filter(
            GamePlatform.platform_slug == platform
        )

    games = query.distinct().all()

    if sort == "title":
        games.sort(key=lambda g: g.title.lower())
    elif sort == "release":
        games.sort(key=lambda g: g.release_date or "", reverse=True)
    else:
        games.sort(
            key=lambda g: (_best_metascore(g) is not None, _best_metascore(g) or 0),
            reverse=True,
        )

    platforms = (
        db.query(GamePlatform.platform_slug, GamePlatform.platform_name)
        .distinct()
        .order_by(GamePlatform.platform_name)
        .all()
    )

    return templates.TemplateResponse(
        "games_list.html",
        {
            "request": request,
            "games": games,
            "q": q or "",
            "platform": platform or "",
            "sort": sort,
            "platforms": platforms,
        },
    )


@router.get("/games/{slug}", response_class=HTMLResponse)
def game_detail(slug: str, request: Request, db: Session = Depends(get_db)):
    game = (
        db.query(Game)
        .options(joinedload(Game.platforms))
        .filter(Game.slug == slug)
        .first()
    )
    if not game:
        return HTMLResponse("Game not found", status_code=404)

    all_games = db.query(Game).options(joinedload(Game.platforms)).all()
    similar = find_similar(all_games, game, limit=5)

    return templates.TemplateResponse(
        "game_detail.html",
        {"request": request, "game": game, "similar": similar},
    )


@router.get("/worker", response_class=HTMLResponse)
def worker_monitor(request: Request):
    return templates.TemplateResponse("worker.html", {"request": request})
