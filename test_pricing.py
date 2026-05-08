"""Regression tests for compute_turnkey_total against the manager's reference table.

Run with:  python3 test_pricing.py

These cases come from the screenshots the manager sent (2026-05-08). The bot
must produce the same total the Google Sheets pricing table produces given
the same inputs. If you're tempted to relax these tolerances, talk to the
manager first — the table is the source of truth.
"""

from utils import (
    AGENT_FEE_RUB,
    compute_broker_fee,
    compute_turnkey_total,
)


RUSSIA_FEES = {"svh_rub": 35_000, "lab_rub": 20_000, "perm_registration_rub": 8_000}


def _approx_equal(a, b, tol):
    return abs(a - b) < tol


def test_audi_q2_reference():
    # Screenshot inputs: ₩33.2M, 1998cc, reg 04/2023, 3-5 years.
    # Currency rates from the screenshot itself: USD 74.56, KRW 0.05577.
    result = compute_turnkey_total(
        price_krw=33_200_000,
        krw_rub=0.05577,
        usd_rub=74.56,
        customs_duty_rub=474_130,
        customs_fee_rub=8_530,
        recycling_fee_rub=5_200,
        russia_fees=RUSSIA_FEES,
    )
    expected_total = 2_588_594  # from the Google Sheets ИТОГО cell
    assert _approx_equal(result["total_rub"], expected_total, tol=200), (
        f"Audi Q2: got {result['total_rub']:,.0f}, expected ~{expected_total:,}"
    )
    # Broker line in the screenshot: 22,318 ₽
    assert _approx_equal(result["broker_rub"], 22_318, tol=2), result["broker_rub"]


def test_hyundai_venue_reference():
    # Screenshot inputs: ₩20.8M, 1559cc, reg 04/2022, 3-5 years.
    # Currency rates from the screenshot: USD 74.30, KRW 0.05570.
    result = compute_turnkey_total(
        price_krw=20_800_000,
        krw_rub=0.05570,
        usd_rub=74.30,
        customs_duty_rub=342_550,
        customs_fee_rub=3_100,
        recycling_fee_rub=5_200,
        russia_fees=RUSSIA_FEES,
    )
    expected_total = 1_756_261  # from the Google Sheets ИТОГО cell
    assert _approx_equal(result["total_rub"], expected_total, tol=200), (
        f"Hyundai Venue: got {result['total_rub']:,.0f}, expected ~{expected_total:,}"
    )
    # Broker line in the screenshot: 20,263 ₽
    assert _approx_equal(result["broker_rub"], 20_263, tol=2), result["broker_rub"]


def test_broker_fee_formula():
    # Spot-checks the 1.5% × customs_sum + 15,000 formula directly.
    assert compute_broker_fee(474_130, 8_530, 5_200) == 22_317.9
    assert compute_broker_fee(342_550, 3_100, 5_200) == 20_262.75
    # No customs at all → just the 15K base.
    assert compute_broker_fee(0, 0, 0) == 15_000


def test_breakdown_sums_to_total():
    # Whatever the inputs, AGENT_FEE + korea_operating + russia must equal
    # total_rub. Otherwise the "Детали расчёта" view will silently disagree
    # with the headline number, which is the bug the client reported.
    result = compute_turnkey_total(
        price_krw=25_000_000,
        krw_rub=0.056,
        usd_rub=75.0,
        customs_duty_rub=400_000,
        customs_fee_rub=8_000,
        recycling_fee_rub=5_200,
        russia_fees=RUSSIA_FEES,
    )
    assert (
        AGENT_FEE_RUB + result["korea_operating_rub"] + result["russia_rub"]
        == result["total_rub"]
    )


def test_audi_korea_subtotal_excludes_agent_fee():
    # "Итого расходов по Корее" in the reference table = 1,965,416 ₽ for the
    # Audi case. This is the Korea-side subtotal WITHOUT the agent fee.
    result = compute_turnkey_total(
        price_krw=33_200_000,
        krw_rub=0.05577,
        usd_rub=74.56,
        customs_duty_rub=474_130,
        customs_fee_rub=8_530,
        recycling_fee_rub=5_200,
        russia_fees=RUSSIA_FEES,
    )
    assert _approx_equal(result["korea_operating_rub"], 1_965_416, tol=200), (
        f"got {result['korea_operating_rub']:,.0f}, expected ~1,965,416"
    )


if __name__ == "__main__":
    tests = [
        test_audi_q2_reference,
        test_hyundai_venue_reference,
        test_broker_fee_formula,
        test_breakdown_sums_to_total,
        test_audi_korea_subtotal_excludes_agent_fee,
    ]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"ok  {t.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL {t.__name__}: {e}")
    if failures:
        raise SystemExit(f"{failures} test(s) failed")
    print(f"\n{len(tests)} test(s) passed")
