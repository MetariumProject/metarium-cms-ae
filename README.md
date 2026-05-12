# Metarium CMS

A standalone content management system on Google App Engine with substrate-based sr25519 authentication, two-role access control, series-based upload organization, and a semantic graph relationship system.

## Quick Start

### Prerequisites

- Python 3.11+
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud` CLI)
- A GCP project with App Engine enabled

### Local Development

```bash
# Clone and set up
git clone <repo-url>
cd metarium-cms-ae
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# Run locally
export FLASK_APP=main:app
flask run --port=8080
```

The app will be available at `http://localhost:8080`.

### Deploy to App Engine

1. **Create a GCP project** and enable App Engine:

```bash
gcloud projects create YOUR_PROJECT_ID
gcloud app create --project=YOUR_PROJECT_ID --region=us-central
```

2. **Enable required APIs:**

```bash
gcloud services enable appengine.googleapis.com \
  cloudresourcemanager.googleapis.com \
  datastore.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  --project=YOUR_PROJECT_ID
```

3. **Update `app.yaml`** — set `GOOGLE_CLOUD_PROJECT` to your project ID:

```yaml
env_variables:
  GOOGLE_CLOUD_PROJECT: "YOUR_PROJECT_ID"
```

4. **Deploy:**

```bash
gcloud app deploy app.yaml index.yaml --project=YOUR_PROJECT_ID
```

The deploy creates Datastore composite indexes. These take 2-5 minutes to become ready — queries may return errors during that window.

5. **Set the admin key:**

```bash
# Generate a new sr25519 keypair
python setup_admin.py --generate

# Or use an existing SS58 address
python setup_admin.py 5YourSS58AddressHere
```

This writes the admin address to Datastore. The admin can then add scribes via the API.

### Custom Domain

To serve from a custom domain (e.g., `cms.yourdomain.net`):

1. Go to **App Engine > Settings > Custom Domains** in the GCP Console
2. Add your domain and verify ownership
3. Update your DNS with the provided CNAME or A/AAAA records
4. SSL is provisioned automatically by Google

## Usage

Once deployed, the app provides:

| URL | Description |
|-----|-------------|
| `/docs` | API documentation — full reference for all 22 endpoints |
| `/browse` | Browser UI — log in with a Polkadot.js wallet to browse uploads |

### API Documentation

Visit **`/docs`** for the complete API reference. The docs page covers all endpoints with request/response examples, authentication details, and error codes.

### Browser UI

Visit **`/browse`** to use the web interface. Requires the [Polkadot.js browser extension](https://polkadot.js.org/extension/):

1. Install the Polkadot.js extension for [Chrome](https://chrome.google.com/webstore/detail/polkadot%7Bjs%7D-extension/mopnmbcafieddcagagdcbnhejhlodfdd) or [Firefox](https://addons.mozilla.org/en-US/firefox/addon/polkadot-js-extension/)
2. Import or create an account in the extension
3. Navigate to `/browse` and click **Connect Wallet**
4. Select your account and sign the authentication challenge
5. Enter a series name to browse uploads, click any row to view content

The browse UI works for both admin and scribe roles.

### Authentication

All API access requires substrate-based sr25519 authentication:

1. `POST /api/auth/challenge` with your SS58 address
2. Sign the challenge with your sr25519 keypair
3. `POST /api/auth/verify` with the signed message
4. Use the returned access token as `Authorization: Bearer <token>`

Access tokens expire after 1 hour. Use the refresh token (30-day TTL) to get new tokens via `POST /api/auth/refresh`.

### Roles

- **Admin** — full access: manage scribes, upload content, view everything
- **Scribe** — upload content and view everything; cannot manage other scribes

### Running Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

## Architecture

| Component | Details |
|-----------|---------|
| Runtime | Python 3.11 on App Engine Standard (F1 instances, 0-5 auto-scaling) |
| Database | Google Cloud Datastore (NDB) |
| Auth | sr25519 challenge-response with blake3-hashed tokens |
| Uploads | Series-based with transactional monotonic IDs, immutable (no deletion) |
| Graph | 62 semantic predicates across 10 namespaces with soft-delete |
