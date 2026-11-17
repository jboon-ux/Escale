"""Escale — assistant voyage privé.

Serveur web : sert l'interface (static/index.html) et expose /api/recommend,
qui interroge Claude avec la recherche web en direct pour proposer
restaurants, bars, logements, activités et itinéraires.
"""

import json
import os
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Deque, Dict, List, Optional

import anthropic
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

try:  # charge le fichier .env en local ; ignoré si python-dotenv est absent
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

MODEL = os.environ.get("ESCALE_MODEL", "claude-opus-5-5")
ACCESS_CODE = os.environ.get("ESCALE_ACCESS_CODE", "").strip()
BOOKING_AID = os.environ.get("BOOKING_AFFILIATE_ID", "").strip()
RATE_LIMIT_PER_HOUR = int(os.environ.get("ESCALE_RATE_LIMIT_PER_HOUR", "12"))
MAX_SEARCHES = int(os.environ.get("ESCALE_MAX_WEB_SEARCHES", "8"))

STATIC_DIR = Path(__file__).parent / "static"

client = anthropic.Anthropic()  # lit ANTHROPIC_API_KEY dans l'environnement
app = FastAPI(title="Escale")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

MODES = {
    "restaurant": "Trouver un restaurant",
    "bar": "Boire un verre (bar, bar à vin, cocktails, club…)",
    "logement": "Trouver un hébergement",
    "activites": "Trouver des activités",
    "voyage": "Organiser tout le voyage",
}

SECTIONS = {
    "restaurant": 'une section "Restaurants" de 8 adresses',
    "bar": 'une section "Bars" de 8 adresses',
    "logement": 'une section "Hébergements" de 6 adresses',
    "activites": 'une section "Activités" de 8 propositions',
    "voyage": 'quatre sections dans cet ordre : "Hébergement" (3), "Restaurants" (6), '
    '"Bars et bars à vin" (4), "Activités" (6)',
}


class Answer(BaseModel):
    label: str = Field(max_length=60)
    value: str = Field(default="", max_length=1200)


class RecommendRequest(BaseModel):
    mode: str
    answers: List[Answer] = Field(max_length=20)
    refine: Optional[str] = Field(default=None, max_length=400)
    previous: Optional[dict] = None
    access_code: Optional[str] = None


# --- Limite de requêtes par adresse IP (en mémoire) -------------------------
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def check_rate_limit(ip: str) -> None:
    now = time.time()
    q = _hits[ip]
    while q and now - q[0] > 3600:
        q.popleft()
    if len(q) >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(429, "rate_limited")
    q.append(now)


