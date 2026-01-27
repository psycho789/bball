#!/usr/bin/env python3
"""
Inspect the catboost_odds_platt_v2 model artifact to understand why it's miscalibrated.
"""

import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.lib._winprob_lib import load_artifact


def main():
    artifact_path = Path("artifacts/winprob_catboost_odds_platt_v2.json")
    
    if not artifact_path.exists():
        print(f"ERROR: Model artifact not found: {artifact_path}")
        return 1
    
    print("=" * 80)
    print("INSPECTING catboost_odds_platt_v2 MODEL ARTIFACT")
    print("=" * 80)
    print()
    
    # Load artifact
    artifact = load_artifact(artifact_path)
    
    print("1. MODEL METADATA")
    print("-" * 80)
    print(f"Version: {artifact.version}")
    print(f"Train season start max: {artifact.train_season_start_max}")
    print(f"Calib season start: {artifact.calib_season_start}")
    print(f"Test season start: {artifact.test_season_start}")
    print(f"Model type: {artifact.model_type}")
    
    # Determine calibration method from what's present
    if artifact.platt is not None:
        calibration_method = "platt"
    elif artifact.isotonic is not None:
        calibration_method = "isotonic"
    else:
        calibration_method = "none"
    print(f"Calibration method: {calibration_method}")
    print()
    
    print("2. FEATURES")
    print("-" * 80)
    print(f"Total features: {len(artifact.feature_names)}")
    print("\nFeature list:")
    for i, feat in enumerate(artifact.feature_names, 1):
        print(f"  {i:2d}. {feat}")
    print()
    
    print("3. PREPROCESS PARAMETERS")
    print("-" * 80)
    preprocess = artifact.preprocess
    print(f"Point diff mean: {preprocess.point_diff_mean:.4f}")
    print(f"Point diff std: {preprocess.point_diff_std:.4f}")
    print(f"Time rem mean: {preprocess.time_rem_mean:.4f}")
    print(f"Time rem std: {preprocess.time_rem_std:.4f}")
    
    if preprocess.score_diff_div_sqrt_time_rem_mean is not None:
        print(f"\nInteraction terms:")
        print(f"  score_diff_div_sqrt mean: {preprocess.score_diff_div_sqrt_time_rem_mean:.4f}")
        print(f"  score_diff_div_sqrt std: {preprocess.score_diff_div_sqrt_time_rem_std:.4f}")
    
    if preprocess.espn_home_prob_mean is not None:
        print(f"  espn_home_prob mean: {preprocess.espn_home_prob_mean:.4f}")
        print(f"  espn_home_prob std: {preprocess.espn_home_prob_std:.4f}")
    print()
    
    print("4. CALIBRATION PARAMETERS")
    print("-" * 80)
    if artifact.platt is not None:
        print(f"Platt scaling parameters:")
        print(f"  Alpha (slope): {artifact.platt.alpha}")
        print(f"  Beta (intercept): {artifact.platt.beta}")
        print(f"\nInterpretation:")
        if abs(artifact.platt.alpha) < 0.5 or abs(artifact.platt.alpha) > 2.0:
            print(f"  ⚠️  Alpha is extreme (normal range: 0.5-2.0)")
        else:
            print(f"  ✅ Alpha is in normal range")
        if abs(artifact.platt.beta) > 1.0:
            print(f"  ⚠️  Beta is extreme (normal range: -1.0 to 1.0)")
        else:
            print(f"  ✅ Beta is in normal range")
    elif artifact.isotonic is not None:
        print(f"Isotonic calibration: Present")
        print(f"  (Isotonic regression uses piecewise constant function)")
    else:
        print("  No calibration found")
    print()
    
    print("5. FEATURE IMPORTANCE")
    print("-" * 80)
    
    # Load CatBoost model if it's a CatBoost model
    if artifact.model_type == "catboost" and artifact.catboost_model_path is not None:
        from catboost import CatBoostClassifier
        
        # Resolve model path
        model_path = Path(artifact.catboost_model_path)
        if not model_path.is_absolute():
            # Try common locations
            possible_paths = [
                Path("artifacts") / model_path,
                Path("data/models") / model_path,
                model_path,
            ]
            for possible_path in possible_paths:
                if possible_path.exists():
                    model_path = possible_path
                    break
        
        if not model_path.exists():
            print(f"  ⚠️  CatBoost model file not found: {model_path}")
        else:
            try:
                model = CatBoostClassifier()
                model.load_model(str(model_path))
                
                importance = model.get_feature_importance()
                print(f"\nFeature importance (top 15):")
                print()
                
                # Pair features with importance and sort
                feat_importance = list(zip(artifact.feature_names, importance))
                feat_importance.sort(key=lambda x: x[1], reverse=True)
                
                print(f"{'Rank':<6} {'Feature Name':<50} {'Importance':<12} {'Type'}")
                print("-" * 80)
                
                for i, (feat, imp) in enumerate(feat_importance[:15], 1):
                    # Check if it's an opening odds feature
                    is_odds_feat = any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround'])
                    feat_type = "🔴 Odds" if is_odds_feat else "  Other"
                    print(f"{i:<6} {feat:<50} {imp:>10.2f}  {feat_type}")
                
                # Count odds features in top 10
                odds_in_top10 = sum(1 for feat, _ in feat_importance[:10] 
                                    if any(term in feat.lower() for term in ['opening', 'odds', 'moneyline', 'spread', 'total', 'overround']))
                print()
                print(f"Opening odds features in top 10: {odds_in_top10}/10")
                if odds_in_top10 >= 5:
                    print("  ⚠️  WARNING: Opening odds features dominate! This could cause overconfidence.")
                elif odds_in_top10 >= 3:
                    print("  ⚠️  CAUTION: Opening odds features are very important (may be contributing to issue)")
                else:
                    print("  ✅ Opening odds features are not dominating")
                    
            except Exception as e:
                print(f"  ❌ Could not load CatBoost model: {e}")
                import traceback
                traceback.print_exc()
    else:
        print("  Model is not CatBoost or model path not found")
    print()
    
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()
    print("Key observations:")
    print(f"- Model has {len(artifact.feature_names)} features")
    print(f"- Model type: {artifact.model_type}")
    if artifact.platt is not None:
        print(f"- Calibration: Platt (alpha={artifact.platt.alpha:.4f}, beta={artifact.platt.beta:.4f})")
    elif artifact.isotonic is not None:
        print(f"- Calibration: Isotonic")
    else:
        print(f"- Calibration: None")
    print()
    print("If opening odds features are in the top of feature importance,")
    print("they may be dominating the predictions and causing miscalibration.")
    print()
    print("Next steps:")
    print("1. Review feature importance above - are odds features dominating?")
    print("2. Check calibration parameters - are they extreme?")
    print("3. Run calibration set distribution query (see analysis document)")
    print("4. Consider retraining with different feature engineering")
    print("5. Consider filtering to only use model when opening odds present")


if __name__ == "__main__":
    main()
