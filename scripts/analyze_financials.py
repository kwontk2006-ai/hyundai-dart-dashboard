
import json
import csv
from pathlib import Path

DATA = Path("data")
YEARS = range(2022, 2026)

# DART 재무제표 계정과 추출 항목 연결
ACCOUNTS = {
    "revenue": {
        "ids": ["ifrs-full_Revenue", "ifrs_Revenue"],
        "names": ["매출액", "수익(매출액)", "매출"]
    },
    "operating_profit": {
        "ids": ["dart_OperatingIncomeLoss"],
        "names": ["영업이익", "영업이익(손실)"]
    },
    "net_income": {
        "ids": ["ifrs-full_ProfitLoss", "ifrs_ProfitLoss"],
        "names": ["당기순이익", "당기순이익(손실)"]
    },
    "assets": {
        "ids": ["ifrs-full_Assets", "ifrs_Assets"],
        "names": ["자산총계"]
    },
    "liabilities": {
        "ids": ["ifrs-full_Liabilities", "ifrs_Liabilities"],
        "names": ["부채총계"]
    },
    "equity": {
        "ids": ["ifrs-full_Equity", "ifrs_Equity"],
        "names": ["자본총계"]
    },
    "current_assets": {
        "ids": ["ifrs-full_CurrentAssets", "ifrs_CurrentAssets"],
        "names": ["유동자산"]
    },
    "current_liabilities": {
        "ids": ["ifrs-full_CurrentLiabilities", "ifrs_CurrentLiabilities"],
        "names": ["유동부채"]
    },
    "operating_cashflow": {
        "ids": [
            "ifrs-full_CashFlowsFromUsedInOperatingActivities",
            "ifrs_CashFlowsFromUsedInOperatingActivities"
        ],
        "names": ["영업활동현금흐름"]
    }
}

# 재무제표 항목이 속한 표
STATEMENTS = {
    "revenue": {"IS", "CIS"},
    "operating_profit": {"IS", "CIS"},
    "net_income": {"IS", "CIS"},
    "assets": {"BS"},
    "liabilities": {"BS"},
    "equity": {"BS"},
    "current_assets": {"BS"},
    "current_liabilities": {"BS"},
    "operating_cashflow": {"CF"}
}


def parse_amount(value):
    """DART 금액을 정수로 변환."""
    if value is None:
        return None

    text = str(value).strip().replace(",", "")

    if text in ("", "-", "null"):
        return None

    try:
        return int(text)
    except ValueError:
        return None


def extract_account(records, key):
    """연결재무제표에서 해당 계정의 전체 합계 금액 추출."""
    spec = ACCOUNTS[key]

    candidates = []

    for row in records:
        if row.get("sj_div") not in STATEMENTS[key]:
            continue

        # 연결재무제표의 전체 항목을 우선 사용
        detail = str(row.get("account_detail", "")).strip()

        if detail not in ("", "-"):
            continue

        account_id = row.get("account_id", "")
        account_name = row.get("account_nm", "").strip()

        if (
            account_id in spec["ids"]
            or account_name in spec["names"]
        ):
            amount = parse_amount(row.get("thstrm_amount"))

            if amount is not None:
                candidates.append({
                    "amount": amount,
                    "id": account_id,
                    "name": account_name
                })

    # 계정 ID가 정확히 일치하는 자료 우선
    for account_id in spec["ids"]:
        matches = [
            c["amount"] for c in candidates
            if c["id"] == account_id
        ]

        if len(set(matches)) == 1 and matches:
            return matches[0]

    # 이름으로 확인한 항목이 유일할 때 사용
    amounts = [c["amount"] for c in candidates]

    if len(set(amounts)) == 1 and amounts:
        return amounts[0]

    if candidates:
        print(f"주의: {key}에 서로 다른 후보 금액이 있습니다.")

    return None


def safe_ratio(numerator, denominator):
    """분모가 없거나 0일 때 잘못된 계산 방지."""
    if numerator is None or denominator in (None, 0):
        return None

    return numerator / denominator * 100


def average(a, b):
    if a is None or b is None:
        return None

    return (a + b) / 2


def extract_year(year):
    filename = DATA / f"financial_{year}.json"

    with open(filename, encoding="utf-8") as file:
        document = json.load(file)

    if document.get("status") != "000":
        raise RuntimeError(f"{year}년 DART 응답 오류")

    records = document.get("list", [])

    # 연결재무제표 여부 확인
    if not records or any(
        row.get("fs_div") != "CFS" for row in records
    ):
        raise RuntimeError(
            f"{year}년 연결재무제표 확인 실패"
        )

    result = {"year": year}

    for key in ACCOUNTS:
        result[key] = extract_account(records, key)

        if result[key] is None:
            print(f"{year}년 {key}: 미확인")

    return result


def save_csv(filename, rows):
    with open(
        DATA / filename,
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(rows[0].keys())
        )

        writer.writeheader()
        writer.writerows(rows)


def main():
    financials = [
        extract_year(year) for year in YEARS
    ]

    save_csv("financial_summary.csv", financials)

    ratios = []

    previous = None

    for current in financials:
        revenue = current["revenue"]

        if previous:
            revenue_growth = safe_ratio(
                revenue - previous["revenue"]
                if revenue is not None
                and previous["revenue"] is not None
                else None,
                previous["revenue"]
            )

            avg_assets = average(
                current["assets"],
                previous["assets"]
            )

            avg_equity = average(
                current["equity"],
                previous["equity"]
            )
        else:
            revenue_growth = None
            avg_assets = None
            avg_equity = None

        row = {
            "year": current["year"],

            "revenue_growth_pct": revenue_growth,

            "operating_margin_pct": safe_ratio(
                current["operating_profit"],
                revenue
            ),

            "net_margin_pct": safe_ratio(
                current["net_income"],
                revenue
            ),

            "current_ratio_pct": safe_ratio(
                current["current_assets"],
                current["current_liabilities"]
            ),

            "debt_to_equity_pct": safe_ratio(
                current["liabilities"],
                current["equity"]
            ),

            "roa_pct": safe_ratio(
                current["net_income"],
                avg_assets
            ),

            "roe_pct": safe_ratio(
                current["net_income"],
                avg_equity
            )
        }

        ratios.append(row)
        previous = current

    save_csv("financial_ratios.csv", ratios)

    print("재무분석 파일 생성 완료")

    for row in ratios:
        print(
            row["year"],
            "영업이익률:",
            row["operating_margin_pct"],
            "부채비율:",
            row["debt_to_equity_pct"]
        )


if __name__ == "__main__":
    main()
