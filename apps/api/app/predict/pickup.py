"""Pick-up predictor module. Supports deterministic stub and TabPFN classifier."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("circlecue.predict")


class PickupPredictor:
    """Estimates the probability that a call will be picked up based on contextual features."""

    def __init__(self, provider: str = "stub"):
        self.provider = provider

    def predict(self, features: Dict[str, Any]) -> float:
        """Predict pickup probability between 0.0 and 1.0."""
        if self.provider == "tabpfn":
            try:
                return self._predict_tabpfn(features)
            except Exception as e:
                logger.warning("TabPFN predictor failed, falling back to stub: %s", e)
                return self._predict_stub(features)
        return self._predict_stub(features)

    def _predict_stub(self, features: Dict[str, Any]) -> float:
        """Deterministic heuristic for pickup probability based on context features."""
        # Baseline score
        score = 0.50

        # Reachability calls: "ok", "prefer_not", "no"
        calls_status = features.get("reachability_calls", "ok")
        if calls_status == "no":
            return 0.05
        elif calls_status == "prefer_not":
            score -= 0.30
        elif calls_status == "ok":
            score += 0.20

        # Phone battery bucket
        battery = features.get("battery_bucket", "ok")
        if battery == "dying":
            return 0.02
        elif battery == "critical":
            score -= 0.30
        elif battery == "low":
            score -= 0.10

        # Phone mode
        phone_mode = features.get("phone_mode", "normal")
        if phone_mode in ("dnd", "silent"):
            score -= 0.20
        if features.get("declared_offline") or features.get("may_go_offline"):
            score -= 0.25

        # Time of day (local hour 0-23)
        hour = features.get("local_hour", 12)
        if 23 <= hour or hour < 7:  # late night / early morning
            score -= 0.35
        elif 9 <= hour <= 19:  # daytime
            score += 0.10

        # Bound score in [0.01, 0.99]
        return max(0.01, min(0.99, round(score, 2)))

    def _predict_tabpfn(self, features: Dict[str, Any]) -> float:
        """TabPFN based inference stub + TODO(verify)."""
        # Note: TabPFN is an in-context tabular foundation model.
        # Check installed package; if not available, raise ImportError.
        try:
            from tabpfn import TabPFNClassifier  # type: ignore # TODO(verify): check TabPFN version on DO
            # TabPFN expects training X, y and query X_test.
            # In stub/online fallback mode, if no training dataset is passed, return stub score.
            train_x = features.get("_train_x")
            train_y = features.get("_train_y")
            test_x = features.get("_test_x")
            if train_x is not None and train_y is not None and test_x is not None:
                clf = TabPFNClassifier(device="cpu", N_ensemble_configurations=4)
                clf.fit(train_x, train_y)
                probs = clf.predict_proba(test_x)
                return float(probs[0][1])
            return self._predict_stub(features)
        except Exception as e:
            logger.debug("TabPFN invocation fallback: %s", e)
            return self._predict_stub(features)


_default_predictor = PickupPredictor()


def predict_pickup_probability(features: Dict[str, Any], provider: Optional[str] = None) -> float:
    """Global convenience function."""
    from app.config import settings
    prov = provider or getattr(settings, "PREDICTOR_PROVIDER", "stub")
    predictor = PickupPredictor(provider=prov)
    return predictor.predict(features)
