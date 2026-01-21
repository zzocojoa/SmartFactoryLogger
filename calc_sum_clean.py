import json

data = [
    {"적합 중량": "2,293.1"}, {"적합 중량": "3,341.8"}, {"적합 중량": "1,041"}, {"적합 중량": "553.4"},
    {"적합 중량": "508.2"}, {"적합 중량": "603.6"}, {"적합 중량": "494.7"}, {"적합 중량": "536.7"},
    {"적합 중량": "317.5"}, {"적합 중량": "1,276.4"}
]

total = 0.0
for item in data:
    val_str = item["적합 중량"].replace(",", "")
    total += float(val_str)

print(f"Total Valid Weight: {total:,.1f} kg")
