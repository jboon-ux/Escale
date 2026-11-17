# Escale - assistant voyage

Application FastAPI en français : restaurants, bars, hébergements, activités et idées de voyage.

## Architecture gratuite

- **Tavily Researcher** : recherche web, 1 000 crédits gratuits par mois. Une demande simple utilise une recherche basic (1 crédit), un voyage complet quatre (4 crédits). Les affinages relancent les recherches.
- **Groq Free** : synthèse avec `openai/gpt-oss-120b`, sortie JSON. Les limites du compte et du modèle s'appliquent.
- **Render Free** : serveur Python. Mise en veille après 15 minutes sans visite et réveil parfois lent.

Aucune carte ni facturation n'est nécessaire pour cette configuration. Ne pas activer pay-as-you-go, auto-upgrade ou un plan payant. Les API arrêtent les requêtes aux limites gratuites. Le code ne propose aucun fallback payant, ni relance automatique cachée.

Les offres et quotas peuvent changer. Cette version n'offre aucune garantie de service. Les sources web ne garantissent ni horaires, ni prix, ni disponibilités : vérifier auprès des établissements avant de réserver. Les indications d'accessibilité restent non vérifiées. Les liens renvoyés par l'IA sont conservés uniquement s'ils figurent dans les résultats Tavily. Les listes peuvent être plus courtes que demandé si les sources manquent.

## Confidentialité

Les critères saisis sont transmis à Tavily puis Groq pour produire la sélection. Ne pas saisir d'informations sensibles, confidentielles ou personnelles. Les clés API restent uniquement dans les variables serveur, jamais dans GitHub ou le navigateur. Aucun historique de recherche n'est stocké côté serveur par cette app. Les fournisseurs appliquent leurs propres conditions et règles de conservation.

## Lancer en local

Python 3.10 ou plus récent :

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Remplir GROQ_API_KEY et TAVILY_API_KEY dans .env, sans le publier.
.venv/bin/uvicorn app:app --reload
```

Ouvrir http://localhost:8000.

## Déployer sur Render

Créer un Web Service Python depuis ce dépôt. Choisir explicitement le plan **Free**.

- Build : `pip install -r requirements.txt`
- Start : `uvicorn app:app --host 0.0.0.0 --port $PORT`
- Secrets : `GROQ_API_KEY`, `TAVILY_API_KEY`
- Facultatif : `ESCALE_ACCESS_CODE` pour limiter les visiteurs, `ESCALE_RATE_LIMIT_PER_HOUR` (12 par IP par défaut), `BOOKING_AFFILIATE_ID`.

Le fichier `render.yaml` fournit les mêmes réglages. Aucun disque ni base de données payants n'est nécessaire. Les limites de débit locales sont en mémoire et sont remises à zéro à chaque redémarrage. Elles ne remplacent pas les plafonds des fournisseurs. Un dépôt public importé par URL peut nécessiter un déploiement manuel après les futurs commits.

## Sources fournisseurs

- https://www.tavily.com/pricing
- https://help.tavily.com/articles/8298987937-billing-credits-usage-limits
- https://console.groq.com/docs/rate-limits
- https://console.groq.com/docs/billing-faqs
- https://render.com/docs/free
