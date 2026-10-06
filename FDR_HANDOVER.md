# Fire Danger Pattern Estimate – Handover Guide

## Overview

This document explains the Fire Danger Pattern Estimate feature added in the `feature/fdr-ml-model` branch and what another team member should do when taking over, merging, deploying, or maintaining this work.

The feature uses historical Victorian AFDRS Fire Danger Rating data to estimate whether a selected fire district and time of year are historically more similar to:

- **Moderate**
- **Elevated**

where:

- `Moderate` = Moderate Fire Danger Rating
- `Elevated` = High + Extreme + Catastrophic Fire Danger Ratings

This feature is intended to show historical seasonal patterns only.

It is **not an official Fire Danger Rating forecast** and must not be used for emergency decisions.

---

# 1. Feature Summary

The implementation includes:

- AFDRS historical Fire Danger Rating data processing
- cleaned FDR data stored in MySQL
- model training and evaluation
- saved trained model
- backend prediction API
- frontend Fire Danger Pattern Estimate panel
- user-friendly Moderate / Elevated explanations
- safety disclaimer

The final model compares:

- Logistic Regression
- Decision Tree
- Random Forest

The final selected model is:

**Decision Tree**

Final evaluation:

| Metric | Result |
|---|---:|
| Accuracy | 0.6802 |
| Precision | 0.5406 |
| Recall | 0.6453 |
| F1-score | 0.5883 |

The model was selected using the F1-score of the Elevated class.

---

# 2. Model Inputs

The final model uses three input variables:

```text
district
month
day_of_year
```

Example:

```text
Date: 15 January 2026
District: Central

district = Central
month = 1
day_of_year = 15
```

The full `date` value is not directly used as a model feature.

The date is used during training to create a chronological train/test split.

---

# 3. Target Variable

The original AFDRS rating codes are:

```text
0 = No rating
1 = Moderate
2 = High
3 = Extreme
4 = Catastrophic
```

For model training, they are converted into a binary target:

```text
0 = Moderate
1 = Elevated
```

where:

```text
Elevated = High + Extreme + Catastrophic
```

The target is created using:

```python
df["target"] = (df["rating_code"] >= 2).astype(int)
```

Therefore:

```text
rating_code = 1 -> Moderate
rating_code = 2 -> Elevated
rating_code = 3 -> Elevated
rating_code = 4 -> Elevated
```

Records with:

```text
rating_code = 0
```

are excluded from training because `No rating` does not mean low fire danger.

---

# 4. Why High, Extreme and Catastrophic Are Combined

The historical dataset contains many more Moderate and High observations than Extreme and Catastrophic observations.

The approximate usable class distribution is:

```text
Moderate        4855
High            1687
Extreme          121
Catastrophic      15
```

Training a four-class model would therefore provide very few examples for Extreme and Catastrophic.

To make the classification problem more reliable, the higher categories are combined into:

```text
Elevated
```

This produces:

```text
Moderate = 4855
Elevated = 1823
```

This means the model does not separately predict:

```text
High
Extreme
Catastrophic
```

It predicts only:

```text
Moderate
or
Elevated
```

---

# 5. Important Model Limitation

The model only uses:

```text
district
month
day_of_year
```

It does not use live or forecast weather information such as:

```text
temperature
wind speed
humidity
rainfall
fuel moisture
drought conditions
```

Therefore, the model should be interpreted as:

> Based on historical Fire Danger Rating records, does this district and time of year look more similar to Moderate or Elevated historical conditions?

It should NOT be interpreted as:

> A bushfire will occur.

It should also NOT be interpreted as:

> This is today's official Fire Danger Rating.

---

# 6. Important Files

## Data processing

Raw AFDRS data is processed by:

```text
data/scripts/process_fdr_history.py
```

Processed dataset:

```text
data/processed/fdr_history.parquet
```

Raw source files are stored locally under:

```text
data/raw/FDR_history/
```

Raw files are intentionally excluded from Git by `.gitignore`.

---

## Database ingestion

Dedicated ingestion script:

```text
data/scripts/ingest_fdr_history_to_mysql.py
```

The general open-data ingestion script has also been updated:

```text
data/scripts/ingest_open_data_to_mysql.py
```

---

## Database schema

Migration:

```text
database/migrations/010_fdr_history.sql
```

Initial schema:

```text
database/init/001_initial_schema.sql
```

New table:

```text
open_data_fdr_history
```

