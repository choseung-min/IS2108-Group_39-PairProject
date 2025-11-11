# storefront/ml/loader.py
from functools import lru_cache
from pathlib import Path
import joblib

BASE = Path(__file__).resolve().parent.parent / "mlmodels"

@lru_cache(maxsize=1)
def load_classifier():
    return joblib.load(BASE / "b2c_customers_100.joblib")

@lru_cache(maxsize=1)
def load_rules():
    return joblib.load(BASE / "b2c_products_500_transactions_50k.joblib")
