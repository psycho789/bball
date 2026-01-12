# Platt ESPN Odds: Probability Transformation Pipeline

This document explains how probabilities are transformed through the win-probability model pipeline, from raw ESPN probabilities to final Platt-calibrated probabilities (also called "Platt ESPN odds").

## Overview

The win-probability model uses a **Pipeline Pattern** to transform probabilities through three distinct stages:

1. **Raw ESPN Probabilities** → Used as model features
2. **Model Base Probabilities** → Logistic regression output (before calibration)
3. **Platt-Calibrated Probabilities** → Final calibrated output ("Platt ESPN odds")

## Stage 1: Raw ESPN Probabilities

### Source
Raw ESPN probabilities come from the ESPN API and are stored in the `espn.probabilities_raw_items` table.

### Format
- **Column**: `home_win_percentage`
- **Format**: May be 0-100 (percentage) or 0-1 (probability)
- **Normalization**: Converted to 0-1 format during data loading

### Code Reference
**File**: `scripts/model/train_winprob_logreg.py:118-122`

```python
-- Normalize probabilities to 0-1 format
CASE 
    WHEN p.home_win_percentage > 1.0 THEN p.home_win_percentage / 100.0
    ELSE p.home_win_percentage
END AS espn_home_prob
```

### Usage
Raw ESPN probabilities are used as **features** in the logistic regression model, not as direct outputs. They are combined with other game state features:
- Point differential (home - away)
- Time remaining in regulation
- Possession indicator
- Interaction terms (if enabled)

### Example
```python
# Raw ESPN probability from database
espn_home_prob_raw = 0.65  # 65% home win probability from ESPN API

# After normalization (if needed)
espn_home_prob = 0.65  # Already in 0-1 format
```

### Notation
- `P_espn_raw`: Raw ESPN probability (before normalization)
- `P_espn`: Normalized ESPN probability (0-1 format, used as feature)

## Stage 2: Model Base Probabilities

### Source
Base probabilities are the output of the logistic regression model **before** Platt calibration is applied.

### Calculation
The model combines multiple features to produce base probabilities:

```python
logits = X @ weights + intercept
P_base = sigmoid(logits)
```

Where:
- `X` = Design matrix containing scaled features (point differential, time remaining, ESPN probability, etc.)
- `weights` = Model weights (learned during training)
- `intercept` = Model intercept (learned during training)
- `sigmoid` = Logistic function: `1 / (1 + exp(-x))`

### Code Reference
**File**: `scripts/lib/_winprob_lib.py:245-251`

```245:251:scripts/lib/_winprob_lib.py
def predict_proba(artifact: WinProbArtifact, *, X: np.ndarray) -> np.ndarray:
    w = np.asarray(artifact.model.weights, dtype=np.float64)
    logits = X @ w + float(artifact.model.intercept)
    p = sigmoid(logits)
    if artifact.platt is not None:
        p = artifact.platt.apply(p)
    return p
```

### Features Used
The model uses the following features (after scaling/normalization):
1. **Point differential** (scaled): `(score_diff - mean) / std`
2. **Time remaining** (scaled): `(time_remaining - mean) / std`
3. **Possession** (one-hot encoded): `possession_home`, `possession_away`, `possession_unknown`
4. **ESPN probability** (scaled, if interaction terms enabled): `(espn_home_prob - mean) / std`
5. **Interaction terms** (if enabled):
   - `score_diff_div_sqrt_time_remaining` (scaled)
   - `espn_home_prob_lag_1` (scaled)
   - `espn_home_prob_delta_1` (scaled)
   - `period` (one-hot encoded: period_1, period_2, period_3, period_4)

