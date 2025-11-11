import pandas as pd

from .loader import load_classifier

def predict_preferred_category(customer_data):
    model = load_classifier()
    
    columns = {
        'age':'int64', 'household_size':'int64', 'has_children':'int64', 'monthly_income_sgd':'float64',
        'gender_Female':'bool', 'gender_Male':'bool', 'employment_status_Full-time':'bool',
        'employment_status_Part-time':'bool', 'employment_status_Retired':'bool',
        'employment_status_Self-employed':'bool', 'employment_status_Student':'bool',
        'occupation_Admin':'bool', 'occupation_Education':'bool', 'occupation_Sales':'bool',
        'occupation_Service':'bool', 'occupation_Skilled Trades':'bool', 'occupation_Tech':'bool',
        'education_Bachelor':'bool', 'education_Diploma':'bool', 'education_Doctorate':'bool',
        'education_Master':'bool', 'education_Secondary':'bool'
    }

    df = pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in columns.items()})
    customer_df = pd.DataFrame([customer_data])
    customer_encoded = pd.get_dummies(customer_df, columns=['gender', 'employment_status', 'occupation', 'education'])    

    for col in df.columns:

        if col not in customer_encoded.columns:

            # Use False for bool columns, 0 for numeric
            if df[col].dtype == bool:
                df[col] = False
            else:
                df[col] = 0
        
        else:

            df[col] = customer_encoded[col]
    
    # Now input_encoded can be used for prediction
    prediction = model.predict(df)    

    return prediction