import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()


def _opt_date(value):
    return date.fromisoformat(value) if value else None


class Config:
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost:5432/retail_forecaster')
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    DEBUG = FLASK_ENV == 'development'

    # --- Data window (ADR-0003). Favorita promotions are unrecorded before 2014-04-01;
    # the synthetic dataset has no gap, so set TRAINING_START_DATE= (empty) to use all history.
    TRAINING_START_DATE = _opt_date(os.getenv('TRAINING_START_DATE', '2014-04-01'))

    # --- Horizon (ADR-0005)
    MAX_FORECAST_DAYS = int(os.getenv('MAX_FORECAST_DAYS', 90))
    HORIZON_BUCKETS = ((1, 7), (8, 30), (31, 90))

    # --- Rolling CV (ADR-0005, ADR-0007)
    CV_INITIAL_DAYS = int(os.getenv('CV_INITIAL_DAYS', 365))
    CV_PERIOD_DAYS = int(os.getenv('CV_PERIOD_DAYS', 60))
    N_TEST_FOLDS = int(os.getenv('N_TEST_FOLDS', 3))
    MIN_SELECTION_FOLDS = int(os.getenv('MIN_SELECTION_FOLDS', 3))

    # --- Ablation (ADR-0007)
    ABLATION_MIN_REL_GAIN = float(os.getenv('ABLATION_MIN_REL_GAIN', 0.02))
    ABLATION_MIN_FOLD_WIN_SHARE = float(os.getenv('ABLATION_MIN_FOLD_WIN_SHARE', 2 / 3))

    # --- Verdicts (ADR-0012)
    VERDICT_SKILL_THRESHOLD = float(os.getenv('VERDICT_SKILL_THRESHOLD', 0.05))
    VERDICT_MIN_FOLD_SHARE = float(os.getenv('VERDICT_MIN_FOLD_SHARE', 2 / 3))

    # --- Sample paths / inventory (ADR-0008)
    UNCERTAINTY_SAMPLES = int(os.getenv('UNCERTAINTY_SAMPLES', 1000))
    DEFAULT_LEAD_TIME = int(os.getenv('DEFAULT_LEAD_TIME', 7))
    DEFAULT_SERVICE_LEVEL = float(os.getenv('DEFAULT_SERVICE_LEVEL', 0.95))
    MAX_LEAD_TIME = 90

    # --- Persistence (ADR-0010)
    KEEP_FORECAST_RUNS = int(os.getenv('KEEP_FORECAST_RUNS', 5))
    FORECAST_SEED = int(os.getenv('FORECAST_SEED', 42))