### Example
```python
from scripts.lib._winprob_lib import load_artifact, build_design_matrix, predict_proba
from pathlib import Path
import numpy as np

# Load artifact
artifact = load_artifact(Path("artifacts/winprob_logreg_v4_historical.json"))

# Build design matrix
X = build_design_matrix(
    point_differential=np.array([5.0]),  # Home team up by 5
    time_remaining_regulation=np.array([1200.0]),  # 20 minutes remaining
    possession=["home"],
    preprocess=artifact.preprocess,
    espn_home_prob=np.array([0.65]),  # ESPN says 65% home win
    # ... other features
)

# Get base probabilities (without Platt calibration)
# Temporarily disable Platt calibration
original_platt = artifact.platt
artifact.platt = None
P_base = predict_proba(artifact, X=X)
artifact.platt = original_platt  # Restore

print(f"Base model probability: {P_base[0]:.3f}")  # e.g., 0.680
```

### Notation
- `P_base`: Base model probability (logistic regression output, before calibration)

## Stage 3: Platt-Calibrated Probabilities ("Platt ESPN Odds")

### Source
Platt-calibrated probabilities are the **final output** of the model pipeline. These are the base probabilities transformed using Platt scaling.

### Calculation
Platt scaling applies a logistic regression transformation to the base probabilities:

```python
logit(P_calibrated) = alpha + beta × logit(P_base)
P_calibrated = sigmoid(alpha + beta × logit(P_base))
```

Where:
- `alpha` = Platt calibration intercept parameter (learned during calibration)
- `beta` = Platt calibration slope parameter (learned during calibration)
- `logit(p)` = Log-odds transformation: `log(p / (1 - p))`
- `sigmoid(x)` = Inverse logit: `1 / (1 + exp(-x))`

### Code Reference
**File**: `scripts/lib/_winprob_lib.py:129-136` (PlattCalibrator class)

```129:136:scripts/lib/_winprob_lib.py
@dataclass(frozen=True)
class PlattCalibrator:
    alpha: float
    beta: float

    def apply(self, p: np.ndarray) -> np.ndarray:
        x = logit(p)
        return sigmoid(self.alpha + self.beta * x)
```

**File**: `scripts/lib/_winprob_lib.py:245-251` (Application in predict_proba)

The Platt calibration is automatically applied if `artifact.platt is not None`:

```python
p = sigmoid(logits)  # Base probability
if artifact.platt is not None:
    p = artifact.platt.apply(p)  # Apply Platt calibration
return p
```

### Current Model Parameters
For `winprob_logreg_v4_historical.json`:
- **Alpha**: -0.05145924163626064
- **Beta**: 1.0469339980195846

**Interpretation**:
- Beta ≈ 1.0 suggests the base model is already well-calibrated (minimal slope adjustment)
- Alpha ≈ 0 suggests minimal intercept adjustment needed
- Small adjustments indicate good base model calibration

### Example
```python
from scripts.lib._winprob_lib import load_artifact, build_design_matrix, predict_proba
from pathlib import Path
import numpy as np

# Load artifact (includes Platt calibration)
artifact = load_artifact(Path("artifacts/winprob_logreg_v4_historical.json"))

# Build design matrix
X = build_design_matrix(
    point_differential=np.array([5.0]),
    time_remaining_regulation=np.array([1200.0]),
    possession=["home"],
    preprocess=artifact.preprocess,
    espn_home_prob=np.array([0.65]),
    # ... other features
)

# Get Platt-calibrated probabilities (final output)
P_platt = predict_proba(artifact, X=X)

print(f"Raw ESPN probability: 0.650")
print(f"Platt-calibrated probability: {P_platt[0]:.3f}")  # e.g., 0.670
```

### Why Platt Calibration?
Platt scaling improves **probability calibration** (how well probabilities match observed frequencies) without changing **discrimination** (ability to distinguish between classes, measured by AUC).

**Benefits**:
- Reduces Expected Calibration Error (ECE)
- Preserves model discrimination (AUC unchanged)
- Simple 2-parameter transformation
- Standard technique in machine learning

**Trade-offs**:
- Requires separate calibration dataset
- May overfit if calibration set is small
- Adds computational overhead (minimal)

