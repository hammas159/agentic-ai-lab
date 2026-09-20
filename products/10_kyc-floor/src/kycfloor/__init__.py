"""kyc-floor.

Customer onboarding, sanctions and PEP screening, and triage of the alerts screening produces.

The deterministic core lives in :mod:`kycfloor.domain`. Everything the model is
allowed to touch sits above it.
"""

__all__ = ["domain"]
