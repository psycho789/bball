#!/usr/bin/env python3
"""
Extract feature importance from v2 odds-enabled CatBoost models.

This script loads all 4 v2 odds-enabled models and extracts feature importance
for opening odds features to verify redundancy of has_opening_moneyline.
"""

import sys
from pathlib import Path

import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from scripts.lib._winprob_lib import load_artifact
from catboost import CatBoostClassifier

def main():
    """Extract feature importance from all 4 v2 odds-enabled models."""
    
    models = [
        "catboost_odds_platt_v2",
        "catboost_odds_isotonic_v2",
        "catboost_odds_no_interaction_platt_v2",
        "catboost_odds_no_interaction_isotonic_v2",
    ]
    
    odds_features = ['opening_overround', 'has_opening_moneyline', 'has_opening_spread', 'has_opening_total']
    
    print("=" * 80)
    print("Feature Importance Analysis for Opening Odds Features")
    print("=" * 80)
    print()
    
    for model_name in models:
        artifact_path = Path(f"artifacts/winprob_{model_name}.json")
        
        if not artifact_path.exists():
            print(f"⚠️  Model artifact not found: {artifact_path}")
            print(f"   Skipping {model_name}")
            print()
            continue
        
        try:
            # Load artifact
            artifact = load_artifact(artifact_path)
            
            # Load CatBoost model
            model = CatBoostClassifier()
            if artifact.catboost_model_path is None:
                print(f"    ⚠️  No CatBoost model path in artifact")
                continue
            
            # Resolve model path (same logic as predict_proba)
            model_path = Path(artifact.catboost_model_path)
            if not model_path.is_absolute():
                # Try common locations
                possible_paths = [
                    Path("data/models") / model_path,
                    Path("artifacts") / model_path,
                    artifact_path.parent / model_path,
                    model_path,
                ]
                found = False
                for possible_path in possible_paths:
                    if possible_path.exists():
                        model_path = possible_path
                        found = True
                        break
                if not found:
                    print(f"    ⚠️  CatBoost model file not found: {artifact.catboost_model_path}")
                    continue
            
            model.load_model(str(model_path))
            
            # Get feature importance
            importance = model.get_feature_importance()
            feature_names = artifact.feature_names
            
            print(f"Model: {model_name}")
            print(f"  Total features: {len(feature_names)}")
            print()
            print("  Opening Odds Feature Importance:")
            
            # Find and print opening odds feature importance
            found_any = False
            for feat in odds_features:
                if feat in feature_names:
                    idx = feature_names.index(feat)
                    feat_importance = importance[idx]
                    total_importance = sum(importance)
                    pct = (feat_importance / total_importance * 100) if total_importance > 0 else 0.0
                    print(f"    {feat:25s}: {feat_importance:10.4f} ({pct:6.2f}%)")
                    found_any = True
            
            if not found_any:
                print("    (No opening odds features found in model)")
            
            # Compare has_opening_moneyline vs opening_overround
            if 'has_opening_moneyline' in feature_names and 'opening_overround' in feature_names:
                ml_idx = feature_names.index('has_opening_moneyline')
                ov_idx = feature_names.index('opening_overround')
                ml_imp = importance[ml_idx]
                ov_imp = importance[ov_idx]
                ratio = ml_imp / ov_imp if ov_imp > 0 else float('inf')
                print()
                print(f"  Redundancy Check:")
                print(f"    has_opening_moneyline / opening_overround ratio: {ratio:.4f}")
                if ratio < 0.1:
                    print(f"    ✅ has_opening_moneyline has very low importance (likely redundant)")
                elif ratio < 0.5:
                    print(f"    ⚠️  has_opening_moneyline has moderate importance")
                else:
                    print(f"    ❌ has_opening_moneyline has high importance (not redundant)")
            
            print()
            print("-" * 80)
            print()
            
        except Exception as e:
            print(f"❌ Error processing {model_name}: {e}")
            print()
            import traceback
            traceback.print_exc()
            print()

if __name__ == "__main__":
    main()
