# ShopSight 🔍 — Live AI Price Hunter

Watch a real browser navigate Indian shopping sites live on your screen. ShopSight opens Chrome, visits Amazon.in, Flipkart, and Reliance Digital one by one, scrapes prices directly from the page, and shows you the best deal — no API keys, no cost, just pure browser automation.

---

## How It Works

1. Type a product name → agent launches a real visible Chrome window
2. Browser visits Amazon.in, Flipkart, and Reliance Digital live on your screen
3. Prices, ratings, and delivery info are scraped directly from the HTML
4. Best deal is highlighted instantly on the website

---

## Run Locally

### Prerequisites

- Python 3.10+
- No API keys needed

### Setup

```bash
# Install dependencies
pip install -r backend/requirements.txt --timeout 120

# Install browser
python -m playwright install chromium

# Run the server from the project root
python backend/run.py
```

### Open the UI

Open `http://127.0.0.1:8000` in your browser. The backend serves the frontend and the WebSocket endpoint.

### Frontend development

The frontend is now a React/Vite application. Run the backend in one terminal, then run the frontend in another:

```bash
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`.

---

## Deploy to Google Cloud Run

```bash
gcloud run deploy shopsight \
  --source . \
  --port 8080 \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2
```

After deploy, update the `WS` variable in `index.html`:

```js
const WS = "wss://YOUR-CLOUD-RUN-URL/ws/search";
```

---

## Project Structure

```
shopsight/
├── backend/
│   ├── agent.py          # Browser automation + scraping logic
│   ├── main.py           # FastAPI + WebSocket server
│   ├── run.py            # Windows-compatible server launcher
│   └── requirements.txt  # Python dependencies
├── frontend/
│   └── index.html        # Frontend UI
├── docs/
│   └── README.md         # Project documentation
├── presentations/        # Project presentation files
└── .env                 # Environment config
```

---

## Tech Stack

| Layer               | Technology            |
| ------------------- | --------------------- |
| Browser Automation  | Playwright + Chromium |
| Real-time Streaming | WebSockets            |
| Backend             | FastAPI + Uvicorn     |
| Frontend            | Vanilla HTML/CSS/JS   |
| Cloud               | Google Cloud Run      |

---

## Shops Supported

| Shop      | Region |
| --------- | ------ |
| Amazon.in | India  |
| Flipkart  | India  |
| Reliance Digital | India  |
