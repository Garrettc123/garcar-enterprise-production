import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
import joblib

data = pd.DataFrame({
    'tenure': [12, 24, 6, 36, 3],
    'usage': [100, 200, 50, 300, 20],
    'churn': [0, 0, 1, 0, 1]
})

X = data[['tenure', 'usage']]
y = data['churn']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
model = LogisticRegression().fit(X_train, y_train)
print('Accuracy:', accuracy_score(y_test, model.predict(X_test)))

joblib.dump(model, 'churn_model.pkl')
print('Churn model ready for revenue ops.')