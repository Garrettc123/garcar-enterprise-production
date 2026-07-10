import pandas as pd
import joblib

model = joblib.load('churn_model.pkl')

customers = pd.DataFrame({
    'id': [1,2,3],
    'tenure': [10, 25, 5],
    'usage': [150, 250, 30]
})

customers['churn_prob'] = model.predict_proba(customers[['tenure', 'usage']])[:,1]
print('High-risk customers:', customers[customers['churn_prob'] > 0.5])

revenue = len(customers) * 99
print('Monthly MRR:', revenue)
print('Revenue loop active - ready for immediate billing.')