# Deployment Guide

This guide provides step-by-step instructions to deploy **InsureRoute** using Google Cloud Serverless technologies. This ensures maximum scalability, high availability, and zero-maintenance infrastructure.

---

## 1. Prerequisites

Before you begin, ensure you have the following:

- A [Google Cloud Platform (GCP)](https://cloud.google.com/) account.
- The [Google Cloud CLI (`gcloud`)](https://cloud.google.com/sdk/docs/install) installed and authenticated.
- API Keys:
  - **OpenWeatherMap API Key** (Free tier)
  - **Google Gemini API Key** (Google AI Studio)
  - **NewsData.io API Key** (Free tier)

Authenticate your GCP account:
```bash
gcloud auth login
gcloud config set project [YOUR-PROJECT-ID]
```

---

## 2. Deploying the Backend (Google Cloud Run)

We use Google Cloud Run to host our FastAPI backend. It automatically builds a container from the source code and scales it to zero when not in use, ensuring you only pay for what you use.

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```

2. Deploy directly from source using Google Cloud Build:
   ```bash
   gcloud run deploy insureroute-backend \
     --source . \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars="OPENWEATHER_API_KEY=your_key,GEMINI_API_KEY=your_key"
   ```

3. Once deployed, `gcloud` will output a Service URL (e.g., `https://insureroute-backend-xyz.run.app`). Copy this URL.

---

## 3. Deploying the Frontend (Google Cloud Run or Firebase Hosting)

You can deploy the React frontend to either Cloud Run (containerized) or Firebase Hosting (static edge delivery). Below is the Cloud Run method for consistency.

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Update your API configuration:
   Ensure your frontend API calls point to the new backend URL generated in Step 2. You may need to create a `.env.production` file:
   ```env
   VITE_API_URL=https://insureroute-backend-xyz.run.app
   ```

3. Deploy the frontend:
   ```bash
   gcloud run deploy insureroute-frontend \
     --source . \
     --region us-central1 \
     --allow-unauthenticated
   ```

4. Once finished, Cloud Run will output the final public URL for your dashboard.

---

## 4. Why Google Cloud Serverless?

By deploying InsureRoute to Google Cloud Run, we achieve:
- **Zero Server Management:** No need to provision or manage VMs.
- **Auto-Scaling:** Instantly handles traffic spikes during critical supply chain events and scales to zero to save costs.
- **Security:** Endpoints are automatically secured with HTTPS.

You are now ready to monitor and manage global supply chain risks in real-time!