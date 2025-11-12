import joblib
from .loader import load_rules
# load the rules from the file in joblib format

# use the loaded_rules to extract recommendations
def get_recommendations(items, metric='confidence', top_n=5):
    loaded_rules = load_rules()
    recommendations = set()

    for item in items:

        # Find rules where the item is in the antecedents
        matched_rules = loaded_rules[loaded_rules['antecedents'].apply(lambda x: item in x)]
        # Sort by the specified metric and get the top N
        top_rules = matched_rules.sort_values(by=metric, ascending=False).head(top_n)

        for _, row in top_rules.iterrows():

            recommendations.update(row['consequents'])

    # Remove items that are already in the input list
    recommendations.difference_update(items)
    
    return list(recommendations)[:top_n]