#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
API="$BASE_URL/api"

LOGIN_JSON=$(curl -sS -X POST "$API/auth/login" -H "Content-Type: application/json" -d '{"identifier":"smoke@careos","role":"caregiver","locale":"zh-CN"}')
TOKEN=$(echo "$LOGIN_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["access_token"])')

AUTH=(-H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json")

FAMILY_JSON=$(curl -sS -X POST "$API/family" "${AUTH[@]}" -d '{"name":"Smoke Family","timezone":"Asia/Shanghai"}')
FAMILY_ID=$(echo "$FAMILY_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["family_id"])')

curl -sS -X POST "$API/profile" "${AUTH[@]}" -d "{
  \"family_id\": $FAMILY_ID,
  \"age_band\": \"7-9\",
  \"language_level\": \"short_sentence\",
  \"sensory_flags\": [\"sound\"],
  \"triggers\": [\"过渡\"],
  \"soothing_methods\": [\"提前预告\"],
  \"donts\": [\"不可触碰\"],
  \"school_context\": {},
  \"high_friction_scenarios\": [\"transition\"]
}" >/dev/null

curl -sS -X POST "$API/checkin" "${AUTH[@]}" -d "{
  \"family_id\": $FAMILY_ID,
  \"child_sleep_hours\": 5.5,
  \"meltdown_count\": 2,
  \"transition_difficulty\": 8,
  \"sensory_overload_level\": \"medium\",
  \"caregiver_stress\": 8,
  \"caregiver_sleep_hours\": 5,
  \"support_available\": \"none\",
  \"env_changes\": [\"学校事件\"]
}" >/dev/null

PLAN_JSON=$(curl -sS -X POST "$API/plan48h/generate" "${AUTH[@]}" -d "{
  \"family_id\": $FAMILY_ID,
  \"context\": \"manual\",
  \"scenario\": \"transition\",
  \"manual_trigger\": true,
  \"high_risk_selected\": false,
  \"free_text\": \"\"
}")

SCRIPT_JSON=$(curl -sS -X POST "$API/scripts/generate" "${AUTH[@]}" -d "{
  \"family_id\": $FAMILY_ID,
  \"scenario\": \"transition\",
  \"intensity\": \"medium\",
  \"resources\": {\"adults\":1},
  \"high_risk_selected\": false,
  \"free_text\": \"\"
}")

curl -sS -X POST "$API/review" "${AUTH[@]}" -d "{
  \"family_id\": $FAMILY_ID,
  \"scenario\": \"transition\",
  \"intensity\": \"medium\",
  \"triggers\": [\"等待\"],
  \"card_ids\": [\"CARD-0001\"],
  \"outcome_score\": 1,
  \"notes\": \"smoke\",
  \"followup_action\": \"继续\"
}" >/dev/null

WEEK_START=$(python3 - <<'PY'
from datetime import date, timedelta
now=date.today()
monday=now-timedelta(days=(now.isoweekday()-1))
print(monday.isoformat())
PY
)

REPORT_JSON=$(curl -sS "$API/report/weekly/$FAMILY_ID?week_start=$WEEK_START" "${AUTH[@]}")

echo "Smoke check OK"
echo "plan=$(echo "$PLAN_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("blocked"))')"
echo "script=$(echo "$SCRIPT_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("blocked"))')"
echo "report_week=$(echo "$REPORT_JSON" | python3 -c 'import json,sys; print(json.loads(sys.stdin.read()).get("week_start"))')"
