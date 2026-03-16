#!/bin/bash
# SoccerSolver — quick setup script
# Run from the project root: bash scripts/setup.sh

set -e
echo "🚀 SoccerSolver setup"

# 1. Copy env
if [ ! -f .env ]; then
  cp .env.example .env
  echo "✓ Created .env from .env.example"
fi

# 2. Start database
echo "📦 Starting database..."
docker-compose up db -d
echo "  Waiting for database to be ready..."
until docker-compose exec -T db pg_isready -U soccer -d soccersolver > /dev/null 2>&1; do
  sleep 2
done
echo "✓ Database ready"

# 3. Python deps
echo "🐍 Installing Python dependencies..."
python3.11 -m pip install -r api/requirements.txt 
python3.11 -m pip install -r scraper/requirements.txt 
echo "✓ Python dependencies installed"

# 4. Generate mock data
echo "🎲 Scrapping real player data (500 players × 3 seasons)..."
python3.11 scraper/sofifa_scraper.py --season '2025/26'
echo "✓ Real data saved to database"

# 5. Run ML pipeline
echo "🧠 Running ML pipeline (PCA → K-Means → similarity → uniqueness)..."
python3.11 pipeline/ml_pipeline.py
echo "✓ ML pipeline complete"

# 6. Start API
echo "⚡ Starting FastAPI..."
cd api && uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!
cd ..
sleep 3
echo "✓ API running at http://localhost:8000"
echo "  API docs at http://localhost:8000/docs"

# 7. Frontend
echo "🎨 Installing frontend dependencies..."
cd frontend && npm install
echo "✓ Frontend ready"
echo ""
echo "=== Setup complete! ==="
echo ""
echo "To start the frontend:"
echo "  cd frontend && npm run dev"
echo ""
echo "Then open http://localhost:3000"
echo ""
echo "To run tests:"
echo "  cd tests && pytest test_integration.py -v"
echo ""
echo "To scrape real SoFIFA data (after installing playwright):"
echo "  playwright install chromium"
echo "  python3.11 scraper/sofifa_scraper.py '2025/26'"
