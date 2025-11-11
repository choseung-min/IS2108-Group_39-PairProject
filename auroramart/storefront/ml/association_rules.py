# storefront/ml/association_rules.py
import pandas as pd
from .loader import load_rules

# Works with mlxtend association_rules DF:
# columns: ['antecedents','consequents','support','confidence','lift', ...]
# antecedents/consequents are frozensets of SKUs (strings)

def get_recommendations(items, metric: str = "lift", top_n: int = 5):
    items = list(dict.fromkeys(items))  # dedupe, preserve order
    rules = load_rules()

    if metric not in rules.columns:
        metric = "confidence" if "confidence" in rules.columns else "lift"

    matched = []
    for sku in items:
        # rules where the sku appears in the antecedents
        mask = rules["antecedents"].apply(lambda fs: sku in fs)
        subset = rules.loc[mask]
        if not subset.empty:
            matched.append(subset)

    if not matched:
        return []

    matched_rules = pd.concat(matched, ignore_index=True)
    top_rules = matched_rules.sort_values(by=metric, ascending=False).head(max(top_n, 10))  # fetch a bit more
    # union all consequents
    reco = []
    seen = set(items)
    for consequents in top_rules["consequents"]:
        for c in consequents:
            if c not in seen:
                seen.add(c)
                reco.append(c)
                if len(reco) >= top_n:
                    return reco
    return reco