### Notation
- `P_platt`: Platt-calibrated probability (final output, "Platt ESPN odds")
- `P_calibrated`: Same as `P_platt` (alternative notation)

## Complete Pipeline Example

Here's a complete example showing all three stages:

```python
from scripts.lib._winprob_lib import load_artifact, build_design_matrix, predict_proba
from pathlib import Path
import numpy as np

# Load model artifact
artifact = load_artifact(Path("artifacts/winprob_logreg_v4_historical.json"))

# Stage 1: Raw ESPN Probability (from database)
P_espn_raw = 0.65  # 65% home win from ESPN API
P_espn = 0.65  # Normalized to 0-1 format

# Stage 2: Build design matrix and get base probabilities
X = build_design_matrix(
    point_differential=np.array([5.0]),  # Home up by 5
    time_remaining_regulation=np.array([1200.0]),  # 20 min remaining
    possession=["home"],
    preprocess=artifact.preprocess,
    espn_home_prob=np.array([P_espn]),  # ESPN probability as feature
    # ... other features if interaction terms enabled
)

# Temporarily disable Platt to get base probability
original_platt = artifact.platt
artifact.platt = None
P_base = predict_proba(artifact, X=X)[0]
artifact.platt = original_platt

# Stage 3: Get Platt-calibrated probability (final output)
P_platt = predict_proba(artifact, X=X)[0]

print(f"Stage 1 - Raw ESPN: {P_espn:.3f}")
print(f"Stage 2 - Base Model: {P_base:.3f}")
print(f"Stage 3 - Platt-Calibrated: {P_platt:.3f}")
```

**Example Output**:
```
Stage 1 - Raw ESPN: 0.650
Stage 2 - Base Model: 0.680
Stage 3 - Platt-Calibrated: 0.670
```

## Key Insights

1. **ESPN Probabilities are Features, Not Outputs**: Raw ESPN probabilities are used as **input features** to the model, not as direct outputs. The model combines ESPN probabilities with game state to produce better predictions.

2. **Platt Calibration is Automatic**: If the artifact contains Platt calibration parameters, they are automatically applied during prediction. No manual calibration step is needed.

3. **Calibration Improves Accuracy**: Platt scaling transforms base probabilities to better match observed win rates, reducing calibration error while preserving discrimination.

4. **"Platt ESPN Odds" Terminology**: The term "Platt ESPN odds" refers to the **final calibrated probabilities** output by the model, which combine ESPN probabilities (as features) with game state information and Platt calibration.

## Related Files

- **Model Training**: `scripts/model/train_winprob_logreg.py`
- **Model Evaluation**: `scripts/model/evaluate_winprob_model.py`
- **Core Library**: `scripts/lib/_winprob_lib.py`
- **Model Artifact**: `artifacts/winprob_logreg_v4_historical.json`

## Terminology Glossary

### Raw ESPN Probabilities
**Definition**: Direct win probabilities from the ESPN API, stored in `espn.probabilities_raw_items.home_win_percentage`.

**Format**: May be 0-100 (percentage) or 0-1 (probability), normalized to 0-1 during data loading.

**Usage**: Used as **features** in the logistic regression model, combined with game state information.

**Notation**: `P_espn_raw` (before normalization), `P_espn` (after normalization)

**Example**: `P_espn = 0.65` means ESPN predicts 65% chance of home team winning.

### Model Base Probabilities
**Definition**: Output probabilities from the logistic regression model **before** Platt calibration is applied.

**Calculation**: `P_base = sigmoid(X @ weights + intercept)`, where X contains scaled features (point differential, time remaining, ESPN probability, etc.).

**Usage**: Intermediate output that gets transformed by Platt scaling to produce final calibrated probabilities.

**Notation**: `P_base`

**Example**: `P_base = 0.68` means the base model predicts 68% chance of home team winning (before calibration).

