from utils import clean_number, get_customs_fees


def main():
    # User's reported car: id 41393395, 2000cc, ~17,250,000 KRW × 10,000 / 100 form;
    # using the actual KRW units the bot passes to get_customs_fees.
    result = get_customs_fees(
        engine_volume=2000,
        car_price=17250 * 10000,
        car_year=2025,
        car_month=12,
        power=239,
        engine_type=2,  # diesel
    )

    print(result)
    assert result["ok"] is True, result
    assert {"sbor", "tax", "util"}.issubset(result["data"].keys()), result

    customs_fee = clean_number(result["data"]["sbor"])
    customs_duty = clean_number(result["data"]["tax"])
    util = clean_number(result["data"]["util"])

    print("customs_fee:", customs_fee)
    print("customs_duty:", customs_duty)
    print("util:", util)


if __name__ == "__main__":
    main()
