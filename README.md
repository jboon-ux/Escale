# Escale — assistant voyage privé

Site web où le client décrit sa demande (restaurant, bar, logement ou voyage complet),
répond à quelques questions, puis reçoit des listes d'adresses vérifiées en direct
sur le web : Guide Michelin, Le Fooding, Le Routard, Booking, Airbnb et sites officiels.

## Ce qu'il y a dans ce dossier

| Fichier | Rôle |
|---|---|
| `app.py` | Le serveur : reçoit la demande, interroge Claude avec la recherche web, renvoie les listes |
| `static/index.html` | L'interface que voient les clients |
| `requirements.txt` | Les bibliothèques Python nécessaires |
| `.env.example` | Le modèle des réglages (clé API, code d'accès, identifiant Booking) |
| `render.yaml` | La configuration pour mettre le site en ligne sur Render |

## 1. Obtenir une clé API Claude

1. Créez un compte sur https://console.anthropic.com/
2. Ajoutez un moyen de paiement (l'API est facturée à l'usage : chaque recherche consomme des tokens et des recherches web).
3. Dans **API Keys**, créez une clé et copiez-la.

Conseil : dans la console, fixez une **limite de dépenses mensuelle** pour éviter les surprises.

## 2. Tester sur votre ordinateur

Il faut Python 3.10 ou plus récent (https://www.python.org/downloads/).

```bash
cd escale-app
cp .env.example .env
```

Ouvrez `.env` et collez votre clé après `ANTHROPIC_API_KEY=`. Puis :

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app:app --reload
```

Ouvrez http://localhost:8000 dans votre navigateur.

## 3. Mettre le site en ligne (Render)

1. Créez un compte gratuit sur https://github.com et déposez-y ce dossier (bouton **Add file › Upload files**). Ne déposez jamais le fichier `.env`.
2. Créez un compte sur https://render.com et connectez-le à GitHub.
3. **New › Blueprint**, choisissez votre dépôt : Render lit `render.yaml` et prépare le site.
4. Quand Render le demande, collez votre clé dans `ANTHROPIC_API_KEY`.
5. Au bout de quelques minutes, le site est en ligne à une adresse du type `https://escale.onrender.com`.

Le plan gratuit met le site en veille après 15 minutes sans visite : la première visite suivante prend environ une minute. Pour un site toujours prêt, passez au plan payant dans Render.

## 4. Votre propre nom de domaine

1. Achetez un domaine (par exemple `escale-voyage.fr`) chez un registraire comme OVH, Gandi ou Namecheap.
2. Dans Render : **Settings › Custom Domains › Add**, puis suivez les instructions DNS affichées.

## 5. Réglages utiles

| Réglage | Effet |
|---|---|
| `ESCALE_ACCESS_CODE` | Si rempli, les visiteurs doivent saisir ce code. Utile pendant les tests, pour que des inconnus ne consomment pas votre crédit API |
| `BOOKING_AFFILIATE_ID` | Votre identifiant du programme partenaire Booking : il est ajouté aux liens Booking, ce qui vous permet de toucher une commission |
| `ESCALE_RATE_LIMIT_PER_HOUR` | Nombre maximum de recherches par visiteur et par heure (12 par défaut) |
| `ESCALE_MAX_WEB_SEARCHES` | Nombre maximum de recherches web par demande (8 par défaut) : moins = plus rapide et moins cher |

## Sources : ce qui est branché, ce qui reste à faire

- **Recherche web en direct (branchée)** : pour chaque demande, Claude cherche sur le web et vérifie que les adresses existent et sont ouvertes. Il consulte en priorité les sites du Michelin, du Fooding, du Routard, de Booking et d'Airbnb.
- **Booking** : l'identifiant partenaire est pris en charge dans les liens. Pour les prix et les disponibilités en temps réel, il faut l'API Booking (Demand API), réservée aux partenaires acceptés : inscrivez-vous au programme partenaire de Booking. Une fois l'accès obtenu, on pourra la brancher.
- **Airbnb** : pas d'API publique. Le site propose des liens de recherche Airbnb par quartier.
- **Michelin, Le Fooding, Le Routard** : pas d'API publique. Leurs pages sont consultées via la recherche web ; reprendre leurs contenus (textes, notes) nécessiterait un accord de licence avec chaque éditeur.
