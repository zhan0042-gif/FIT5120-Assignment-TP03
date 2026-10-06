import os
from pathlib import Path

import joblib
import pandas as pd
import pymysql

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from sklearn.tree import DecisionTreeClassifier


MODEL_DIR = Path("backend/models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODEL_DIR / "fdr_model.joblib"


def get_connection():
    """
    Create a MySQL connection for loading the cleaned FDR dataset.

    Returns:
        pymysql.connections.Connection:
            Active MySQL connection.
    """
    return pymysql.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_EXPOSED_PORT", "3307")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
    )


def load_training_data():
    """
    Load cleaned AFDRS history from MySQL.

    Only issued ratings are loaded. rating_code = 0 represents
    "No rating" and is excluded from model training.

    Returns:
        pandas.DataFrame:
            Cleaned FDR records used for model training.
    """
    connection = get_connection()

    try:
        query = """
            SELECT
                date,
                district,
                month,
                day_of_year,
                rating_code
            FROM open_data_fdr_history
            WHERE rating_code > 0
            ORDER BY date, district
        """

        return pd.read_sql(query, connection)

    finally:
        connection.close()


def prepare_data(df):
    """
    Prepare features and binary target.

    Target:
        0 = Moderate
        1 = Elevated (High, Extreme, Catastrophic)

    Date is retained temporarily so that the chronological
    train/test split can be created.

    Args:
        df:
            Cleaned FDR DataFrame.

    Returns:
        tuple:
            Feature DataFrame and target Series.
    """
    df = df.copy()

    df["date"] = pd.to_datetime(df["date"])

    # Moderate = 0
    # High / Extreme / Catastrophic = 1
    df["target"] = (df["rating_code"] >= 2).astype(int)

    X = df[
        [
            "date",
            "district",
            "month",
            "day_of_year",
        ]
    ]

    y = df["target"]

    return X, y


def chronological_split(X, y, test_fraction=0.20):
    """
    Split the dataset chronologically.

    Earlier dates are used for training and the latest dates
    are reserved for testing.

    The split is based on unique dates rather than raw row count,
    so all districts for the same date remain together.

    Args:
        X:
            Feature DataFrame containing a date column.
        y:
            Target Series.
        test_fraction:
            Fraction of unique dates reserved for testing.

    Returns:
        tuple:
            X_train, X_test, y_train, y_test.
    """
    unique_dates = sorted(X["date"].unique())

    split_index = int(len(unique_dates) * (1 - test_fraction))

    train_dates = unique_dates[:split_index]
    test_dates = unique_dates[split_index:]

    train_mask = X["date"].isin(train_dates)
    test_mask = X["date"].isin(test_dates)

    X_train = X.loc[train_mask].copy()
    X_test = X.loc[test_mask].copy()

    y_train = y.loc[train_mask].copy()
    y_test = y.loc[test_mask].copy()

    print(
        "\nTraining date range:",
        X_train["date"].min().date(),
        "to",
        X_train["date"].max().date(),
    )

    print(
        "Testing date range :",
        X_test["date"].min().date(),
        "to",
        X_test["date"].max().date(),
    )

    print(f"\nTraining rows: {len(X_train)}")
    print(f"Testing rows : {len(X_test)}")

    print("\nTraining target distribution:")
    print(y_train.value_counts().sort_index())

    print("\nTesting target distribution:")
    print(y_test.value_counts().sort_index())

    # Date is only used for chronological splitting.
    # It is not supplied to the models.
    X_train = X_train.drop(columns=["date"])
    X_test = X_test.drop(columns=["date"])

    return X_train, X_test, y_train, y_test


def build_models():
    """
    Build preprocessing and classification pipelines.

    Returns:
        dict:
            Model name mapped to its scikit-learn Pipeline.
    """
    categorical_features = ["district"]

    numeric_features = [
        "month",
        "day_of_year",
    ]

    preprocessing = ColumnTransformer(
        transformers=[
            (
                "district",
                OneHotEncoder(handle_unknown="ignore"),
                categorical_features,
            ),
            (
                "numeric",
                "passthrough",
                numeric_features,
            ),
        ]
    )

    models = {
        "Logistic Regression": LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            random_state=42,
        ),
        "Decision Tree": DecisionTreeClassifier(
            max_depth=8,
            class_weight="balanced",
            random_state=42,
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
    }

    pipelines = {}

    for name, model in models.items():
        pipelines[name] = Pipeline(
            steps=[
                ("preprocessing", preprocessing),
                ("model", model),
            ]
        )

    return pipelines


def evaluate_model(name, model, X_test, y_test):
    """
    Evaluate one trained classification model.

    Args:
        name:
            Display name of the model.
        model:
            Trained scikit-learn Pipeline.
        X_test:
            Test features.
        y_test:
            Test target.

    Returns:
        float:
            F1-score for the Elevated class.
    """
    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    precision = precision_score(
        y_test,
        predictions,
        zero_division=0,
    )

    recall = recall_score(
        y_test,
        predictions,
        zero_division=0,
    )

    f1 = f1_score(
        y_test,
        predictions,
        zero_division=0,
    )

    print("\n" + "=" * 70)
    print(name)
    print("=" * 70)

    print(f"Accuracy : {accuracy:.4f}")
    print(f"Precision: {precision:.4f}")
    print(f"Recall   : {recall:.4f}")
    print(f"F1-score : {f1:.4f}")

    print("\nConfusion matrix:")
    print(confusion_matrix(y_test, predictions))

    print("\nClassification report:")
    print(
        classification_report(
            y_test,
            predictions,
            target_names=[
                "Moderate",
                "Elevated",
            ],
            zero_division=0,
        )
    )

    return f1


def main():
    """
    Train and compare FDR classification models.

    The cleaned dataset is loaded from MySQL. A chronological
    split is used so models are trained on earlier historical
    observations and tested on later observations.

    The model with the highest Elevated-class F1-score is saved.
    """
    print("Loading FDR training data from MySQL...")

    df = load_training_data()

    print(f"Rows loaded: {len(df)}")

    X, y = prepare_data(df)

    print("\nOverall target distribution:")
    print(y.value_counts().sort_index())

    X_train, X_test, y_train, y_test = chronological_split(
        X,
        y,
        test_fraction=0.20,
    )

    models = build_models()

    best_model = None
    best_name = None
    best_f1 = -1

    for name, model in models.items():
        model.fit(X_train, y_train)

        f1 = evaluate_model(
            name,
            model,
            X_test,
            y_test,
        )

        if f1 > best_f1:
            best_f1 = f1
            best_model = model
            best_name = name

    print("\n" + "=" * 70)
    print("BEST MODEL")
    print("=" * 70)

    print(f"Model: {best_name}")
    print(f"F1-score: {best_f1:.4f}")

    joblib.dump(best_model, MODEL_PATH)

    print(f"\nSaved model to: {MODEL_PATH}")


if __name__ == "__main__":
    main()