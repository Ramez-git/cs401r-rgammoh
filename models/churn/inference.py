"""SageMaker inference handlers for the portable JSON XGBoost artifact."""
import json
from pathlib import Path
import numpy as np
import xgboost as xgb


def model_fn(model_dir):
    model = xgb.Booster()
    model.load_model(Path(model_dir) / 'model.json')
    return model


def input_fn(body, content_type):
    if content_type != 'application/json':
        raise ValueError('Expected application/json')
    return json.loads(body)


def predict_fn(data, model):
    columns = model.feature_names
    records = data if isinstance(data, list) else [data]
    values = np.array([[record.get(c, float('nan')) for c in columns] for record in records], dtype=float)
    return model.predict(xgb.DMatrix(values, feature_names=columns)).tolist()


def output_fn(predictions, accept):
    if accept != 'application/json':
        raise ValueError('Expected application/json')
    return json.dumps({'churn_probabilities': predictions})