# --- Prompt ------------------------------------------------------------------
def build_prompt(req: RecommendRequest) -> str:
    criteria = "\n".join(
        "- {} : {}".format(a.label, a.value or "non précisé") for a in req.answers
    )
    item = (
        '{"name": string, "area": string (quartier), "kind": string (3 mots max), '
        '"price": "€"|"€€"|"€€€"|"€€€€", "distinction": string (ex. "2 étoiles Michelin", '
        '"Bib Gourmand", ou ""), "sources": string[], "url": string, '
        '"access": "oui"|"partiel"|"non vérifié"|"", '
        '"category": "restaurant"|"bar"|"logement"|"activite"}'
    )
    itinerary = (
        ' "itinerary" : un jour par jour du séjour (7 jours maximum), chaque jour 2 à 4 '
        'éléments courts qui reprennent les adresses proposées (ex. "Matin : …", "Dîner : …"). '
        "Adapte le nombre d'activités par jour au rythme."
        if req.mode == "voyage"
        else ' "itinerary" : tableau vide.'
    )
    prompt = (
        "Tu es Escale, un assistant voyage privé qui répond en français.\n\n"
        "Type de demande : {}\nCritères du client :\n{}\n\n".format(MODES[req.mode], criteria)
        + "Méthode :\n"
        "- Utilise la recherche web pour vérifier que chaque adresse existe, est ouverte "
        "aujourd'hui, et correspond au budget. Consulte en priorité le Guide Michelin "
        "(guide.michelin.com), Le Fooding (lefooding.com), Le Routard (routard.com), "
        "Booking (booking.com) et Airbnb (airbnb.fr), puis les sites officiels.\n"
        "- Ne propose que des établissements réels et actuellement ouverts. En cas de doute, "
        "ne les propose pas.\n\n"
        "Règles de la réponse :\n"
        "- Pas de descriptions : seulement des listes (nom, quartier, type, prix).\n"
        "- Classe chaque liste de la plus adaptée à la moins adaptée au client.\n"
        "- \"sources\" : parmi [\"Guide Michelin\", \"Le Fooding\", \"Le Routard\", "
        "\"Booking\", \"Airbnb\"], seulement celles où ta recherche a confirmé que "
        "l'adresse figure. Tableau vide sinon.\n"
        "- \"url\" : une page trouvée pendant ta recherche (fiche du guide, site officiel ou "
        "page Booking). Jamais une adresse inventée ; \"\" si tu n'en as pas.\n"
        "- Pour un appartement, ne nomme pas une annonce précise : propose une recherche du "
        "type \"Location Airbnb – <quartier>\" avec \"Airbnb\" comme source.\n"
        "- \"access\" : si le client a un besoin d'accessibilité, indique \"oui\", \"partiel\" "
        "ou \"non vérifié\" ; sinon \"\". Privilégie les lieux accessibles et n'affirme "
        "jamais une accessibilité que ta recherche n'a pas confirmée.\n"
        "- Un critère peut contenir plusieurs choix séparés par des virgules : ils sont "
        "tous acceptables pour le client. \"Peu importe\" signifie aucune contrainte.\n"
        "- Tiens compte des précisions libres du client en priorité.\n\n"
    )
    if req.refine and req.previous:
        prompt += (
            "Voici ta proposition précédente :\n"
            + json.dumps(req.previous, ensure_ascii=False)[:12000]
            + "\n\nLe client demande de l'ajuster : « {} ». ".format(req.refine)
            + "Renvoie la proposition complète mise à jour.\n\n"
        )
    prompt += (
        "Ta réponse finale doit être uniquement un objet JSON de cette forme, sans texte "
        "autour :\n"
        '{"summary": string (une phrase), "sections": [{"title": string, "items": ['
        + item
        + ']}], "itinerary": [{"day": string, "items": string[]}], "tips": string[]}\n'
        "Contenu attendu : " + SECTIONS[req.mode] + "." + itinerary
        + ' "tips" : 2 ou 3 conseils pratiques d\'une ligne maximum.'
    )
    return prompt


# --- Appel à Claude ----------------------------------------------------------
def parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start : end + 1])


def ask_claude(prompt: str) -> dict:
    messages = [{"role": "user", "content": prompt}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES}]
    response = None
    for _ in range(5):  # reprises après une pause de la recherche web
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32000,
            betas=["server-side-fallback-2026-07-01"],
            extra_body={"fallbacks": "default"},
            output_config={"effort": "medium"},
            tools=tools,
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
        if response.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": response.content})

    if response is None or response.stop_reason == "refusal":
        raise HTTPException(422, "refused")
    texts = [b.text for b in response.content if b.type == "text"]
    # Le JSON est dans le dernier bloc de texte ; sinon on essaie le texte complet.
    for candidate in (texts[-1:] if texts else []) + ["".join(texts)]:
        try:
            data = parse_json(candidate)
            if isinstance(data.get("sections"), list):
                return data
        except ValueError:
            continue
    raise HTTPException(502, "invalid_json")


# --- Routes ------------------------------------------------------------------
@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def config():
    return {"requiresCode": bool(ACCESS_CODE), "bookingAid": BOOKING_AID}


@app.post("/api/recommend")
def recommend(req: RecommendRequest, request: Request):
    if ACCESS_CODE and req.access_code != ACCESS_CODE:
        raise HTTPException(401, "bad_code")
    if req.mode not in MODES:
        raise HTTPException(400, "bad_mode")
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise HTTPException(503, "not_configured")
    check_rate_limit(request.client.host if request.client else "unknown")
    try:
        return ask_claude(build_prompt(req))
    except anthropic.RateLimitError:
        raise HTTPException(429, "rate_limited")
    except anthropic.APIConnectionError:
        raise HTTPException(503, "upstream_error")
    except anthropic.APIStatusError as e:
        print("Anthropic API error:", e.status_code, e.message)
        raise HTTPException(502, "upstream_error")
