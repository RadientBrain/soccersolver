#!/usr/bin/env bash
# Run the full data pipeline: scrape → ML → done
# Usage:
#   bash scripts/run_pipeline.sh mock          # use mock data (no scraping)
#   bash scripts/run_pipeline.sh real          # scrape current season from SoFIFA
#   bash scripts/run_pipeline.sh real all      # scrape all 3 seasons

set -e
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

MODE=${1:-mock}
SCOPE=${2:-current}

if [ "$MODE" = "mock" ]; then
  echo -e "${YELLOW}▶ Loading mock data (500 players × 3 seasons)...${NC}"
  python scraper/mock_data_generator.py
  echo -e "${GREEN}✓ Mock data loaded${NC}"

elif [ "$MODE" = "real" ]; then
  if [ "$SCOPE" = "all" ]; then
    SEASONS="2022/23 2023/24 2025/26"
  else
    SEASONS="2025/26"
  fi

  echo -e "${YELLOW}▶ Scraping SoFIFA for: $SEASONS${NC}"
  echo -e "  (This will take ~30–60 min per season with responsible delays)"
  python scraper/sofifa_scraper.py $SEASONS
  echo -e "${GREEN}✓ Scraping complete${NC}"

else
  echo -e "${RED}Usage: bash scripts/run_pipeline.sh [mock|real] [current|all]${NC}"
  exit 1
fi

echo -e "${YELLOW}▶ Running ML pipeline (PCA + K-Means + Similarity)...${NC}"
python pipeline/ml_pipeline.py
echo -e "${GREEN}✓ ML pipeline complete${NC}"

echo ""
echo -e "${GREEN}=== Pipeline done! ===${NC}"
echo "Run tests:    pytest tests/test_integration.py -v"
echo "Start API:    uvicorn api.main:app --port 8000 --reload"