---

## Model training

Training script:

```text
data/scripts/train_fdr_model.py
```

Saved model:

```text
backend/models/fdr_model.joblib
```

The trained model is committed to the repository.

Normal application startup does not require model retraining.

---

## Backend

API route:

```text
backend/app/api/routes/fdr.py
```

Prediction service:

```text
backend/app/services/fdr_prediction.py
```

Response schema:

```text
backend/app/schemas/fdr_prediction.py
```

Main API router:

```text
backend/app/api/router.py
```

---

## Frontend

API client:

```text
frontend/src/api/client.js
```

Pinia store:

```text
frontend/src/stores/fdrPrediction.js
```

FDR component:

```text
frontend/src/components/overview/FdrPredictionPanel.vue
```

Overview page integration:

```text
frontend/src/views/OverviewView.vue
```

---

# 7. Backend API

Prediction endpoint:

```text
GET /api/v1/fdr/prediction
```

Parameters:

```text
district
date
```

Example:

```bash
curl "http://localhost:8000/api/v1/fdr/prediction?district=Central&date=2026-01-15"
```

Example response:

```json
{
  "district": "Central",
  "date": "2026-01-15",
  "prediction_class": 0,
  "prediction_label": "Moderate",
  "elevated_probability": 0.4952,
  "model_name": "Decision Tree",
  "disclaimer": "This is a machine-learning estimate based on historical seasonal patterns. It is not an official Fire Danger Rating forecast and must not be used for emergency decisions."
}
```

The frontend intentionally does not display the model name or technical machine-learning terminology to end users.

---

# 8. Frontend Behaviour

The Overview page contains:

```text
Fire Danger Pattern Estimate
```

Users select:

```text
Fire district
Date
```

The result displays:

```text
Estimated pattern
District
Date
Chance of elevated historical pattern
```

It also explains:

### Moderate

Historically more similar to days with a Moderate Fire Danger Rating.

### Elevated

Historically more similar to days with High, Extreme or Catastrophic Fire Danger Ratings.

The frontend also displays this safety message:

> This estimate is based on historical seasonal patterns. It is not an official Fire Danger Rating forecast and should not be used for emergency decisions.

---

# 9. Handover – What To Do After Pulling or Merging

## Step 1 – Pull the latest code

After the feature is merged:

```bash
git checkout main
git pull origin main
```

---

## Step 2 – Check the database migration

This feature introduces:

```text
database/migrations/010_fdr_history.sql
```

which creates:

```text
open_data_fdr_history
```

If the target database does not already contain this table, apply the migration before deployment.

### Important

The production RDS migration should only be marked as completed after it has actually been applied.

At the time of writing, verify whether the production database has already received this migration.

---

# 10. Load FDR Data Into the Database

The cleaned dataset is:

```text
data/processed/fdr_history.parquet
```

To populate the new database table, run:

```bash
python data/scripts/ingest_fdr_history_to_mysql.py
```

Make sure the required database environment variables are configured first.

Typical variables include:

```text
DATABASE_HOST
MYSQL_USER
MYSQL_PASSWORD
MYSQL_DATABASE
```

Do not commit database passwords or other credentials to Git.

---

# 11. Model Retraining

The trained model is already committed:

```text
backend/models/fdr_model.joblib
```

Therefore:

**Do not retrain the model during normal deployment.**

Retraining is only necessary if:

- the FDR dataset is intentionally updated
- the feature set changes
- the target definition changes
- the modelling approach changes

To retrain:

```bash
python data/scripts/train_fdr_model.py
```

The script compares:

```text
Logistic Regression
Decision Tree
Random Forest
```

and saves the model with the highest Elevated-class F1-score to:

```text
backend/models/fdr_model.joblib
```

Running the training script overwrites the existing model file.

---

# 12. Rebuild the Backend

After updating the model or backend code, rebuild the backend container:

```bash
docker compose up -d --build backend
```

Check that the backend starts successfully.

---

# 13. Test the API

Run:

```bash
curl "http://localhost:8000/api/v1/fdr/prediction?district=Central&date=2026-01-15"
```

A valid JSON response should be returned.

Also test another district, for example:

```bash
curl "http://localhost:8000/api/v1/fdr/prediction?district=Mallee&date=2026-11-06"
```

Test invalid input if required:

```bash
curl "http://localhost:8000/api/v1/fdr/prediction?district=ABC&date=2026-01-15"
```

