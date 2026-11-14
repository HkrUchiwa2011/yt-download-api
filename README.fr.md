# yt-download-api

[English](README.md) | [Français](README.fr.md)

[![Licence](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg)

Une API YouTube à héberger soi-même, basée sur FastAPI, yt-dlp, FFmpeg et Redis.
Soumettez une vidéo, consultez son état, puis récupérez le fichier. Les routes HTTP
restent compatibles avec le client Python [yt-download-client](https://github.com/HkrUchiwa2011/yt-download-client).

Cette page est la traduction du [README anglais](README.md), qui sert de référence.

## Démarrer avec Docker Compose

```bash
git clone https://github.com/HkrUchiwa2011/yt-download-api.git
cd yt-download-api
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Placez le secret généré dans `.env`, comme valeur de `API_KEY`. La valeur
d'exemple est refusée au démarrage. Lancez ensuite :

```bash
docker compose up --build -d
```

L'image fournie compile une version limitée de FFmpeg 9.0.2 avec des corrections
de sécurité ciblées et met à jour le parseur XML intégré à Python. Les sources
sont vérifiées par leur empreinte ; les étapes de compilation sont exclues de
l'image finale. Consultez les [détails de compilation native](build/README.md).

L'API écoute sur **http://127.0.0.1:8000**. Redis reste interne à Compose : son
port n'est pas publié. L'API et le processus de téléchargement partagent un
volume de fichiers ; Redis utilise un journal persistant. Pour ajouter des
processus de téléchargement :

```bash
docker compose up -d --scale worker=3
```

`MAX_CONCURRENT_DOWNLOADS` limite tous les téléchargements acceptés, y compris
ceux qui attendent un processus disponible, entre les différents processus de
l'API. Lorsque la capacité est atteinte, le service répond `503` avec
`Retry-After`, sans créer de tâche. L'espace disque est réservé avec une marge
pour les téléchargements et leur traitement.

Pour un accès distant, exposez l'API derrière un proxy inverse HTTPS. La
configuration fournie écoute sur localhost. Les en-têtes transmettant l'adresse
IP du client sont ignorés ; les clients derrière un proxy partagent donc son
quota par IP. Adaptez les limites à ce déploiement.

## Démarrer sans Docker

Installez Python 3.11+, Redis, FFmpeg/ffprobe et [uv](https://docs.astral.sh/uv/).
Les dépendances Python, dont Deno et le composant EJS de yt-dlp, sont verrouillées
dans `uv.lock`. Sans Docker, utilisez les paquets natifs corrigés de votre
environnement ; la revue de l'image fournie ne certifie pas une autre installation.

```bash
uv sync --locked --no-dev
uv run --locked --no-dev python -m app.server
```

Le serveur lance l'API et un processus de téléchargement supervisé. Pour les
séparer, avec le **même système de fichiers**, définissez `EMBEDDED_WORKERS=0`
puis lancez :

```bash
uv run --locked --no-dev python -m app.worker
uv run --locked --no-dev python -m app.server
```

Vous pouvez aussi installer les dépendances verrouillées avec
`pip install --require-hashes -r requirements.txt`. Ce fichier est généré à partir
de `uv.lock`.

## API HTTP

Toutes les routes sauf `/health` nécessitent l'en-tête `X-API-Key`. Une clé
absente ou incorrecte entraîne une réponse `401`.

| Méthode | Route | Comportement |
|---|---|---|
| GET | `/health` | Vérifie Redis et les processus de téléchargement enregistrés ; répond 503 si indisponibles |
| GET | `/info?url=...` | Métadonnées de la vidéo, avec un délai d'extraction limité |
| POST | `/download` | Met le téléchargement en file persistante et renvoie son UUID |
| GET | `/status/{job_id}` | État de la tâche, avec un quota de consultation indépendant |
| GET | `/file/{job_id}` | Récupère un fichier terminé sans le supprimer |
| DELETE | `/file/{job_id}` | Supprime un fichier terminé ; une tâche active entraîne une réponse 409 |

Formats : `mp4`, `mp3`, `webm`. Qualités : `best`, `1080p`, `720p`, `480p`,
`360p`, `audio_only`. MP3 sélectionne toujours les pistes audio ; `audio_only`
nécessite MP3. MP4 et WebM sélectionnent des pistes compatibles avec le conteneur
demandé. Si aucune piste compatible n'est disponible, la tâche échoue.

Les URL doivent utiliser HTTPS et un domaine YouTube accepté, avec un identifiant
vidéo de 11 caractères. Les liens watch, shorts, embed et live sont normalisés en
une URL watch. Les paramètres de playlist et les autres paramètres sont retirés.
Les téléchargements en direct ou de durée inconnue sont refusés ; `/info` peut
renvoyer `duration: null`.

```bash
curl --fail http://localhost:8000/download \
  -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' \
  -d '{"url":"https://youtu.be/aqz-KE-bpKQ","format":"mp4","quality":"720p"}'
```

La réponse contient `job_id`, `status: "pending"` et un message. L'état initial
et l'entrée dans la file sont enregistrés ensemble. La tâche suit les états
`pending` → `started` → `progress` → `post_processing` → `success` / `failure`.

Les fichiers restent disponibles pendant `FILE_TTL_MINUTES` après la fin du téléchargement,
sauf suppression explicite. Le nettoyage des fichiers expirés s'effectue chaque
minute. Un client déconnecté peut récupérer le fichier à nouveau. Les requêtes
HTTP pour une seule plage d'octets et `If-Range` sont acceptées ; les plages
multiples sont refusées. Les tâches en attente survivent aux redémarrages tant
que leur délai dans la file n'a pas expiré. Les tâches interrompues pendant leur
exécution échouent ; les téléchargements partiels ne reprennent pas
automatiquement. Après un arrêt brutal, RQ détecte les tâches abandonnées lors
de sa maintenance périodique, pas instantanément.

## Client Python

```python
from yt_download_client import YTDownloadClient

with YTDownloadClient("http://localhost:8000", api_key="YOUR_KEY") as client:
    path = client.download("https://youtu.be/aqz-KE-bpKQ", format="mp4", quality="720p")
```

Le client gère la consultation de l'état et les tentatives supplémentaires
limitées pour les requêtes GET. La soumission n'est jamais répétée automatiquement,
pour éviter de créer plusieurs tâches.

## Webhooks

Les webhooks sont désactivés par défaut. Configurez ces deux variables :

```dotenv
WEBHOOK_ALLOWED_HOSTS=["callbacks.example.org"]
WEBHOOK_SECRET=YOUR_RANDOM_SECRET_OF_AT_LEAST_32_CHARACTERS
```

Soumettez `webhook_url: "https://callbacks.example.org/download-finished"`.
Seuls les domaines exacts autorisés, en HTTPS sur le port 443, sont acceptés.
Le DNS doit renvoyer uniquement des adresses IP publiques. La connexion utilise
une IP vérifiée tout en contrôlant le certificat TLS du domaine d'origine ;
les redirections et les proxies d'environnement sont désactivés. Les erreurs
réseau et les réponses HTTP 5xx entraînent au maximum trois tentatives.
L'échec de livraison ne modifie pas un téléchargement terminé.

Le message contient `job_id`, `status` et les champs publics du résultat ou de
l'erreur, sans nom de fichier local ni chemin. Vérifiez `X-YT-Signature` :
`sha256=` suivi du HMAC-SHA256 de `timestamp + "." + raw_request_body`, calculé
avec `WEBHOOK_SECRET`. Le timestamp se trouve dans `X-YT-Timestamp`. Comparez
les signatures en temps constant et refusez les messages trop anciens ou déjà
reçus sur le service destinataire.

## Configuration

Toutes les valeurs sont des variables d'environnement ; voir `.env.example`.

| Variable | Valeur par défaut | Rôle |
|---|---|---|
| `API_KEY` | obligatoire | Secret aléatoire d'au moins 32 caractères |
| `REDIS_URL` | `redis://localhost:6379/0` | Connexion à un Redis privé ; utiliser TLS pour un Redis distant |
| `REDIS_NAMESPACE` | `yt` | Isole les tâches et les compteurs de ce déploiement |
| `TMP_DIR` | `/tmp/yt-downloads` | Répertoire dédié appartenant au compte du service |
| `FILE_TTL_MINUTES` | 30 | Conservation des fichiers et des états terminaux |
| `MAX_DURATION_SECONDS` | 3600 | Durée maximale connue d'une vidéo |
| `MAX_FILESIZE_MB` | 500 | Limite de la taille cumulée des sources et de celle du fichier final |
| `MIN_FREE_SPACE_MB` | 256 | Marge de sécurité sur l'espace disque |
| `JOB_TIMEOUT_SECONDS` | 900 | Délai dans la file et délai d'exécution, appliqués séparément |
| `SOCKET_TIMEOUT_SECONDS` | 15 | Délai réseau ; l'extraction des métadonnées est limitée à trois fois cette valeur |
| `MAX_CONCURRENT_DOWNLOADS` | 5 | Nombre maximal global de téléchargements acceptés |
| `MAX_CONCURRENT_INFO_REQUESTS` | 2 | Nombre maximal global d'extractions de métadonnées simultanées |
| `RATE_LIMIT_PER_MINUTE_IP` / `RATE_LIMIT_PER_MINUTE_KEY` | 10 / 30 | Quotas des requêtes de travail |
| `STATUS_RATE_LIMIT_PER_MINUTE_IP` / `STATUS_RATE_LIMIT_PER_MINUTE_KEY` | 120 / 300 | Quotas distincts de consultation de l'état |
| `EMBEDDED_WORKERS` | 1 | Processus supervisés par `app.server` ; Compose impose zéro |
| `ENABLE_DOCS` | false | Active `/docs` et `/openapi.json` |
| `PROXY_URL` | vide | Proxy yt-dlp configuré par l'opérateur ; garder ses identifiants secrets |
| `WEBHOOK_ALLOWED_HOSTS` / `WEBHOOK_SECRET` | désactivés | Domaines de callback autorisés et secret HMAC |

Redis et le répertoire partagé de téléchargement sont des composants de confiance.
Les utilisateurs de la même clé API peuvent accéder à toutes les tâches ; cette
API ne fournit pas de comptes utilisateurs ni d'isolation entre utilisateurs.
N'exposez pas Redis ou le volume de téléchargement publiquement. Les contrôles
réseau sortants de l'hôte peuvent renforcer l'isolation de yt-dlp/FFmpeg et d'un
éventuel proxy. YouTube peut refuser les IP de centres de données même avec des
dépendances à jour.

## Render

`render.yaml` utilise un service web payant avec disque persistant et un service
Key Value payant. Un processus de téléchargement est supervisé dans le service
web, car des services Render distincts ne peuvent pas partager ce disque.
La configuration limite les fichiers à 100 Mo et accepte deux tâches simultanées.
Vérifiez la disponibilité, les tarifs et les permissions du disque avant de
déployer. Les tests locaux ne déploient rien. L'ancienne configuration gratuite
ne fournissait pas de stockage durable pour les fichiers.

## Vérifications locales

Utilisez un Redis de test isolé ; les tests nettoient uniquement leurs propres
données, identifiées par un espace de noms :

```bash
docker run --rm -p 127.0.0.1:16379:6379 redis:8-alpine
# In a second terminal:
uv sync --locked
TEST_REDIS_URL=redis://127.0.0.1:16379/15 uv run --locked pytest
uv run --locked ruff check app tests
uv run --locked ruff format --check app tests
uv run --locked pip-audit
```

Les tests d'intégration multimédia nécessitent aussi FFmpeg/ffprobe. La cible
Docker `tests` vérifie les bibliothèques natives corrigées utilisées en production ;
ses commandes figurent dans les [détails de compilation native](build/README.md).
Sans `TEST_REDIS_URL`, les tests Redis sont explicitement ignorés ; les tests
unitaires de validation et de sécurité restent exécutés. Consultez
[SECURITY_REVIEW.md](SECURITY_REVIEW.md) pour le périmètre et les résultats de la
revue locale, et [CHANGELOG.md](CHANGELOG.md) pour les notes de migration.

## Maintenance

GitHub Actions vérifie les pull requests et lance un audit hebdomadaire.
Dependabot propose les mises à jour chaque semaine ; leur fusion et la publication
des versions restent manuelles. Consultez [MAINTENANCE.md](MAINTENANCE.md), en anglais,
pour les horaires, les contrôles de sécurité et la mise à jour des composants natifs.

## Licence

Le code de l'application est sous [licence MIT](LICENSE). FFmpeg, Expat et les
autres composants intégrés conservent leurs licences respectives ; voir les
[détails de compilation native](build/README.md).
Téléchargez uniquement les contenus que vous avez le droit de télécharger.
