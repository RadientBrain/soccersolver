.PHONY: up down db mock pipeline api frontend test clean

# ── Docker ─────────────────────────────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

db:
	docker compose up -d db

# ── Data ───────────────────────────────────────────────────────────────────────
mock:
	python scraper/mock_data_generator.py

scrape:
	python scraper/sofifa_scraper.py 2025/26

scrape-all:
	python scraper/sofifa_scraper.py 2022/23 2023/24 2025/26

pipeline:
	python pipeline/ml_pipeline.py

# ── Services ───────────────────────────────────────────────────────────────────
api:
	uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev

# ── Tests ──────────────────────────────────────────────────────────────────────
test:
	pytest tests/test_integration.py -v

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	pip install -r api/requirements.txt
	pip install -r scraper/requirements.txt
	playwright install chromium --with-deps
	cd frontend && npm install

setup: db
	sleep 5
	$(MAKE) install
	$(MAKE) mock
	$(MAKE) pipeline

# ── Clean ──────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