The API should reject unsupported districts.

---

# 14. Test the Frontend

Run:

```bash
cd frontend
npm run dev
```

Open the Overview page.

Test several combinations of:

```text
district
date
```

Confirm that the page displays:

- Moderate or Elevated
- chance of elevated historical pattern
- district
- date
- Moderate explanation
- Elevated explanation
- safety disclaimer

Confirm that the page does not display:

```text
Decision Tree
```

to normal users.

The model type can be explained verbally to mentors or technical team members.

---

# 15. Production Frontend Build

Before deployment, run:

```bash
npm --prefix frontend run build
```

The FDR feature has already passed the production frontend build locally.

A Vite warning may appear about the existing large OpenFreeMap chunk.

This warning is unrelated to the FDR feature and does not prevent the build from succeeding.

---

# 16. Local Database Defaults

The local Docker Compose configuration uses defaults similar to:

```text
MYSQL_DATABASE = fit5120
MYSQL_USER = fit5120_app
```

Database credentials should be obtained from the local environment or project configuration.

Never commit actual passwords or API keys.

---

# 17. Current Validation Status

The following checks have been completed locally:

- [x] AFDRS data processed successfully
- [x] processed FDR parquet created
- [x] FDR records ingested into local MySQL
- [x] database table verified
- [x] Logistic Regression trained
- [x] Decision Tree trained
- [x] Random Forest trained
- [x] chronological train/test split used
- [x] Decision Tree selected
- [x] final F1-score = 0.5883
- [x] trained model saved
- [x] backend Docker image rebuilt
- [x] backend prediction API tested
- [x] frontend prediction tested
- [x] dark theme tested
- [x] frontend production build passed

Production database migration and production data ingestion should be verified separately before deployment.

---

# 18. Final Model Results

## Logistic Regression

```text
Accuracy  = 0.6081
Precision = 0.4604
Recall    = 0.6202
F1-score  = 0.5285
```

## Decision Tree

```text
Accuracy  = 0.6802
Precision = 0.5406
Recall    = 0.6453
F1-score  = 0.5883
```

## Random Forest

```text
Accuracy  = 0.6788
Precision = 0.5404
Recall    = 0.6221
F1-score  = 0.5784
```

Final selected model:

```text
Decision Tree
```

---

# 19. Chronological Train/Test Split

The dataset contains:

```text
6678 usable records
```

Overall target distribution:

```text
Moderate = 4855
Elevated = 1823
```

Training period:

```text
2022-11-14 to 2025-11-16
```

Training rows:

```text
5221
```

Testing period:

```text
2025-11-17 to 2026-05-07
```

Testing rows:

```text
1457
```

The split is performed using unique dates so all districts belonging to the same date remain together.

Earlier historical observations are used for training and later observations are used for testing.

---

# 20. Safety and Communication

When presenting this feature to users, mentors, or stakeholders, describe it as:

> A historical Fire Danger Rating pattern estimate based on district and seasonal timing.

Do not describe it as:

> A bushfire prediction model.

Do not describe it as:

> An official Fire Danger Rating forecast.

Do not claim that:

> Elevated means a bushfire will happen.

A correct explanation is:

> Elevated means that the selected district and time of year are historically more similar to days that had High, Extreme or Catastrophic Fire Danger Ratings.

---

# 21. Future Improvements

Possible future improvements include:

- including weather variables such as temperature
- including humidity
- including wind speed
- including rainfall
- including fuel or vegetation conditions
- adding more historical observations
- evaluating additional model types
- improving probability calibration
- testing cyclical date encoding
- evaluating separate High / Extreme / Catastrophic predictions if enough data becomes available

These are future improvements only and are not required for the current implementation.

---

# 22. Branch Information

Feature branch:

```text
feature/fdr-ml-model
```

Main implementation commit:

```text
e3135f6
```

Commit message:

```text
Add historical fire danger pattern prediction
```

---

# 23. Quick Handover Checklist

For someone taking over this feature:

```text
1. Pull latest main
2. Verify database migration 010_fdr_history.sql
3. Verify open_data_fdr_history exists
4. Ingest processed FDR data if required
5. Do NOT retrain the model unless necessary
6. Rebuild backend
7. Test /api/v1/fdr/prediction
8. Test the Overview page
9. Run frontend production build
10. Verify production database before deployment
```

If all of the above work correctly, the Fire Danger Pattern Estimate feature is ready for deployment.