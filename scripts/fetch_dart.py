
import os
import json
import io
import zipfile
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

# 1. GitHub에 등록한 DART 인증키 읽기
API_KEY = os.environ.get("DART_API_KEY")

if not API_KEY:
    raise RuntimeError("DART_API_KEY가 설정되지 않았습니다.")

BASE_URL = "https://opendart.fss.or.kr/api/"

OUTPUT = Path("data")
OUTPUT.mkdir(exist_ok=True)


# 2. DART API에 데이터 요청
def request_dart(endpoint, params=None):
    parameters = {"crtfc_key": API_KEY}
    parameters.update(params or {})

    url = BASE_URL + endpoint + "?" + urllib.parse.urlencode(parameters)

    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read()


# 3. 현대건설의 DART 기업 고유번호 검색
def find_corp_code():
    raw = request_dart("corpCode.xml")

    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        xml_file = archive.namelist()[0]
        root = ET.fromstring(archive.read(xml_file))

    for company in root.findall("list"):
        stock_code = company.findtext("stock_code", "").strip()
        corp_name = company.findtext("corp_name", "").strip()

        if stock_code == "000720" and corp_name == "현대건설":
            return company.findtext("corp_code")

    raise RuntimeError("현대건설의 기업 고유번호를 찾지 못했습니다.")


# 4. 현대건설의 연도별 재무제표 가져오기
def fetch_financials(corp_code, year):
    raw = request_dart(
        "fnlttSinglAcntAll.json",
        {
            "corp_code": corp_code,
            "bsns_year": str(year),
            "reprt_code": "11011",
            "fs_div": "CFS"
        }
    )

    data = json.loads(raw.decode("utf-8-sig"))

    if data.get("status") != "000":
        raise RuntimeError(
            f"{year}년 DART 조회 실패: {data.get('message')}"
        )

    if not data.get("list"):
        raise RuntimeError(f"{year}년 재무제표가 비어 있습니다.")

    output_file = OUTPUT / f"financial_{year}.json"

    with open(output_file, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print(f"{year}년 재무제표 수집 완료")


# 5. 프로그램 실행
def main():
    corp_code = find_corp_code()

    print("현대건설 재무제표 수집 시작")

    for year in range(2022, 2026):
        fetch_financials(corp_code, year)

    print("2022~2025년 재무데이터 수집 완료")


if __name__ == "__main__":
    main()
