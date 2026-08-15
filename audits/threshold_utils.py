#!/usr/bin/env python3
"""
audits/threshold_utils.py

Reusable threshold evaluation utilities.

Converts metric violations into standardized Finding objects.
"""

from __future__ import annotations

from typing import Any, Optional

from audits.findings import Finding, Severity


def evaluate_threshold(
    metric: str,
    value: Any,
    category: str,

    maximum: Optional[Any] = None,
    minimum: Optional[Any] = None,

    severity: Severity = Severity.HIGH,

    component: Optional[str] = None,
    source: Optional[str] = None,
    run_id: Optional[str] = None,

    custom_message: Optional[str] = None,
    recommendation: Optional[str] = None,

    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,

) -> Optional[Finding]:
    """
    Evaluate metric against defined boundaries.

    Returns:
        Finding object if violation detected.
        None if metric is compliant.
    """

    metadata = metadata.copy() if metadata else {}
    tags = tags.copy() if tags else []

    # --------------------------------------------
    # Maximum threshold breach
    # --------------------------------------------

    try:

        if maximum is not None and value > maximum:

            metadata.update(
                {
                    "threshold_type": "maximum",
                    "threshold_value": maximum,
                    "observed_value": value,
                }
            )

            return Finding(

                severity=severity,

                category=category,

                metric=metric,

                actual=value,

                expected=f"<= {maximum}",

                message=(
                    custom_message
                    or
                    (
                        f"{metric} exceeded maximum allowed value. "
                        f"Observed={value}, Limit={maximum}"
                    )
                ),

                recommendation=(
                    recommendation
                    or
                    (
                        f"Reduce {metric} below {maximum} "
                        "to restore compliance."
                    )
                ),

                component=component,

                source=source,

                run_id=run_id,

                tags=tags,

                metadata=metadata,
            )


        # --------------------------------------------
        # Minimum threshold breach
        # --------------------------------------------

        if minimum is not None and value < minimum:

            metadata.update(
                {
                    "threshold_type": "minimum",
                    "threshold_value": minimum,
                    "observed_value": value,
                }
            )

            return Finding(

                severity=severity,

                category=category,

                metric=metric,

                actual=value,

                expected=f">= {minimum}",

                message=(
                    custom_message
                    or
                    (
                        f"{metric} fell below minimum allowed value. "
                        f"Observed={value}, Required={minimum}"
                    )
                ),

                recommendation=(
                    recommendation
                    or
                    (
                        f"Increase {metric} above {minimum} "
                        "to restore compliance."
                    )
                ),

                component=component,

                source=source,

                run_id=run_id,

                tags=tags,

                metadata=metadata,
            )

    except TypeError:

        return Finding(

            severity=Severity.CRITICAL,

            category=category,

            metric=metric,

            actual=value,

            expected={
                "minimum": minimum,
                "maximum": maximum,
            },

            message=(
                f"Unable to evaluate threshold for '{metric}'. "
                "Metric type mismatch."
            ),

            recommendation=(
                "Validate metric datatype before running audit."
            ),

            component=component,

            source=source,

            run_id=run_id,

            tags=[
                *tags,
                "AUDIT_ENGINE_ERROR",
            ],

            metadata={
                **metadata,
                "error": "TYPE_COMPARISON_FAILURE",
            },
        )


    return None