### Platt-Calibrated Probabilities (aka "Platt ESPN Odds")
**Definition**: Final calibrated probabilities output by the model after applying Platt scaling to base probabilities.

**Calculation**: `P_calibrated = sigmoid(alpha + beta × logit(P_base))`, where alpha and beta are Platt calibration parameters.

**Usage**: Final output used in trading simulations and decision-making. These are the "Platt ESPN odds" referenced in the codebase.

**Notation**: `P_platt` or `P_calibrated`

**Example**: `P_platt = 0.67` means the calibrated model predicts 67% chance of home team winning (after Platt scaling).

### Platt Scaling (Platt Calibration)
**Definition**: A probability calibration method that fits a logistic regression model to transform probabilities: `logit(P_calibrated) = alpha + beta × logit(P_base)`.

**Algorithm**: Uses Iteratively Reweighted Least Squares (IRLS) to fit 2 parameters (alpha, beta) on a calibration dataset.

**Purpose**: Improves probability calibration (reduces ECE) without changing discrimination (preserves AUC).

**Complexity**: O(n × iterations) for fitting, O(1) for application per prediction.

**Reference**: Platt, J. (1999). "Probabilistic outputs for support vector machines and comparisons to regularized likelihood methods"

### Expected Calibration Error (ECE)
**Definition**: Metric measuring how well-calibrated probabilities are. Lower is better.

**Calculation**: Weighted average of absolute difference between predicted probabilities and observed frequencies across probability bins.

**Target**: ECE < 0.01 indicates good calibration.

**Usage**: Primary metric for evaluating calibration quality.

**Example**: ECE = 0.008 means probabilities are well-calibrated (predicted probabilities closely match observed frequencies).

### Brier Score
**Definition**: Mean squared error between predicted probabilities and actual binary outcomes. Lower is better.

**Calculation**: `Brier = mean((P_predicted - Y_actual)²)`, where Y_actual is 0 or 1.

**Range**: 0.0 (perfect) to 1.0 (worst)

**Usage**: Measures both calibration and discrimination (lower is better for both).

**Example**: Brier = 0.15 means average squared error of 0.15 between predictions and outcomes.

### AUC (Area Under ROC Curve)
**Definition**: Metric measuring model discrimination ability (ability to distinguish between classes). Higher is better.

**Range**: 0.5 (random) to 1.0 (perfect)

**Usage**: Measures discrimination (not affected by Platt calibration).

**Example**: AUC = 0.85 means the model can distinguish between home wins and losses with 85% accuracy.

### Log Loss (Logarithmic Loss)
**Definition**: Negative log-likelihood of the model predictions. Lower is better.

**Calculation**: `LogLoss = -mean(Y × log(P) + (1-Y) × log(1-P))`

**Range**: 0.0 (perfect) to ∞ (worst)

**Usage**: Penalizes confident wrong predictions more than uncertain predictions.

**Example**: LogLoss = 0.45 means average log loss of 0.45 (lower is better).

### Logit Transformation
**Definition**: Transforms probabilities to log-odds space: `logit(p) = log(p / (1-p))`.

**Inverse**: `sigmoid(x) = 1 / (1 + exp(-x))` transforms log-odds back to probabilities.

**Usage**: Used in Platt scaling to transform probabilities before applying linear transformation.

**Example**: `logit(0.5) = 0.0`, `logit(0.75) ≈ 1.10`, `logit(0.25) ≈ -1.10`

### Sigmoid Function
**Definition**: Inverse logit function that transforms log-odds to probabilities: `sigmoid(x) = 1 / (1 + exp(-x))`.

**Range**: Output is always between 0 and 1.

**Usage**: Used in logistic regression and Platt scaling to ensure probabilities are valid.

**Example**: `sigmoid(0) = 0.5`, `sigmoid(1.1) ≈ 0.75`, `sigmoid(-1.1) ≈ 0.25`

